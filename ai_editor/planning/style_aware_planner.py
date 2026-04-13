from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .segment_ranker import SegmentRanker


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class StyleAwarePlanner:
    """Incremental planner that converts analysis scores into plan metadata."""

    def __init__(self, ranker: Optional[SegmentRanker] = None) -> None:
        self.ranker = ranker or SegmentRanker()

    def build_plan(
        self,
        analysis: Optional[Dict[str, Any]],
        source_durations: List[float],
        requirements: Dict[str, Any],
    ) -> Dict[str, Any]:
        analysis = analysis or {}
        scenes = analysis.get("scenes") or []
        segments = analysis.get("segments") or []
        style_profile = analysis.get("style_profile") or {}
        ranked = self.ranker.rank(segments, style_profile=style_profile)

        target_pacing = self._target_pacing(style_profile, requirements)
        target_duration = self._target_segment_duration(style_profile, target_pacing)
        target_count = self._target_segment_count(style_profile, target_pacing)
        opening_window = self._opening_window_seconds(style_profile, target_duration)
        density_profile = self._density_profile(style_profile)
        selected = self._select_primary_segments(
            narrative=ranked.get("narrative", []),
            target_pacing=target_pacing,
            target_count=target_count,
            opening_window=opening_window,
        )
        support = self._select_support_segments(
            support=ranked.get("support", []),
            selected=selected,
            target_pacing=target_pacing,
        )

        if selected:
            planned_durations = [self._planned_duration(seg, target_duration, target_pacing) for seg in selected]
        else:
            planned_durations = [
                float(scene.get("duration", 0.0))
                for scene in scenes
                if float(scene.get("duration", 0.0)) > 0
            ]

        return {
            "scene_durations": planned_durations,
            "source_durations": source_durations,
            "intent_mode": requirements.get("intent_mode", "video"),
            "edit_mode": requirements.get("edit_mode", "scene"),
            "planning_strategy": f"style_aware_{target_pacing}",
            "target_pacing": target_pacing,
            "target_segment_duration": target_duration,
            "target_segment_count": target_count,
            "density_profile": density_profile,
            "opening_segment_ids": [seg.get("label") for seg in selected[:2]],
            "support_segment_ids": [seg.get("label") for seg in support],
            "selected_segments": selected,
            "support_segments": support,
            "rejected_segments": ranked.get("rejected", []),
            "style_profile_snapshot": {
                "avg_shot_length": style_profile.get("avg_shot_length"),
                "pacing_label": style_profile.get("pacing_label"),
                "intro_pacing_label": style_profile.get("intro_pacing_label"),
                "short_form_likelihood": style_profile.get("short_form_likelihood"),
                "text_density": style_profile.get("text_density"),
                "ocr_density": style_profile.get("ocr_density"),
            },
            "planning_debug": {
                "strategy_label": f"hook_first_{target_pacing}",
                "opening_window_seconds": opening_window,
                "selected_segment_ids": [seg.get("label") for seg in selected],
                "selected_ranges": [
                    {
                        "label": seg.get("label"),
                        "start": float(seg.get("start", 0.0)),
                        "end": float(seg.get("end", 0.0)),
                        "planner_role": seg.get("planner_role"),
                    }
                    for seg in selected
                ],
                "support_segment_ids": [seg.get("label") for seg in support],
                "rejected_low_score_ids": [
                    seg.get("label")
                    for seg in ranked.get("rejected", [])
                    if seg.get("rejection_reason") in {"low_score", "below_rank_threshold"}
                ],
                "target_pacing_signals": {
                    "target_pacing": target_pacing,
                    "target_segment_duration": target_duration,
                    "target_segment_count": target_count,
                    "density_profile": density_profile,
                },
                "candidate_rankings": {
                    "narrative": self._serialize_candidates(ranked.get("narrative", []), "narrative_rank_score"),
                    "support": self._serialize_candidates(ranked.get("support", []), "support_rank_score"),
                },
            },
        }

    def _target_pacing(self, style_profile: Dict[str, Any], requirements: Dict[str, Any]) -> str:
        pacing_label = str(style_profile.get("pacing_label", "")).lower()
        intro_pacing = str(style_profile.get("intro_pacing_label", "")).lower()
        short_form = float(style_profile.get("short_form_likelihood", 0.0) or 0.0)
        avg_shot_length = float(style_profile.get("avg_shot_length", 0.0) or 0.0)
        text_density = float(style_profile.get("text_density", 0.0) or 0.0)
        ocr_density = float(style_profile.get("ocr_density", 0.0) or 0.0)
        if short_form >= 0.7 or "fast" in pacing_label or intro_pacing == "fast":
            return "fast"
        if short_form >= 0.58 and (text_density >= 0.45 or ocr_density >= 0.35):
            return "fast"
        if "slow" in pacing_label or avg_shot_length >= 5.5:
            return "slow"
        if str(requirements.get("intent_mode", "")).lower() == "shorts":
            return "fast"
        return "medium"

    def _target_segment_duration(self, style_profile: Dict[str, Any], target_pacing: str) -> float:
        avg_shot_length = float(style_profile.get("avg_shot_length", 0.0) or 0.0)
        short_form = float(style_profile.get("short_form_likelihood", 0.0) or 0.0)
        text_density = float(style_profile.get("text_density", 0.0) or 0.0)
        ocr_density = float(style_profile.get("ocr_density", 0.0) or 0.0)
        density_pressure = max(text_density, ocr_density)
        if target_pacing == "fast":
            baseline = 1.8 if short_form >= 0.7 else 2.4
            adjusted = baseline - min(0.45, density_pressure * 0.5)
            return round(_clamp(adjusted, 1.15, max(avg_shot_length or baseline, adjusted)), 3)
        if target_pacing == "slow":
            baseline = avg_shot_length if avg_shot_length > 0 else 5.5
            adjusted = baseline + min(0.6, (1.0 - density_pressure) * 0.35)
            return round(_clamp(adjusted, 4.5, 8.0), 3)
        baseline = avg_shot_length if 2.0 <= avg_shot_length <= 5.0 else 3.5
        adjusted = baseline - min(0.35, density_pressure * 0.25)
        return round(_clamp(adjusted, 2.3, 4.5), 3)

    def _target_segment_count(self, style_profile: Dict[str, Any], target_pacing: str) -> int:
        short_form = float(style_profile.get("short_form_likelihood", 0.0) or 0.0)
        text_density = float(style_profile.get("text_density", 0.0) or 0.0)
        ocr_density = float(style_profile.get("ocr_density", 0.0) or 0.0)
        density_pressure = max(text_density, ocr_density)
        if target_pacing == "fast":
            return 6 if short_form >= 0.75 or density_pressure >= 0.45 else 5
        if target_pacing == "slow":
            return 3
        return 5 if density_pressure >= 0.35 else 4

    def _opening_window_seconds(self, style_profile: Dict[str, Any], target_duration: float) -> float:
        configured = float(style_profile.get("hook_window_seconds", 0.0) or 0.0)
        if configured > 0:
            return round(_clamp(configured, max(2.0, target_duration), 12.0), 3)
        avg_shot_length = float(style_profile.get("avg_shot_length", 0.0) or 0.0)
        inferred = max(2.4, min(8.0, max(target_duration * 1.8, avg_shot_length * 1.6 if avg_shot_length > 0 else 0.0)))
        return round(inferred, 3)

    def _density_profile(self, style_profile: Dict[str, Any]) -> str:
        text_density = float(style_profile.get("text_density", 0.0) or 0.0)
        ocr_density = float(style_profile.get("ocr_density", 0.0) or 0.0)
        density = max(text_density, ocr_density)
        if density >= 0.55:
            return "dense"
        if density >= 0.28:
            return "balanced"
        return "light"

    def _select_primary_segments(
        self,
        narrative: List[Dict[str, Any]],
        target_pacing: str,
        target_count: int,
        opening_window: float,
    ) -> List[Dict[str, Any]]:
        if not narrative:
            return []
        opening_candidates = [
            seg for seg in narrative if float(seg.get("start", 0.0)) <= opening_window
        ]
        opening_pool = opening_candidates or narrative
        opening = sorted(
            opening_pool,
            key=lambda seg: (
                -float(seg.get("hook_score", 0.0)),
                -float(seg.get("novelty_score", 0.0)),
                -float(seg.get("narrative_rank_score", 0.0)),
                float(seg.get("start", 0.0)),
            ),
        )
        selected: List[Dict[str, Any]] = []
        used_ranges: List[Dict[str, Any]] = []
        if opening:
            opener = dict(opening[0])
            opener["planner_role"] = "opening_hook"
            selected.append(opener)
            used_ranges.append(opener)

        for seg in narrative:
            if any(self._same_segment(seg, existing) for existing in selected):
                continue
            if any(self._overlaps(seg, existing) for existing in used_ranges):
                continue
            if any(self._is_redundant(seg, existing, target_pacing) for existing in selected):
                continue
            enriched = dict(seg)
            enriched["planner_role"] = "primary_narrative"
            selected.append(enriched)
            used_ranges.append(enriched)
            if len(selected) >= target_count:
                break
        return sorted(selected, key=lambda seg: float(seg.get("start", 0.0)))

    def _select_support_segments(
        self,
        support: List[Dict[str, Any]],
        selected: List[Dict[str, Any]],
        target_pacing: str,
    ) -> List[Dict[str, Any]]:
        max_support = 3 if target_pacing == "fast" else 2
        chosen: List[Dict[str, Any]] = []
        for seg in support:
            if any(self._same_segment(seg, existing) for existing in selected):
                continue
            if any(self._overlaps(seg, existing) for existing in selected):
                continue
            if any(self._same_visual_cluster(seg, existing) for existing in selected):
                continue
            if any(self._is_redundant(seg, existing, target_pacing) for existing in chosen):
                continue
            if any(self._same_visual_cluster(seg, existing) for existing in chosen):
                continue
            enriched = dict(seg)
            enriched["planner_role"] = "support_broll"
            chosen.append(enriched)
            if len(chosen) >= max_support:
                break
        return sorted(chosen, key=lambda seg: float(seg.get("start", 0.0)))

    def _planned_duration(self, segment: Dict[str, Any], target_duration: float, target_pacing: str) -> float:
        raw = max(float(segment.get("end", 0.0)) - float(segment.get("start", 0.0)), 0.0)
        if raw <= 0:
            return target_duration
        if target_pacing == "fast":
            return round(min(raw, max(1.2, target_duration)), 3)
        if target_pacing == "slow":
            return round(max(min(raw, target_duration * 1.25), target_duration * 0.85), 3)
        return round(max(min(raw, target_duration * 1.15), target_duration * 0.8), 3)

    def _serialize_candidates(
        self,
        candidates: Sequence[Dict[str, Any]],
        score_key: str,
        limit: int = 6,
    ) -> List[Dict[str, Any]]:
        return [
            {
                "label": seg.get("label"),
                "start": float(seg.get("start", 0.0)),
                "end": float(seg.get("end", 0.0)),
                "planner_role": seg.get("planner_role"),
                score_key: float(seg.get(score_key, 0.0)),
                "hook_score": float(seg.get("hook_score", 0.0)),
                "editorial_score": float(seg.get("editorial_score", seg.get("score", 0.0))),
                "broll_score": float(seg.get("broll_score", 0.0)),
                "novelty_score": float(seg.get("novelty_score", 0.0)),
                "visual_cluster_id": seg.get("visual_cluster_id"),
            }
            for seg in list(candidates)[:limit]
        ]

    def _same_segment(self, left: Dict[str, Any], right: Dict[str, Any]) -> bool:
        if left.get("label") and right.get("label") and left.get("label") == right.get("label"):
            return True
        return (
            round(float(left.get("start", 0.0)), 3) == round(float(right.get("start", 0.0)), 3)
            and round(float(left.get("end", left.get("start", 0.0))), 3)
            == round(float(right.get("end", right.get("start", 0.0))), 3)
        )

    def _is_redundant(self, left: Dict[str, Any], right: Dict[str, Any], target_pacing: str) -> bool:
        left_scene = left.get("scene_id")
        right_scene = right.get("scene_id")
        if left_scene and right_scene and left_scene == right_scene:
            start_gap = abs(float(left.get("start", 0.0)) - float(right.get("start", 0.0)))
            threshold = 0.8 if target_pacing == "fast" else 1.25
            if start_gap <= threshold:
                return True
        if self._same_visual_cluster(left, right):
            start_gap = abs(float(left.get("start", 0.0)) - float(right.get("start", 0.0)))
            if start_gap <= (1.0 if target_pacing == "fast" else 1.6):
                return True
        return False

    def _same_visual_cluster(self, left: Dict[str, Any], right: Dict[str, Any]) -> bool:
        left_cluster = str(left.get("visual_cluster_id", "")).strip().lower()
        right_cluster = str(right.get("visual_cluster_id", "")).strip().lower()
        return bool(left_cluster and right_cluster and left_cluster != "unknown" and left_cluster == right_cluster)

    def _overlaps(self, left: Dict[str, Any], right: Dict[str, Any]) -> bool:
        left_start = float(left.get("start", 0.0))
        left_end = float(left.get("end", left_start))
        right_start = float(right.get("start", 0.0))
        right_end = float(right.get("end", right_start))
        return left_end > right_start and right_end > left_start
