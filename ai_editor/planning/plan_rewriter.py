from __future__ import annotations

from typing import Any, Dict, List, Optional

from .segment_ranker import SegmentRanker


class PlanRewriter:
    """Apply safe deterministic validation rewrites to a planner output."""

    def __init__(self, ranker: Optional[SegmentRanker] = None) -> None:
        self.ranker = ranker or SegmentRanker()

    def apply(
        self,
        plan: Dict[str, Any],
        validation: Dict[str, Any],
        analysis: Optional[Dict[str, Any]] = None,
        requirements: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        analysis = analysis or {}
        requirements = requirements or {}
        style_profile = analysis.get("style_profile") or plan.get("style_profile_snapshot") or {}
        ranked = self.ranker.rank(analysis.get("segments") or [], style_profile=style_profile)
        rewritten = dict(plan)
        rewritten["selected_segments"] = [dict(seg) for seg in plan.get("selected_segments") or []]
        rewritten["support_segments"] = [dict(seg) for seg in plan.get("support_segments") or []]

        applied_actions: List[Dict[str, Any]] = []
        for action in validation.get("rewrite_actions") or []:
            if self._apply_action(rewritten, action, ranked, requirements):
                applied_actions.append(action)

        rewritten["scene_durations"] = self._recalculate_scene_durations(
            rewritten.get("selected_segments") or [],
            float(rewritten.get("target_segment_duration") or 0.0),
            str(rewritten.get("target_pacing", "medium")).lower(),
        )
        rewritten["opening_segment_ids"] = [seg.get("label") for seg in (rewritten.get("selected_segments") or [])[:2]]
        rewritten["support_segment_ids"] = [seg.get("label") for seg in rewritten.get("support_segments") or []]

        debug = dict(rewritten.get("planning_debug") or {})
        debug["rewrite_applied"] = bool(applied_actions)
        debug["rewrite_actions_applied"] = applied_actions
        debug["selected_segment_ids"] = [seg.get("label") for seg in rewritten.get("selected_segments") or []]
        debug["support_segment_ids"] = [seg.get("label") for seg in rewritten.get("support_segments") or []]
        target_signals = dict(debug.get("target_pacing_signals") or {})
        target_signals["target_segment_duration"] = rewritten.get("target_segment_duration")
        target_signals["target_segment_count"] = rewritten.get("target_segment_count")
        target_signals["density_profile"] = rewritten.get("density_profile")
        debug["target_pacing_signals"] = target_signals
        rewritten["planning_debug"] = debug
        return rewritten

    def _apply_action(
        self,
        rewritten: Dict[str, Any],
        action: Dict[str, Any],
        ranked: Dict[str, List[Dict[str, Any]]],
        requirements: Dict[str, Any],
    ) -> bool:
        name = str(action.get("action", "")).strip().lower()
        if not name:
            return False
        if name == "replace_opening_with_best_hook":
            return self._replace_opening_with_best_hook(rewritten, ranked, action)
        if name == "drop_redundant_primary_indices":
            return self._drop_redundant_primary_indices(rewritten, ranked, action)
        if name == "trim_support_segments":
            return self._trim_support_segments(rewritten, action)
        if name == "swap_in_visual_contrast":
            return self._swap_in_visual_contrast(rewritten, ranked, action)
        if name == "tighten_target_duration":
            return self._set_target_duration(rewritten, action)
        if name == "relax_target_duration":
            return self._set_target_duration(rewritten, action)
        if name == "raise_target_duration_floor":
            return self._raise_target_duration_floor(rewritten, action)
        if name == "drop_low_score_segments":
            return self._drop_low_score_segments(rewritten, action)
        if name == "increase_target_density":
            return self._set_target_density(rewritten, ranked, action)
        if name == "reduce_target_density":
            return self._set_target_density(rewritten, ranked, action)
        return False

    def _replace_opening_with_best_hook(
        self,
        rewritten: Dict[str, Any],
        ranked: Dict[str, List[Dict[str, Any]]],
        action: Dict[str, Any],
    ) -> bool:
        selected = list(rewritten.get("selected_segments") or [])
        if not selected:
            return False
        candidate_label = action.get("candidate_label")
        candidate = next((dict(seg) for seg in selected if seg.get("label") == candidate_label), None)
        if candidate is None:
            candidate = next(
                (dict(seg) for seg in ranked.get("narrative", []) if seg.get("label") == candidate_label),
                None,
            )
        if candidate is None:
            return False
        candidate["planner_role"] = "opening_hook"
        remaining = [dict(seg) for seg in selected if seg.get("label") != candidate.get("label")]
        for seg in remaining:
            if seg.get("planner_role") == "opening_hook":
                seg["planner_role"] = "primary_narrative"
        rewritten["selected_segments"] = [candidate] + remaining
        rewritten["selected_segments"] = self._dedupe_by_label(rewritten["selected_segments"])
        return True

    def _drop_redundant_primary_indices(
        self,
        rewritten: Dict[str, Any],
        ranked: Dict[str, List[Dict[str, Any]]],
        action: Dict[str, Any],
    ) -> bool:
        indices = sorted({int(index) for index in action.get("indices", []) if isinstance(index, int)}, reverse=True)
        selected = [dict(seg) for seg in rewritten.get("selected_segments") or []]
        if not selected or not indices:
            return False
        removed_scene_ids = set()
        changed = False
        for index in indices:
            if 0 <= index < len(selected):
                removed_scene_ids.add(selected[index].get("scene_id"))
                selected.pop(index)
                changed = True
        if not changed:
            return False
        for candidate in ranked.get("narrative", []):
            if len(selected) >= int(rewritten.get("target_segment_count") or len(selected)):
                break
            if candidate.get("scene_id") in removed_scene_ids:
                continue
            if any(self._same_segment(candidate, existing) for existing in selected):
                continue
            selected.append(dict(candidate))
        rewritten["selected_segments"] = self._dedupe_by_label(selected)
        return True

    def _trim_support_segments(self, rewritten: Dict[str, Any], action: Dict[str, Any]) -> bool:
        keep_count = max(0, int(action.get("keep_count", 0) or 0))
        support = [dict(seg) for seg in rewritten.get("support_segments") or []]
        if len(support) <= keep_count:
            return False
        rewritten["support_segments"] = support[:keep_count]
        return True

    def _swap_in_visual_contrast(
        self,
        rewritten: Dict[str, Any],
        ranked: Dict[str, List[Dict[str, Any]]],
        action: Dict[str, Any],
    ) -> bool:
        indices = sorted({int(index) for index in action.get("indices", []) if isinstance(index, int)})
        selected = [dict(seg) for seg in rewritten.get("selected_segments") or []]
        if not selected or not indices:
            return False
        changed = False
        for index in indices:
            if index <= 0 or index >= len(selected):
                continue
            previous = selected[index - 1]
            current = selected[index]
            in_plan_replacement = next(
                (
                    dict(selected[candidate_index])
                    for candidate_index in range(index + 1, len(selected))
                    if not self._same_visual_cluster(selected[candidate_index], previous)
                    and not self._same_visual_cluster(selected[candidate_index], current)
                ),
                None,
            )
            if in_plan_replacement is not None:
                replacement_label = in_plan_replacement.get("label")
                later_index = next(
                    (candidate_index for candidate_index in range(index + 1, len(selected)) if selected[candidate_index].get("label") == replacement_label),
                    None,
                )
                if later_index is not None:
                    selected[index], selected[later_index] = dict(selected[later_index]), dict(selected[index])
                    changed = True
                    continue
            replacement = next(
                (
                    dict(candidate)
                    for candidate in ranked.get("narrative", [])
                    if not any(self._same_segment(candidate, existing) for existing in selected)
                    and not self._same_visual_cluster(candidate, previous)
                    and not self._same_visual_cluster(candidate, current)
                ),
                None,
            )
            if replacement is None:
                continue
            replacement["planner_role"] = current.get("planner_role", "primary_narrative")
            selected[index] = replacement
            changed = True
        if changed:
            rewritten["selected_segments"] = self._dedupe_by_label(selected)
        return changed

    def _set_target_duration(self, rewritten: Dict[str, Any], action: Dict[str, Any]) -> bool:
        new_duration = float(action.get("target_segment_duration") or 0.0)
        old_duration = float(rewritten.get("target_segment_duration") or 0.0)
        if new_duration <= 0 or abs(new_duration - old_duration) < 1e-6:
            return False
        rewritten["target_segment_duration"] = round(new_duration, 3)
        return True

    def _raise_target_duration_floor(self, rewritten: Dict[str, Any], action: Dict[str, Any]) -> bool:
        new_duration = float(action.get("target_segment_duration") or 0.0)
        old_duration = float(rewritten.get("target_segment_duration") or 0.0)
        if new_duration <= old_duration:
            return False
        rewritten["target_segment_duration"] = round(new_duration, 3)
        return True

    def _drop_low_score_segments(self, rewritten: Dict[str, Any], action: Dict[str, Any]) -> bool:
        labels = {str(label) for label in action.get("labels", []) if label}
        if not labels:
            return False
        selected = [dict(seg) for seg in rewritten.get("selected_segments") or []]
        support = [dict(seg) for seg in rewritten.get("support_segments") or []]
        new_selected = [seg for seg in selected if seg.get("label") not in labels]
        new_support = [seg for seg in support if seg.get("label") not in labels]
        changed = len(new_selected) != len(selected) or len(new_support) != len(support)
        if changed:
            rewritten["selected_segments"] = new_selected
            rewritten["support_segments"] = new_support
        return changed

    def _set_target_density(
        self,
        rewritten: Dict[str, Any],
        ranked: Dict[str, List[Dict[str, Any]]],
        action: Dict[str, Any],
    ) -> bool:
        target_count = max(1, int(action.get("target_segment_count") or 0))
        current_count = int(rewritten.get("target_segment_count") or 0)
        changed = False
        if target_count != current_count:
            rewritten["target_segment_count"] = target_count
            changed = True
        selected = [dict(seg) for seg in rewritten.get("selected_segments") or []]
        if len(selected) > target_count:
            rewritten["selected_segments"] = selected[:target_count]
            return True
        if len(selected) < target_count:
            for candidate in ranked.get("narrative", []):
                if len(selected) >= target_count:
                    break
                if any(self._same_segment(candidate, existing) for existing in selected):
                    continue
                selected.append(dict(candidate))
            rewritten["selected_segments"] = self._dedupe_by_label(selected)[:target_count]
            return True
        return changed

    def _recalculate_scene_durations(
        self,
        selected: List[Dict[str, Any]],
        target_duration: float,
        target_pacing: str,
    ) -> List[float]:
        if not selected:
            return []
        durations: List[float] = []
        for seg in selected:
            raw = max(0.0, float(seg.get("end", 0.0)) - float(seg.get("start", 0.0)))
            if raw <= 0:
                durations.append(round(target_duration, 3))
                continue
            if target_pacing == "fast":
                durations.append(round(min(raw, max(1.2, target_duration)), 3))
            elif target_pacing == "slow":
                durations.append(round(max(min(raw, target_duration * 1.25), target_duration * 0.85), 3))
            else:
                durations.append(round(max(min(raw, target_duration * 1.15), target_duration * 0.8), 3))
        return durations

    def _dedupe_by_label(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        deduped: List[Dict[str, Any]] = []
        for seg in segments:
            if any(self._same_segment(seg, existing) for existing in deduped):
                continue
            deduped.append(seg)
        return deduped

    def _same_segment(self, left: Dict[str, Any], right: Dict[str, Any]) -> bool:
        if left.get("label") and right.get("label") and left.get("label") == right.get("label"):
            return True
        return (
            round(float(left.get("start", 0.0)), 3) == round(float(right.get("start", 0.0)), 3)
            and round(float(left.get("end", left.get("start", 0.0))), 3)
            == round(float(right.get("end", right.get("start", 0.0))), 3)
        )

    def _same_visual_cluster(self, left: Dict[str, Any], right: Dict[str, Any]) -> bool:
        left_cluster = str(left.get("visual_cluster_id", "")).strip().lower()
        right_cluster = str(right.get("visual_cluster_id", "")).strip().lower()
        return bool(left_cluster and right_cluster and left_cluster != "unknown" and left_cluster == right_cluster)
