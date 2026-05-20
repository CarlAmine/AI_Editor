from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from ai_editor.editing.intent_parser import IntentParser
from ai_editor.generation_modes import (
    FREE_GENERATION_MODE,
    REFERENCE_STYLE_TRANSFER_MODE,
    VISION_TEMPLATE_LEARNING_MODE,
    normalize_generation_mode,
)
from ai_editor.llm_client import chat_json, chat_text, get_active_model_name

log = logging.getLogger(__name__)

REQUIRED_FIELDS = [
    "video_topic", "target_audience", "platform", "duration_seconds",
    "aspect_ratio", "orientation", "tone", "pacing", "style_reference",
    "call_to_action", "branding", "subtitles", "deadline", "budget",
    "intent_mode", "refit_mode", "generation_mode", "edit_mode",
]

DEFAULT_STATE: Dict[str, Any] = {
    "video_topic": "General promotional/edit video",
    "target_audience": "General audience",
    "platform": "YouTube",
    "duration_seconds": 60,
    "aspect_ratio": "16:9",
    "orientation": "horizontal",
    "tone": "engaging",
    "pacing": "medium",
    "style_reference": "",
    "call_to_action": "",
    "branding": "",
    "subtitles": "yes",
    "deadline": "",
    "budget": "",
    "intent_mode": "video",
    "refit_mode": "crop",
    "generation_mode": REFERENCE_STYLE_TRANSFER_MODE,
    "edit_mode": "scene",
    "edit_requests": [],
    "user_requests": [],
}

_INTENT_PARSER = IntentParser()


def _normalize_state(current_state: Dict) -> Dict:
    state = dict(DEFAULT_STATE)
    if current_state:
        state.update(current_state)
    if not isinstance(state.get("edit_requests"), list):
        state["edit_requests"] = []
    if not isinstance(state.get("user_requests"), list):
        state["user_requests"] = []
    return state


def _is_editing_instruction(text: str) -> bool:
    """
    Quick heuristic to decide whether to run IntentParser.
    Avoids burning an LLM call on pure preference messages like
    "make it for TikTok" or "set the duration to 45 seconds".
    """
    text_low = text.lower()
    editing_signals = [
        "remove", "cut", "delete", "trim", "add", "replace", "move",
        "change", "make", "increase", "decrease", "faster", "slower",
        "more", "less", "shorter", "longer", "shake", "zoom", "fade",
        "transition", "clip", "shot", "intro", "outro", "ending",
        "beginning", "hook", "replicate", "match", "reference",
        "pacing", "energy", "feel", "style", "effect", "b-roll",
        "caption", "overlay", "between", "after", "before",
    ]
    return any(signal in text_low for signal in editing_signals)


def _extract_generation_mode(text: str) -> str:
    text_low = text.lower()
    if any(k in text_low for k in [
        "train template", "learn template", "template learning", "train model",
        "learn model", "vision template learning",
    ]):
        return VISION_TEMPLATE_LEARNING_MODE
    if any(k in text_low for k in [
        "free generation", "free mode", "non mimic", "not mimic",
    ]):
        return FREE_GENERATION_MODE
    if any(k in text_low for k in [
        "vision mode", "reference vision", "reference mimic", "reference mimic mode",
        "replicate edit", "replicate the edit", "replicate this edit",
        "copy style", "copy the style", "copy editing style", "copy the editing style",
        "match reference", "match the reference", "same edit", "same edit style",
        "same style", "use reference style",
    ]):
        return REFERENCE_STYLE_TRANSFER_MODE
    return ""


def _normalize_generation_mode_for_state(value: str, state: Dict[str, Any]) -> str:
    has_reference = bool(
        str(state.get("style_reference", "")).strip()
        or str(state.get("reference_url", "")).strip()
        or str(state.get("primary_url", "")).strip()
        or state.get("motion_effects_path")
    )
    default = REFERENCE_STYLE_TRANSFER_MODE if has_reference else FREE_GENERATION_MODE
    return normalize_generation_mode(value, default=default)


def _extract_edit_mode(text: str) -> str:
    text_low = text.lower()
    if any(k in text_low for k in [
        "ocr mode", "ocr-based", "ocr based", "text timeline",
        "follow text", "use ocr",
    ]):
        return "ocr"
    if any(k in text_low for k in [
        "scene mode", "scene-based", "scene based", "use scenes", "scene timeline",
    ]):
        return "scene"
    return ""


def _summarize_pipeline_feedback(state: Dict) -> str:
    feedback = state.get("pipeline_feedback")
    if not isinstance(feedback, dict):
        return ""
    reason = str(feedback.get("reason", "")).strip()
    error = str(feedback.get("error", "")).strip()
    stage = str(feedback.get("stage", "")).strip()
    if not reason and not error:
        return ""
    summary = f"stage={stage or 'UNKNOWN'}"
    if reason:
        summary += f", reason={reason}"
    if error:
        summary += f", error={error}"
    return summary


def _extract_preferences(
    user_input: str,
    state: Dict,
    analyzer_output: str,
) -> Dict[str, Any]:
    """
    Runs the LLM preference extractor (unchanged from original).
    Returns a dict of REQUIRED_FIELDS values.
    """
    extraction_prompt = (
        "Extract and normalize video preferences from the user message.\n"
        "Use defaults if unclear; do not block on missing info.\n"
        "Return a JSON object with keys:\n"
        f"{REQUIRED_FIELDS}\n"
        "Allowed intent_mode: video|shorts. Allowed refit_mode: crop|pad.\n"
        "Allowed generation_mode: free_generation_mode|reference_style_transfer"
        "|vision_template_learning.\n"
        "Allowed edit_mode: scene|ocr.\n"
        "If a value is unknown, return null.\n\n"
        f"Current state: {json.dumps(state, ensure_ascii=False, default=str)}\n"
        f"Analyzer context: {analyzer_output}\n"
        f"User message: {user_input}\n"
    )
    result = chat_json(
        messages=[
            {
                "role": "system",
                "content": (
                    "You extract user preferences for a video editing assistant. "
                    "Output JSON only."
                ),
            },
            {"role": "user", "content": extraction_prompt},
        ],
        temperature=0.2,
    )
    return result if isinstance(result, dict) else {}


def _build_reply(
    user_input: str,
    state: Dict,
    parsed_ops: List[Dict],
) -> str:
    """
    Generates the assistant's conversational reply.
    Tells the user what was understood in plain language.
    """
    if parsed_ops:
        op_summary = "; ".join(
            f"{op.get('operation')} on {op.get('target') or op.get('scope', 'video')}"
            for op in parsed_ops[:3]
        )
        if len(parsed_ops) > 3:
            op_summary += f" (and {len(parsed_ops) - 3} more)"
    else:
        op_summary = "no specific edit operations detected"

    state_summary = (
        f"platform={state.get('platform')}, "
        f"tone={state.get('tone')}, "
        f"pacing={state.get('pacing')}, "
        f"edit_mode={state.get('edit_mode')}, "
        f"generation_mode={state.get('generation_mode')}"
    )

    pipeline_feedback = _summarize_pipeline_feedback(state)
    if pipeline_feedback:
        state_summary += f", pipeline_feedback={pipeline_feedback}"

    reply = chat_text(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful video editing assistant. "
                    "Respond naturally in 1-2 short sentences. "
                    "Confirm what the user asked for using plain language - "
                    "do not mention JSON, operations, or technical terms. "
                    "Be concise and friendly."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"User said: \"{user_input}\"\n"
                    f"What was understood: {op_summary}\n"
                    f"Current state: {state_summary}"
                ),
            },
        ]
    )

    if not reply:
        if parsed_ops:
            op = parsed_ops[0]
            reply = (
                f"Got it - I'll {op.get('operation', 'apply that change')} "
                f"on the {op.get('scope', 'video')}."
            )
        else:
            reply = "Got it, I've updated your preferences."

    return reply


def process_ui_turn(
    user_input: str,
    current_state: Dict,
    analyzer_output: str,
    api_key: str = None,
) -> Dict:
    """
    Processes one turn of the chat UI.

    Returns a dict with keys:
        updated_state   - the new state dict (includes edit_requests and
                          parsed_operations for the executor)
        next_message    - assistant reply string
        is_complete     - always False (completion is handled by the pipeline)
        final_report    - always None
        model_used      - active LLM model name
    """
    del api_key
    state = _normalize_state(current_state)

    state["user_requests"].append(user_input.strip())

    extracted = _extract_preferences(user_input, state, analyzer_output)
    for key in REQUIRED_FIELDS:
        val = extracted.get(key)
        if val is not None and val != "":
            state[key] = val

    explicit_gen_mode = _extract_generation_mode(user_input)
    if explicit_gen_mode:
        state["generation_mode"] = explicit_gen_mode

    explicit_edit_mode = _extract_edit_mode(user_input)
    if explicit_edit_mode:
        state["edit_mode"] = explicit_edit_mode

    if str(state.get("intent_mode", "")).lower() not in {"video", "shorts"}:
        state["intent_mode"] = "video"
    if str(state.get("refit_mode", "")).lower() not in {"crop", "pad"}:
        state["refit_mode"] = "crop"
    state["generation_mode"] = _normalize_generation_mode_for_state(
        str(state.get("generation_mode", "") or ""),
        state,
    )
    if str(state.get("edit_mode", "")).lower() not in {"scene", "ocr"}:
        state["edit_mode"] = "scene"

    parsed_ops: List[Dict] = []
    if _is_editing_instruction(user_input):
        try:
            operations = _INTENT_PARSER.parse(user_input, current_state=state)
            parsed_ops = [op.to_dict() for op in operations]

            existing_keys = {
                (r.get("operation"), r.get("target"), r.get("scope"))
                for r in state["edit_requests"]
                if isinstance(r, dict)
            }
            for op_dict in parsed_ops:
                key = (op_dict.get("operation"), op_dict.get("target"), op_dict.get("scope"))
                if key not in existing_keys:
                    state["edit_requests"].append(op_dict)
                    existing_keys.add(key)
        except Exception as exc:
            log.exception("IntentParser failed for input %r: %s", user_input[:80], exc)
            state["edit_requests"].append({
                "operation": "custom",
                "value": user_input.strip(),
                "scope": "global",
                "metadata": {"unresolved": True, "parse_error": str(exc)},
            })

    state["parsed_operations"] = parsed_ops

    next_message = _build_reply(user_input, state, parsed_ops)

    return {
        "updated_state": state,
        "next_message": next_message,
        "is_complete": False,
        "final_report": None,
        "model_used": get_active_model_name(),
    }
