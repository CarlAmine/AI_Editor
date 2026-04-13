from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional, Sequence

from ai_editor.planning import PlanRewriter, PlanValidator, SegmentRanker

from .edit_operations import EditOperation


class PlanPatcher:
    """Applies structured edit operations to an existing timeline plan."""

    def __init__(
        self,
        ranker: Optional[SegmentRanker] = None,
        validator: Optional[PlanValidator] = None,
        rewriter: Optional[PlanRewriter] = None,
    ) -> None:
        self.ranker = ranker or SegmentRanker()
        self.validator = validator or PlanValidator()
        self.rewriter = rewriter or PlanRewriter(self.ranker)

    def apply_operations(
        self,
        plan: Dict[str, Any],
        operations: Sequence[EditOperation],
        analysis: Optional[Dict[str, Any]] = None,
        requirements: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        analysis = analysis or {}
        requirements = requirements or {}
        patched = dict(plan)
        patched["selected_segments"] = [dict(seg) for seg in plan.get("selected_segments") or []]
        patched["support_segments"] = [dict(seg) for seg in plan.get("support_segments") or []]
        patched.setdefault("edit_directives", [])
        patched.setdefault("edit_metadata", {})

        ranked = self.ranker.rank(
            analysis.get("segments") or [],
            style_profile=analysis.get("style_profile") or patched.get("style_profile_snapshot") or {},
        )
        applied: List[Dict[str, Any]] = []
        deferred: List[Dict[str, Any]] = []
        for operation in operations:
            outcome = self._apply_single(patched, operation, ranked)
            if outcome == "applied":
                applied.append(operation.to_dict())
            elif outcome == "deferred":
                deferred.append(operation.to_dict())

        patched["scene_durations"] = self._recalculate_scene_durations(patched)
        validation = self.validator.validate(patched, analysis=analysis, requirements=requirements)
        rewritten = self.rewriter.apply(patched, validation, analysis=analysis, requirements=requirements)
        final_validation = self.validator.validate(rewritten, analysis=analysis, requirements=requirements)

        debug = dict(rewritten.get("planning_debug") or {})
        debug["edit_operations_applied"] = applied
        debug["edit_operations_deferred"] = deferred
        debug["edit_patch_ran"] = True
        rewritten["planning_debug"] = debug
        rewritten["plan_validation"] = dict(final_validation)
        rewritten["plan_validation"]["pre_rewrite"] = validation
        rewritten["plan_patch"] = {
            "applied_operations": applied,
            "deferred_operations": deferred,
            "operation_count": len(applied),
            "patch_strategy": "deterministic_edit_patch",
        }
        return rewritten

    def _apply_single(
        self,
        patched: Dict[str, Any],
        operation: EditOperation,
        ranked: Dict[str, List[Dict[str, Any]]],
    ) -> str:
        name = operation.operation
        if name == "promote_hook":
            return "applied" if self._promote_hook(patched, ranked, operation) else "noop"
        if name == "increase_pacing":
            return "applied" if self._adjust_pacing(patched, faster=True, operation=operation) else "noop"
        if name == "decrease_pacing":
            return "applied" if self._adjust_pacing(patched, faster=False, operation=operation) else "noop"
        if name in {"reduce_repetition", "increase_visual_diversity"}:
            return "applied" if self._increase_visual_diversity(patched, ranked, operation) else "noop"
        if name == "increase_broll":
            return "applied" if self._increase_broll(patched, ranked, operation) else "noop"
        if name == "decrease_broll":
            return "applied" if self._decrease_broll(patched, operation) else "noop"
        if name == "trim_middle":
            return "applied" if self._trim_middle(patched, operation) else "noop"
        if name == "shorten_ending":
            return "applied" if self._shorten_ending(patched, operation) else "noop"
        if name == "prioritize_source":
            return "applied" if self._prioritize_source(patched, ranked, operation, prioritize=True) else "noop"
        if name == "deprioritize_source":
            return "applied" if self._prioritize_source(patched, ranked, operation, prioritize=False) else "noop"
        if name == "increase_captions":
            return self._record_edit_directive(patched, operation)
        if name == "decrease_captions":
            return self._record_edit_directive(patched, operation)
        if name == "increase_overlay_density":
            return self._record_edit_directive(patched, operation)
        if name == "decrease_overlay_density":
            return self._record_edit_directive(patched, operation)
        if name == "change_caption_style":
            return self._record_edit_directive(patched, operation)
        if name == "remove_segment":
            return "applied" if self._remove_segment(patched, operation) else "noop"
        if name == "replace_segment":
            return "applied" if self._replace_segment(patched, ranked, operation) else "noop"
        if name == "move_segment":
            return "applied" if self._move_segment(patched, operation) else "noop"
        return "noop"

    def _promote_hook(self, patched: Dict[str, Any], ranked: Dict[str, List[Dict[str, Any]]], operation: EditOperation) -> bool:
        selected = self._segments_in_window(patched.get("selected_segments") or [], operation)
        if not selected:
            return False
        strongest = next(
            iter(
                sorted(
                    [seg for seg in ranked.get("narrative") or [] if self._segment_matches_operation(seg, operation)],
                    key=lambda seg: (
                        -float(seg.get("hook_score", 0.0)),
                        -float(seg.get("narrative_rank_score", 0.0)),
                        float(seg.get("start", 0.0)),
                    ),
                )
            ),
            None,
        )
        if strongest is None:
            return False
        if selected[0].get("label") == strongest.get("label"):
            return False
        rewritten = self.rewriter.apply(
            patched,
            {"rewrite_actions": [{"action": "replace_opening_with_best_hook", "candidate_label": strongest.get("label")}]},
        )
        patched.update(rewritten)
        return True

    def _adjust_pacing(self, patched: Dict[str, Any], faster: bool, operation: EditOperation) -> bool:
        current_duration = float(patched.get("target_segment_duration") or 0.0)
        current_count = int(patched.get("target_segment_count") or len(patched.get("selected_segments") or []))
        current_pacing = str(patched.get("target_pacing", "medium")).lower()
        if current_duration <= 0:
            return False
        if faster:
            patched["target_segment_duration"] = round(max(1.15, current_duration * 0.85), 3)
            patched["target_segment_count"] = current_count + 1
            patched["target_pacing"] = "fast" if current_pacing != "slow" else "medium"
        else:
            patched["target_segment_duration"] = round(current_duration * 1.15, 3)
            patched["target_segment_count"] = max(1, current_count - 1)
            patched["target_pacing"] = "slow" if current_pacing != "fast" else "medium"
        patched.setdefault("edit_metadata", {})["last_pacing_scope"] = operation.scope
        return True

    def _increase_visual_diversity(self, patched: Dict[str, Any], ranked: Dict[str, List[Dict[str, Any]]], operation: EditOperation) -> bool:
        indices = [
            index
            for index in range(1, len(patched.get("selected_segments") or []))
            if self._segment_matches_operation((patched.get("selected_segments") or [])[index], operation)
        ]
        rewritten = self.rewriter.apply(
            patched,
            {"rewrite_actions": [{"action": "swap_in_visual_contrast", "indices": indices or list(range(1, len(patched.get("selected_segments") or [])))}]},
        )
        if rewritten.get("selected_segments") != patched.get("selected_segments"):
            patched.update(rewritten)
            return True
        return False

    def _increase_broll(self, patched: Dict[str, Any], ranked: Dict[str, List[Dict[str, Any]]], operation: EditOperation) -> bool:
        selected = patched.get("selected_segments") or []
        support = [dict(seg) for seg in patched.get("support_segments") or []]
        support_labels = {seg.get("label") for seg in support}
        for candidate in ranked.get("support", []):
            if candidate.get("label") in support_labels:
                continue
            if any(self._same_visual_cluster(candidate, primary) for primary in selected):
                continue
            if not self._segment_matches_operation(candidate, operation, selected):
                continue
            enriched = dict(candidate)
            enriched["planner_role"] = "support_broll"
            if operation.metadata:
                enriched.setdefault("edit_metadata", {}).update(operation.metadata)
            support.append(enriched)
            patched["support_segments"] = support
            patched["support_segment_ids"] = [seg.get("label") for seg in support]
            return True
        return False

    def _decrease_broll(self, patched: Dict[str, Any], operation: EditOperation) -> bool:
        support = [dict(seg) for seg in patched.get("support_segments") or []]
        if not support:
            return False
        if operation.scope == "global" and operation.time_window is None:
            support = support[: max(0, len(support) - 1)]
        else:
            kept = [seg for seg in support if not self._segment_matches_operation(seg, operation, patched.get("selected_segments") or [])]
            if len(kept) == len(support):
                return False
            support = kept
        patched["support_segments"] = support
        patched["support_segment_ids"] = [seg.get("label") for seg in support]
        return True

    def _trim_middle(self, patched: Dict[str, Any], operation: EditOperation) -> bool:
        selected = [dict(seg) for seg in patched.get("selected_segments") or []]
        if len(selected) <= 2:
            return False
        candidate_indices = [index for index, seg in enumerate(selected) if self._segment_matches_operation(seg, operation, selected)]
        if not candidate_indices:
            return False
        middle_index = candidate_indices[len(candidate_indices) // 2]
        selected.pop(middle_index)
        patched["selected_segments"] = selected
        patched["target_segment_count"] = max(1, int(patched.get("target_segment_count") or len(selected)) - 1)
        return True

    def _shorten_ending(self, patched: Dict[str, Any], operation: EditOperation) -> bool:
        selected = [dict(seg) for seg in patched.get("selected_segments") or []]
        if not selected:
            return False
        candidate_indices = [index for index, seg in enumerate(selected) if self._segment_matches_operation(seg, operation, selected)]
        if len(selected) > 2 and candidate_indices:
            selected.pop(candidate_indices[-1])
            patched["selected_segments"] = selected
            patched["target_segment_count"] = max(1, int(patched.get("target_segment_count") or len(selected)) - 1)
            return True
        patched["target_segment_duration"] = round(max(1.15, float(patched.get("target_segment_duration") or 1.5) * 0.9), 3)
        return True

    def _prioritize_source(
        self,
        patched: Dict[str, Any],
        ranked: Dict[str, List[Dict[str, Any]]],
        operation: EditOperation,
        prioritize: bool,
    ) -> bool:
        source_value = operation.source_target or operation.value
        if not source_value:
            return False
        selected = [dict(seg) for seg in patched.get("selected_segments") or []]
        preferred = [dict(seg) for seg in ranked.get("narrative", []) if str(seg.get("source", "")).lower() == str(source_value).lower()]
        if not preferred:
            return False
        if prioritize:
            selected.sort(key=lambda seg: 0 if str(seg.get("source", "")).lower() == str(source_value).lower() else 1)
        else:
            selected.sort(key=lambda seg: 1 if str(seg.get("source", "")).lower() == str(source_value).lower() else 0)
        if selected != patched.get("selected_segments"):
            patched["selected_segments"] = selected
            return True
        return False

    def _remove_segment(self, patched: Dict[str, Any], operation: EditOperation) -> bool:
        selected = [dict(seg) for seg in patched.get("selected_segments") or []]
        if not selected:
            return False
        index = self._resolve_target_index(selected, operation)
        if index is None:
            return False
        selected.pop(index)
        patched["selected_segments"] = selected
        patched["target_segment_count"] = max(1, int(patched.get("target_segment_count") or len(selected)) - 1)
        return True

    def _replace_segment(
        self,
        patched: Dict[str, Any],
        ranked: Dict[str, List[Dict[str, Any]]],
        operation: EditOperation,
    ) -> bool:
        selected = [dict(seg) for seg in patched.get("selected_segments") or []]
        if not selected:
            return False
        index = self._resolve_target_index(selected, operation)
        if index is None:
            return False
        current = selected[index]
        if operation.value == "stronger_hook" or operation.target == "opening":
            replacement = next(
                (dict(seg) for seg in ranked.get("narrative", []) if seg.get("label") != current.get("label") and float(seg.get("hook_score", 0.0)) > float(current.get("hook_score", 0.0))),
                None,
            )
        else:
            replacement = next(
                (dict(seg) for seg in ranked.get("narrative", []) if seg.get("label") != current.get("label")),
                None,
            )
        if replacement is None:
            return False
        replacement["planner_role"] = current.get("planner_role", "primary_narrative")
        selected[index] = replacement
        patched["selected_segments"] = selected
        return True

    def _move_segment(self, patched: Dict[str, Any], operation: EditOperation) -> bool:
        selected = [dict(seg) for seg in patched.get("selected_segments") or []]
        if len(selected) < 2:
            return False
        index = self._resolve_target_index(selected, operation)
        if index is None:
            return False
        position = str(operation.position or operation.scope or "").lower().strip()
        segment = selected.pop(index)
        if position in {"opening", "intro"}:
            selected.insert(0, segment)
        elif position == "middle":
            selected.insert(len(selected) // 2, segment)
        elif position in {"ending", "end", "outro"}:
            selected.append(segment)
        else:
            return False
        patched["selected_segments"] = selected
        return True

    def _resolve_target_index(self, selected: Sequence[Dict[str, Any]], operation: EditOperation) -> Optional[int]:
        normalized = str(operation.segment_target or operation.target or "").lower().strip()
        if not normalized:
            matches = [index for index, segment in enumerate(selected) if self._segment_matches_operation(segment, operation, selected)]
            return matches[0] if matches else None
        if normalized in {"opening", "intro"}:
            return 0 if selected else None
        if normalized in {"ending", "outro"}:
            return len(selected) - 1 if selected else None
        if normalized == "middle":
            return len(selected) // 2 if selected else None
        for index, segment in enumerate(selected):
            if str(segment.get("label", "")).lower() == normalized:
                return index
        return None

    def _record_edit_directive(self, patched: Dict[str, Any], operation: EditOperation) -> str:
        directives = list(patched.get("edit_directives") or [])
        directives.append(operation.to_dict())
        patched["edit_directives"] = directives
        overlay_metadata = dict(patched.get("edit_metadata") or {})
        overlay_metadata.setdefault("overlay_directives", []).append(operation.to_dict())
        patched["edit_metadata"] = overlay_metadata
        return "deferred"

    def _matches_scope(self, segment: Dict[str, Any], selected: Sequence[Dict[str, Any]], scope: str) -> bool:
        if scope == "global":
            return True
        if scope == "opening":
            return float(segment.get("start", 0.0)) <= 3.0
        if scope == "ending":
            max_end = max((float(item.get("end", 0.0)) for item in selected), default=float(segment.get("end", 0.0)))
            return float(segment.get("start", 0.0)) >= max_end * 0.66
        if scope == "middle":
            max_end = max((float(item.get("end", 0.0)) for item in selected), default=float(segment.get("end", 0.0)))
            start = float(segment.get("start", 0.0))
            return max_end * 0.25 <= start <= max_end * 0.75
        return True

    def _segment_matches_operation(
        self,
        segment: Dict[str, Any],
        operation: EditOperation,
        selected: Sequence[Dict[str, Any]] | None = None,
    ) -> bool:
        if operation.segment_target and str(segment.get("label", "")).lower() != str(operation.segment_target).lower():
            return False
        if operation.source_target and str(segment.get("source", "")).lower() != str(operation.source_target).lower():
            return False
        if operation.time_window is not None:
            window = operation.time_window
            start = float(segment.get("start", 0.0))
            end = float(segment.get("end", start))
            if window.start is not None and end < float(window.start):
                return False
            if window.end is not None and start > float(window.end):
                return False
            if window.label and window.label not in {"global", "explicit_range"} and selected is not None:
                return self._matches_scope(segment, selected, window.label)
        if selected is not None and operation.scope and operation.scope != "global":
            return self._matches_scope(segment, selected, operation.scope)
        return True

    def _segments_in_window(
        self,
        segments: Sequence[Dict[str, Any]],
        operation: EditOperation,
    ) -> List[Dict[str, Any]]:
        return [dict(segment) for segment in segments if self._segment_matches_operation(segment, operation, segments)]

    def _recalculate_scene_durations(self, patched: Dict[str, Any]) -> List[float]:
        selected = patched.get("selected_segments") or []
        if not selected:
            return list(patched.get("scene_durations") or [])
        durations: List[float] = []
        target_duration = float(patched.get("target_segment_duration") or 0.0)
        target_pacing = str(patched.get("target_pacing", "medium")).lower()
        for segment in selected:
            raw = max(0.0, float(segment.get("end", 0.0)) - float(segment.get("start", 0.0)))
            if raw <= 0:
                durations.append(round(target_duration, 3))
            elif target_pacing == "fast":
                durations.append(round(min(raw, max(1.2, target_duration)), 3))
            elif target_pacing == "slow":
                durations.append(round(max(min(raw, target_duration * 1.25), target_duration * 0.85), 3))
            else:
                durations.append(round(max(min(raw, target_duration * 1.15), target_duration * 0.8), 3))
        return durations

    def _same_visual_cluster(self, left: Dict[str, Any], right: Dict[str, Any]) -> bool:
        left_cluster = str(left.get("visual_cluster_id", "")).strip().lower()
        right_cluster = str(right.get("visual_cluster_id", "")).strip().lower()
        return bool(left_cluster and right_cluster and left_cluster != "unknown" and left_cluster == right_cluster)
