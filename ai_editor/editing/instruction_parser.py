from __future__ import annotations

import re
from typing import List

from .edit_operations import EditOperation, TimeWindowTarget


class InstructionParser:
    """Rule-based parser that converts natural language into edit operations."""

    def parse(self, text: str) -> List[EditOperation]:
        normalized = " ".join(str(text or "").strip().lower().split())
        normalized = re.sub(r"^(remove|cut|delete|trim|add|replace)\s*:\s*", r"\1 ", normalized)
        normalized = re.sub(r"^edit\s*:\s*", "", normalized)
        if not normalized:
            return []

        operations: List[EditOperation] = []
        scope = self._extract_scope(normalized)
        time_window = self._extract_time_window(normalized)

        if any(phrase in normalized for phrase in {"replace the intro with a stronger hook", "stronger hook", "promote the hook"}):
            operations.append(EditOperation(operation="promote_hook", scope="opening", time_window=time_window or TimeWindowTarget(label="opening"), section_label="opening"))
        elif "opening faster" in normalized or "make the opening faster" in normalized:
            operations.append(EditOperation(operation="increase_pacing", scope="opening", time_window=time_window or TimeWindowTarget(label="opening"), section_label="opening"))

        if any(phrase in normalized for phrase in {"remove repetitive shots", "reduce repetition", "less repetitive"}):
            operations.append(EditOperation(operation="reduce_repetition", scope=scope, time_window=time_window, section_label=scope))
        if any(phrase in normalized for phrase in {"increase visual diversity", "more visually diverse", "less repetitive looking"}):
            operations.append(EditOperation(operation="increase_visual_diversity", scope=scope, time_window=time_window, section_label=scope))

        if "use more b-roll" in normalized or "more b-roll" in normalized:
            operations.append(EditOperation(operation="increase_broll", scope=scope, time_window=time_window, section_label=scope))
        if "less b-roll" in normalized or "decrease b-roll" in normalized:
            operations.append(EditOperation(operation="decrease_broll", scope=scope, time_window=time_window, section_label=scope))

        if any(phrase in normalized for phrase in {"make it less cluttered", "less cluttered", "cleaner"}):
            operations.append(EditOperation(operation="decrease_broll", scope=scope, time_window=time_window, section_label=scope, intensity=0.8))
            operations.append(EditOperation(operation="reduce_repetition", scope=scope, time_window=time_window, section_label=scope, intensity=0.8))
            operations.append(EditOperation(operation="decrease_overlay_density", scope=scope, time_window=time_window, section_label=scope, intensity=0.8))

        if any(phrase in normalized for phrase in {"increase pacing", "faster overall", "make it faster"}):
            operations.append(EditOperation(operation="increase_pacing", scope=scope, time_window=time_window, section_label=scope))
        if any(phrase in normalized for phrase in {"decrease pacing", "slower overall", "make it slower"}):
            operations.append(EditOperation(operation="decrease_pacing", scope=scope, time_window=time_window, section_label=scope))

        if "trim the middle" in normalized or "trim middle" in normalized:
            operations.append(EditOperation(operation="trim_middle", scope="middle", time_window=TimeWindowTarget(label="middle"), section_label="middle"))
        if any(phrase in normalized for phrase in {"shorten the ending", "shorten ending", "make the ending shorter"}):
            operations.append(EditOperation(operation="shorten_ending", scope="ending", time_window=TimeWindowTarget(label="ending"), section_label="ending"))

        prioritize_match = re.search(r"(?:prioritize|use more clips from|use more from)\s+source\s+([a-z0-9_\-]+)", normalized)
        if prioritize_match:
            operations.append(EditOperation(operation="prioritize_source", value=prioritize_match.group(1), source_target=prioritize_match.group(1), scope=scope, time_window=time_window, section_label=scope))
        more_source_match = re.search(r"use more clips from\s+([a-z0-9_\-]+)", normalized)
        if more_source_match:
            operations.append(EditOperation(operation="prioritize_source", value=more_source_match.group(1), source_target=more_source_match.group(1), scope=scope, time_window=time_window, section_label=scope))
        deprioritize_match = re.search(r"(?:deprioritize|use fewer clips from|use less from)\s+source\s+([a-z0-9_\-]+)", normalized)
        if deprioritize_match:
            operations.append(EditOperation(operation="deprioritize_source", value=deprioritize_match.group(1), source_target=deprioritize_match.group(1), scope=scope, time_window=time_window, section_label=scope))

        if any(phrase in normalized for phrase in {"add more captions", "increase captions", "more captions"}):
            operations.append(EditOperation(operation="increase_captions", scope=scope, time_window=time_window, section_label=scope))
            operations.append(EditOperation(operation="increase_overlay_density", scope=scope, time_window=time_window, section_label=scope))
        if any(phrase in normalized for phrase in {"fewer captions", "decrease captions", "less captions"}):
            operations.append(EditOperation(operation="decrease_captions", scope=scope, time_window=time_window, section_label=scope))
            operations.append(EditOperation(operation="decrease_overlay_density", scope=scope, time_window=time_window, section_label=scope))
        if "increase overlay density" in normalized:
            operations.append(EditOperation(operation="increase_overlay_density", scope=scope, time_window=time_window, section_label=scope))
        if "decrease overlay density" in normalized:
            operations.append(EditOperation(operation="decrease_overlay_density", scope=scope, time_window=time_window, section_label=scope))

        caption_style_match = re.search(r"caption style(?: to)?\s+([a-z0-9_\-\s]+)$", normalized)
        if "change caption style" in normalized or caption_style_match:
            style_value = caption_style_match.group(1).strip() if caption_style_match else "requested_change"
            operations.append(
                EditOperation(
                    operation="change_caption_style",
                    value=style_value,
                    scope=scope,
                    time_window=time_window,
                    section_label=scope,
                    metadata={"renderer_ready": False},
                )
            )

        remove_match = re.search(r"remove\s+segment\s+([a-z0-9_\-]+)", normalized)
        if remove_match:
            operations.append(EditOperation(operation="remove_segment", target=remove_match.group(1), segment_target=remove_match.group(1), scope=scope, time_window=time_window, section_label=scope))
        elif "remove the intro" in normalized or "remove intro" in normalized:
            operations.append(EditOperation(operation="remove_segment", target="opening", scope="opening", time_window=TimeWindowTarget(label="opening"), section_label="opening"))
        elif "remove the ending" in normalized or "remove ending" in normalized:
            operations.append(EditOperation(operation="remove_segment", target="ending", scope="ending", time_window=TimeWindowTarget(label="ending"), section_label="ending"))
        elif "remove that repetitive part near the end" in normalized:
            operations.append(EditOperation(operation="remove_segment", target="ending", scope="ending", time_window=TimeWindowTarget(label="ending"), section_label="ending", metadata={"reason": "repetition"}))

        replace_match = re.search(r"replace\s+segment\s+([a-z0-9_\-]+)", normalized)
        if replace_match:
            operations.append(EditOperation(operation="replace_segment", target=replace_match.group(1), segment_target=replace_match.group(1), scope=scope, time_window=time_window, section_label=scope))
        elif "replace the intro" in normalized:
            operations.append(EditOperation(operation="replace_segment", target="opening", value="stronger_hook", scope="opening", time_window=TimeWindowTarget(label="opening"), section_label="opening"))

        move_match = re.search(r"move\s+segment\s+([a-z0-9_\-]+)\s+(?:to|into)\s+(opening|middle|ending|end)", normalized)
        if move_match:
            position = "ending" if move_match.group(2) == "end" else move_match.group(2)
            operations.append(
                EditOperation(
                    operation="move_segment",
                    target=move_match.group(1),
                    segment_target=move_match.group(1),
                    position=position,
                    scope=position,
                    time_window=TimeWindowTarget(label=position),
                    section_label=position,
                )
            )
        elif "put more product shots after the hook" in normalized:
            operations.append(
                EditOperation(
                    operation="increase_broll",
                    scope="middle",
                    time_window=TimeWindowTarget(label="post_hook", start=2.0),
                    section_label="post_hook",
                    metadata={"desired_content": "product_shots", "position": "after_hook"},
                )
            )

        return self._dedupe(operations)

    def _extract_scope(self, normalized: str) -> str:
        if "opening" in normalized or "intro" in normalized:
            return "opening"
        if "middle" in normalized:
            return "middle"
        if "ending" in normalized or "outro" in normalized:
            return "ending"
        if "near the end" in normalized or "at the end" in normalized:
            return "ending"
        return "global"

    def _extract_time_window(self, normalized: str) -> TimeWindowTarget | None:
        range_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)\s*(?:s|sec|seconds)?", normalized)
        if range_match:
            start = float(range_match.group(1))
            end = float(range_match.group(2))
            if end > start:
                return TimeWindowTarget(start=start, end=end, label="explicit_range")
        scope = self._extract_scope(normalized)
        if scope != "global":
            return TimeWindowTarget(label=scope)
        return None

    def _dedupe(self, operations: List[EditOperation]) -> List[EditOperation]:
        deduped: List[EditOperation] = []
        seen = set()
        for operation in operations:
            time_key = None
            if operation.time_window is not None:
                time_key = (operation.time_window.label, operation.time_window.start, operation.time_window.end)
            key = (operation.operation, operation.target, operation.value, operation.scope, operation.position, operation.source_target, time_key)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(operation)
        return deduped
