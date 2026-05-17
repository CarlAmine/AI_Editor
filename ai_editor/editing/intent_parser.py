from __future__ import annotations

"""
LLM-powered intent parser.

Replaces the regex-based _extract_action_requests() in chatbot_interface.py
and the hardcoded phrase matching in InstructionParser.

Given a user message and the current canonical plan state, it returns a list
of EditOperation objects that the pipeline executor can act on directly.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from ai_editor.editing.edit_operations import EditOperation, TimeWindowTarget
from ai_editor.llm_client import chat_json

log = logging.getLogger(__name__)

# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are the intent parser for an AI video editor.

Your job is to read the user's editing instruction and the current video plan,
then output a JSON array of edit operations that describe EXACTLY what the user
wants to change. You must never output free text — only a JSON array.

## EditOperation schema

Each operation is a JSON object with these fields:

  operation       (string, required)  — what to do. Must be one of:
                    remove_segment, replace_segment, move_segment,
                    trim_clip, set_clip_duration,
                    increase_pacing, decrease_pacing,
                    increase_broll, decrease_broll,
                    reduce_repetition, increase_visual_diversity,
                    increase_overlay_density, decrease_overlay_density,
                    increase_captions, decrease_captions,
                    change_caption_style, promote_hook,
                    prioritize_source, deprioritize_source,
                    set_transition, set_motion_effect,
                    reference_vision_mode, custom

  target          (string, optional)  — what the operation applies to.
                    Can be a shot index ("shot_3"), a section name
                    ("opening", "middle", "ending"), a clip identifier,
                    or a description ("the slow part", "clip after the hook").

  value           (string, optional)  — the new value or desired state.
                    e.g. for set_transition: "fade_to_black"
                    e.g. for change_caption_style: "bold_white"
                    e.g. for set_motion_effect: "zoom_in"

  scope           (string)            — "opening" | "middle" | "ending" | "global"
                    Default: "global"

  intensity       (float 0.0–1.0)    — strength of the operation. Default: 1.0

  time_window     (object, optional)  — if the user specified a time range:
                    { "start": float_seconds, "end": float_seconds, "label": string }

  position        (string, optional)  — for move_segment: where to move it.
                    "opening" | "middle" | "ending"

  source_target   (string, optional)  — for prioritize/deprioritize_source:
                    the source clip identifier.

  segment_target  (string, optional)  — for remove/replace/move_segment:
                    the specific segment identifier.

  section_label   (string, optional)  — human-readable label for the affected
                    section.

  metadata        (object, optional)  — any extra context.

## Rules

1. Return ONLY a JSON array. No preamble, no explanation, no markdown fences.
2. If the user's message contains multiple edit instructions, return one object
   per instruction.
3. If the intent is completely unclear and cannot be mapped to any operation,
   return an array with a single object:
   [{"operation": "custom", "value": "<verbatim user instruction>",
     "scope": "global", "metadata": {"unresolved": true}}]
4. Never return an empty array. If in doubt, use "custom".
5. Use the current plan context to resolve vague references like "the third
   clip" (map to shot_3 or the actual clip identifier from the plan).
6. Do not invent clip identifiers that aren't in the plan. Use "unknown" for
   the target if you cannot resolve it.
7. For vision mode instructions ("replicate this edit", "use the reference
   style", "apply the same shake"), set operation to "reference_vision_mode"
   and include relevant metadata.
"""

# ── Few-shot examples ─────────────────────────────────────────────────────────

_FEW_SHOT_EXAMPLES = [
    {
        "user": "the intro feels too slow",
        "plan_context": "3 shots in opening section, avg 4.2s per shot",
        "output": [
            {
                "operation": "increase_pacing",
                "scope": "opening",
                "intensity": 0.8,
                "section_label": "opening",
                "metadata": {"reason": "user said intro feels slow"}
            }
        ]
    },
    {
        "user": "cut the third clip",
        "plan_context": "canonical_timeline has 6 shots: shot_1 through shot_6",
        "output": [
            {
                "operation": "remove_segment",
                "target": "shot_3",
                "segment_target": "shot_3",
                "scope": "global",
                "section_label": "shot_3"
            }
        ]
    },
    {
        "user": "I want the shake effect from the reference on my second clip too",
        "plan_context": "reference video has shake effect on shot_2, replacement clips loaded",
        "output": [
            {
                "operation": "set_motion_effect",
                "target": "shot_2",
                "value": "shake",
                "scope": "global",
                "metadata": {"replicate_from_reference": True}
            }
        ]
    },
    {
        "user": "make the energy pick up after the hook and add a faster cut between clips 2 and 4",
        "plan_context": "6 shots total, hook is shot_1",
        "output": [
            {
                "operation": "increase_pacing",
                "scope": "middle",
                "intensity": 0.9,
                "section_label": "post_hook",
                "metadata": {"position": "after_hook"}
            },
            {
                "operation": "set_clip_duration",
                "target": "shot_2",
                "scope": "global",
                "intensity": 0.7,
                "metadata": {"faster_cut": True, "between": ["shot_2", "shot_4"]}
            }
        ]
    },
    {
        "user": "add a fade to black before the last shot",
        "plan_context": "5 shots, shot_5 is the last",
        "output": [
            {
                "operation": "set_transition",
                "target": "shot_4",
                "value": "fade_to_black",
                "scope": "ending",
                "metadata": {"position": "outgoing"}
            }
        ]
    },
    {
        "user": "replicate the same edit style as the reference video onto my clips",
        "plan_context": "reference video analyzed, motion_effects.json available",
        "output": [
            {
                "operation": "reference_vision_mode",
                "scope": "global",
                "value": "full_replication",
                "metadata": {"apply_motion_effects": True, "apply_transitions": True,
                             "apply_rhythm": True}
            }
        ]
    }
]


def _build_plan_context(current_state: Dict[str, Any]) -> str:
    """
    Extracts a concise, LLM-readable summary of the current plan state.
    Used as context so the LLM can resolve vague references like "the third
    clip" to actual shot identifiers.
    """
    parts: List[str] = []

    # Generation mode
    gen_mode = current_state.get("generation_mode", "unknown")
    parts.append(f"generation_mode={gen_mode}")

    # Canonical timeline summary
    plan = current_state.get("current_plan") or {}
    timeline = (
        plan.get("canonical_timeline")
        or current_state.get("canonical_timeline")
        or []
    )
    if timeline:
        shot_count = len(timeline)
        parts.append(f"canonical_timeline has {shot_count} shots")
        shot_ids = []
        for i, row in enumerate(timeline[:10]):  # cap at 10 to avoid prompt bloat
            sid = row.get("scene_id") or row.get("id") or f"shot_{i+1}"
            dur = row.get("duration") or row.get("clip_duration") or "?"
            shot_ids.append(f"shot_{i+1}(id={sid}, dur={dur}s)")
        parts.append("shots: " + ", ".join(shot_ids))
    else:
        parts.append("no canonical_timeline available yet")

    # Motion effects summary
    motion_path = current_state.get("motion_effects_path")
    if motion_path:
        parts.append("motion_effects.json available (shake/zoom/pan/transition data)")

    # Reference video
    ref = (
        current_state.get("reference_url")
        or current_state.get("style_reference")
        or ""
    )
    if ref:
        parts.append(f"reference_video={ref[:60]}")

    # Edit history
    existing_requests = current_state.get("edit_requests") or []
    if existing_requests:
        parts.append(f"prior_edit_requests={len(existing_requests)}")

    return "; ".join(parts)


def _format_few_shot() -> str:
    """Formats the few-shot examples for injection into the user prompt."""
    lines = ["## Examples\n"]
    for ex in _FEW_SHOT_EXAMPLES:
        lines.append(f"User: \"{ex['user']}\"")
        lines.append(f"Plan context: {ex['plan_context']}")
        lines.append(f"Output: {json.dumps(ex['output'], indent=2)}")
        lines.append("")
    return "\n".join(lines)


def _parse_operation(raw: Dict[str, Any]) -> EditOperation:
    """
    Safely converts a raw dict from the LLM response into an EditOperation.
    Missing optional fields get their dataclass defaults.
    """
    tw_raw = raw.get("time_window")
    time_window: Optional[TimeWindowTarget] = None
    if isinstance(tw_raw, dict):
        time_window = TimeWindowTarget(
            start=tw_raw.get("start"),
            end=tw_raw.get("end"),
            label=str(tw_raw.get("label") or "global"),
        )
    elif isinstance(raw.get("scope"), str) and raw.get("scope") != "global":
        time_window = TimeWindowTarget(label=str(raw.get("scope", "global")))

    return EditOperation(
        operation=str(raw.get("operation") or "custom"),
        target=raw.get("target"),
        value=raw.get("value"),
        intensity=float(raw.get("intensity") or 1.0),
        scope=str(raw.get("scope") or "global"),
        time_window=time_window,
        source_target=raw.get("source_target"),
        segment_target=raw.get("segment_target"),
        section_label=raw.get("section_label"),
        position=raw.get("position"),
        metadata=dict(raw.get("metadata") or {}),
    )


class IntentParser:
    """
    LLM-powered replacement for the regex-based _extract_action_requests()
    and the hardcoded InstructionParser.

    Parses any free-form user editing instruction into a list of
    EditOperation objects using an LLM call with few-shot examples and
    plan-state context.

    Usage:
        parser = IntentParser()
        operations = parser.parse(user_message, current_state)
    """

    def parse(
        self,
        user_message: str,
        current_state: Optional[Dict[str, Any]] = None,
    ) -> List[EditOperation]:
        """
        Parses `user_message` into EditOperation objects.

        Args:
            user_message:  The raw user input from the chat UI.
            current_state: The current job state dict (used to resolve
                           vague references like "the third clip").

        Returns:
            List of EditOperation objects. Never empty — falls back to
            a single "custom" operation if the intent cannot be resolved.
        """
        state = current_state or {}
        plan_context = _build_plan_context(state)
        few_shot = _format_few_shot()

        user_prompt = (
            f"{few_shot}\n"
            f"## Current task\n\n"
            f"Plan context: {plan_context}\n\n"
            f"User message: \"{user_message}\"\n\n"
            f"Return only the JSON array of edit operations."
        )

        raw_response = chat_json(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
        )

        # chat_json returns a dict if the LLM wrapped the array in an object.
        # Unwrap common patterns: {"operations": [...]} or {"edits": [...]}
        if isinstance(raw_response, dict):
            for key in ("operations", "edits", "edit_operations", "results", "items"):
                if isinstance(raw_response.get(key), list):
                    raw_response = raw_response[key]
                    break
            else:
                # Single operation returned as dict
                raw_response = [raw_response]

        if not isinstance(raw_response, list) or not raw_response:
            log.warning(
                "IntentParser: LLM returned unexpected format for input %r — "
                "falling back to custom operation. raw=%r",
                user_message[:80],
                raw_response,
            )
            return [
                EditOperation(
                    operation="custom",
                    value=user_message.strip(),
                    scope="global",
                    metadata={"unresolved": True, "raw_input": user_message},
                )
            ]

        operations: List[EditOperation] = []
        for item in raw_response:
            if not isinstance(item, dict):
                continue
            try:
                op = _parse_operation(item)
                operations.append(op)
            except Exception as exc:
                log.warning("IntentParser: failed to parse operation %r: %s", item, exc)

        if not operations:
            operations = [
                EditOperation(
                    operation="custom",
                    value=user_message.strip(),
                    scope="global",
                    metadata={"unresolved": True, "parse_failed": True},
                )
            ]

        log.info(
            "IntentParser: parsed %d operation(s) from %r",
            len(operations),
            user_message[:60],
        )
        return operations
