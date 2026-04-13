from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


class PlanValidator:
    """Deterministic validator for style-aware timeline plans."""

    def validate(
        self,
        plan: Dict[str, Any],
        analysis: Optional[Dict[str, Any]] = None,
        requirements: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        analysis = analysis or {}
        requirements = requirements or {}
        style_profile = analysis.get("style_profile") or plan.get("style_profile_snapshot") or {}
        selected = list(plan.get("selected_segments") or [])
        support = list(plan.get("support_segments") or [])
        rejected = list(plan.get("rejected_segments") or [])
        target_pacing = str(plan.get("target_pacing", "medium")).lower()
        target_duration = float(plan.get("target_segment_duration") or 0.0)
        target_count = int(plan.get("target_segment_count") or len(selected) or 0)

        checks = {
            "opening_hook": self._check_opening_hook(selected),
            "pacing_consistency": self._check_pacing_consistency(selected, target_pacing, target_duration, style_profile),
            "redundancy": self._check_redundancy(selected, support),
            "visual_diversity": self._check_visual_diversity(selected, support),
            "support_balance": self._check_support_balance(selected, support, target_pacing),
            "density_suitability": self._check_density_suitability(selected, target_count, style_profile),
            "text_readability": self._check_text_readability(selected, target_duration, style_profile),
            "low_score_overuse": self._check_low_score_overuse(selected, support, rejected),
        }
        validation_score = round(sum(float(check["score"]) for check in checks.values()) / max(len(checks), 1), 4)

        warnings: List[Dict[str, Any]] = []
        recommendations: List[Dict[str, Any]] = []
        rewrite_actions: List[Dict[str, Any]] = []
        for name, check in checks.items():
            if check.get("status") != "pass":
                warnings.append(
                    {
                        "code": check.get("code", name.upper()),
                        "message": check.get("message", name),
                        "detail": check.get("detail"),
                    }
                )
            recommendations.extend(check.get("recommendations", []))
            rewrite_actions.extend(check.get("rewrite_actions", []))

        return {
            "validation_score": validation_score,
            "checks": checks,
            "warnings": warnings,
            "recommendations": recommendations,
            "rewrite_actions": rewrite_actions,
            "validator_strategy": "deterministic_style_plan_validator",
        }

    def _check_opening_hook(self, selected: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        if not selected:
            return {
                "status": "pass",
                "score": 1.0,
                "code": "OPENING_HOOK_OK",
                "message": "No selected segments to validate.",
                "detail": {"selected_count": 0},
                "recommendations": [],
                "rewrite_actions": [],
            }
        opening = selected[0]
        opening_hook = float(opening.get("hook_score", 0.0) or 0.0)
        strongest = max(float(seg.get("hook_score", 0.0) or 0.0) for seg in selected)
        gap = strongest - opening_hook
        if opening_hook >= 0.67 or gap <= 0.12:
            return {
                "status": "pass",
                "score": 1.0,
                "code": "OPENING_HOOK_OK",
                "message": "Opening hook strength is acceptable.",
                "detail": {"opening_label": opening.get("label"), "opening_hook_score": round(opening_hook, 4)},
                "recommendations": [],
                "rewrite_actions": [],
            }
        best_index = next(
            (index for index, seg in enumerate(selected) if float(seg.get("hook_score", 0.0) or 0.0) == strongest),
            0,
        )
        return {
            "status": "warn",
            "score": round(_clamp(1.0 - gap), 4),
            "code": "OPENING_HOOK_WEAK",
            "message": "Opening segment underuses available hook strength.",
            "detail": {
                "opening_label": opening.get("label"),
                "opening_hook_score": round(opening_hook, 4),
                "strongest_hook_score": round(strongest, 4),
            },
            "recommendations": [
                {
                    "type": "opening",
                    "message": "Promote the highest-hook narrative segment into the opener.",
                }
            ],
            "rewrite_actions": [
                {
                    "action": "replace_opening_with_best_hook",
                    "candidate_index": best_index,
                    "candidate_label": selected[best_index].get("label"),
                }
            ],
        }

    def _check_pacing_consistency(
        self,
        selected: Sequence[Dict[str, Any]],
        target_pacing: str,
        target_duration: float,
        style_profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        durations = [
            max(0.0, float(seg.get("end", 0.0)) - float(seg.get("start", 0.0)))
            for seg in selected
            if float(seg.get("end", 0.0)) > float(seg.get("start", 0.0))
        ]
        avg_duration = sum(durations) / len(durations) if durations else 0.0
        expected = target_duration or float(style_profile.get("avg_shot_length", 0.0) or 0.0)
        mismatch = abs(avg_duration - expected)
        status = "pass"
        actions: List[Dict[str, Any]] = []
        recommendations: List[Dict[str, Any]] = []
        if target_pacing == "fast" and avg_duration > max(expected + 0.65, 2.85):
            status = "warn"
            actions.append({"action": "tighten_target_duration", "target_segment_duration": round(max(1.15, expected - 0.35), 3)})
            recommendations.append({"type": "pacing", "message": "Tighten segment duration for faster pacing."})
        elif target_pacing == "slow" and durations and avg_duration < max(4.2, expected * 0.8):
            status = "warn"
            actions.append({"action": "relax_target_duration", "target_segment_duration": round(expected + 0.5, 3)})
            recommendations.append({"type": "pacing", "message": "Allow longer holds to better match slow pacing."})
        score = round(_clamp(1.0 - mismatch / max(expected, 1.0)), 4) if expected > 0 else 1.0
        return {
            "status": status,
            "score": score,
            "code": "PACING_MISMATCH" if status != "pass" else "PACING_OK",
            "message": "Plan pacing aligns with the target profile." if status == "pass" else "Plan pacing diverges from target style.",
            "detail": {
                "target_pacing": target_pacing,
                "average_selected_duration": round(avg_duration, 4),
                "target_segment_duration": round(expected, 4),
            },
            "recommendations": recommendations,
            "rewrite_actions": actions,
        }

    def _check_redundancy(
        self,
        selected: Sequence[Dict[str, Any]],
        support: Sequence[Dict[str, Any]],
    ) -> Dict[str, Any]:
        duplicate_primary_indices: List[int] = []
        last_scene_id = None
        support_run = len(support)
        for index, seg in enumerate(selected):
            scene_id = seg.get("scene_id")
            if scene_id and scene_id == last_scene_id:
                duplicate_primary_indices.append(index)
            last_scene_id = scene_id
        status = "pass"
        recommendations: List[Dict[str, Any]] = []
        actions: List[Dict[str, Any]] = []
        if duplicate_primary_indices:
            status = "warn"
            actions.append({"action": "drop_redundant_primary_indices", "indices": duplicate_primary_indices})
            recommendations.append({"type": "redundancy", "message": "Reduce repeated same-scene narrative picks."})
        if support_run >= 3:
            status = "warn"
            recommendations.append({"type": "support_balance", "message": "Limit support-only runs to keep the narrative anchored."})
        penalty = 0.18 * len(duplicate_primary_indices) + (0.12 if support_run >= 3 else 0.0)
        return {
            "status": status,
            "score": round(_clamp(1.0 - penalty), 4),
            "code": "REDUNDANCY_DETECTED" if status != "pass" else "REDUNDANCY_OK",
            "message": "Plan redundancy is acceptable." if status == "pass" else "Repeated scene usage or support runs were detected.",
            "detail": {"duplicate_primary_indices": duplicate_primary_indices, "support_count": len(support)},
            "recommendations": recommendations,
            "rewrite_actions": actions,
        }

    def _check_support_balance(
        self,
        selected: Sequence[Dict[str, Any]],
        support: Sequence[Dict[str, Any]],
        target_pacing: str,
    ) -> Dict[str, Any]:
        primary_count = len(selected)
        support_count = len(support)
        support_ratio = support_count / max(primary_count, 1)
        max_ratio = 0.75 if target_pacing == "fast" else 0.6
        if primary_count == 0 or support_ratio <= max_ratio:
            return {
                "status": "pass",
                "score": 1.0,
                "code": "SUPPORT_BALANCE_OK",
                "message": "Support vs primary balance is acceptable.",
                "detail": {"primary_count": primary_count, "support_count": support_count},
                "recommendations": [],
                "rewrite_actions": [],
            }
        keep_count = max(1, int(primary_count * max_ratio))
        return {
            "status": "warn",
            "score": round(_clamp(1.0 - (support_ratio - max_ratio)), 4),
            "code": "SUPPORT_BALANCE_HEAVY",
            "message": "Support segments outweigh the primary narrative too much.",
            "detail": {"primary_count": primary_count, "support_count": support_count, "support_ratio": round(support_ratio, 4)},
            "recommendations": [{"type": "support_balance", "message": "Trim lower-value support beats to preserve narrative focus."}],
            "rewrite_actions": [{"action": "trim_support_segments", "keep_count": keep_count}],
        }

    def _check_visual_diversity(
        self,
        selected: Sequence[Dict[str, Any]],
        support: Sequence[Dict[str, Any]],
    ) -> Dict[str, Any]:
        adjacent_similar_indices: List[int] = []
        opening_clusters: List[str] = []
        repeated_support_clusters: List[str] = []
        for index, segment in enumerate(selected[:2]):
            cluster = str(segment.get("visual_cluster_id", "unknown"))
            opening_clusters.append(cluster)
            if index > 0 and cluster != "unknown" and cluster == opening_clusters[index - 1]:
                adjacent_similar_indices.append(index)
        for index in range(1, len(selected)):
            current = str(selected[index].get("visual_cluster_id", "unknown"))
            previous = str(selected[index - 1].get("visual_cluster_id", "unknown"))
            if current != "unknown" and current == previous:
                adjacent_similar_indices.append(index)
        support_clusters: Dict[str, int] = {}
        for segment in support:
            cluster = str(segment.get("visual_cluster_id", "unknown"))
            if cluster == "unknown":
                continue
            support_clusters[cluster] = support_clusters.get(cluster, 0) + 1
        repeated_support_clusters = [cluster for cluster, count in support_clusters.items() if count > 1]
        opening_novelty = (
            sum(float(segment.get("novelty_score", 0.0) or 0.0) for segment in selected[:2]) / max(len(selected[:2]), 1)
            if selected
            else 0.0
        )
        if not adjacent_similar_indices and not repeated_support_clusters and opening_novelty >= 0.34:
            return {
                "status": "pass",
                "score": 1.0,
                "code": "VISUAL_DIVERSITY_OK",
                "message": "Visual diversity looks acceptable.",
                "detail": {"opening_novelty": round(opening_novelty, 4), "opening_clusters": opening_clusters},
                "recommendations": [],
                "rewrite_actions": [],
            }
        actions: List[Dict[str, Any]] = []
        if adjacent_similar_indices:
            actions.append({"action": "swap_in_visual_contrast", "indices": adjacent_similar_indices})
        if repeated_support_clusters:
            actions.append({"action": "trim_support_segments", "keep_count": max(1, len(support) - len(repeated_support_clusters))})
        return {
            "status": "warn",
            "score": round(_clamp(0.72 - 0.16 * len(adjacent_similar_indices) - 0.12 * len(repeated_support_clusters) + opening_novelty * 0.2), 4),
            "code": "VISUAL_DIVERSITY_LOW",
            "message": "Visually similar picks reduce diversity.",
            "detail": {
                "adjacent_similar_indices": sorted(set(adjacent_similar_indices)),
                "opening_clusters": opening_clusters,
                "opening_novelty": round(opening_novelty, 4),
                "repeated_support_clusters": repeated_support_clusters,
            },
            "recommendations": [
                {"type": "visual_diversity", "message": "Swap in visually distinct candidates for repetitive beats."}
            ],
            "rewrite_actions": actions,
        }

    def _check_density_suitability(
        self,
        selected: Sequence[Dict[str, Any]],
        target_count: int,
        style_profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        density = max(
            float(style_profile.get("text_density", 0.0) or 0.0),
            float(style_profile.get("ocr_density", 0.0) or 0.0),
        )
        selected_count = len(selected)
        mismatch = abs(selected_count - target_count)
        status = "pass"
        recommendations: List[Dict[str, Any]] = []
        actions: List[Dict[str, Any]] = []
        if density >= 0.5 and selected_count < target_count:
            status = "warn"
            actions.append({"action": "increase_target_density", "target_segment_count": target_count})
            recommendations.append({"type": "density", "message": "Dense styles benefit from more frequent narrative beats."})
        elif density <= 0.15 and target_count > 0 and selected_count > target_count:
            status = "warn"
            actions.append({"action": "reduce_target_density", "target_segment_count": target_count})
            recommendations.append({"type": "density", "message": "Light styles should avoid overly dense segmentation."})
        return {
            "status": status,
            "score": round(_clamp(1.0 - mismatch / max(target_count, 1)), 4) if target_count else 1.0,
            "code": "DENSITY_MISMATCH" if status != "pass" else "DENSITY_OK",
            "message": "Segment density matches style expectations." if status == "pass" else "Segment density mismatches the style profile.",
            "detail": {"selected_count": selected_count, "target_segment_count": target_count, "density": round(density, 4)},
            "recommendations": recommendations,
            "rewrite_actions": actions,
        }

    def _check_text_readability(
        self,
        selected: Sequence[Dict[str, Any]],
        target_duration: float,
        style_profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        text_heavy = max(
            float(style_profile.get("text_density", 0.0) or 0.0),
            float(style_profile.get("ocr_density", 0.0) or 0.0),
        ) >= 0.45
        if not text_heavy:
            return {
                "status": "pass",
                "score": 1.0,
                "code": "READABILITY_OK",
                "message": "Readability holds are acceptable for the current style.",
                "detail": {"text_heavy": False},
                "recommendations": [],
                "rewrite_actions": [],
            }
        short_holds = [
            seg.get("label")
            for seg in selected
            if max(0.0, float(seg.get("end", 0.0)) - float(seg.get("start", 0.0))) < max(1.0, target_duration * 0.75)
        ]
        if not short_holds:
            return {
                "status": "pass",
                "score": 1.0,
                "code": "READABILITY_OK",
                "message": "Readability holds are acceptable for the current style.",
                "detail": {"text_heavy": True, "short_hold_labels": []},
                "recommendations": [],
                "rewrite_actions": [],
            }
        return {
            "status": "warn",
            "score": round(_clamp(1.0 - 0.18 * len(short_holds)), 4),
            "code": "READABILITY_HOLD_SHORT",
            "message": "Text-heavy moments may not hold long enough for readability.",
            "detail": {"text_heavy": True, "short_hold_labels": short_holds},
            "recommendations": [{"type": "readability", "message": "Slightly increase hold length for text-heavy moments."}],
            "rewrite_actions": [{"action": "raise_target_duration_floor", "target_segment_duration": round(max(target_duration, 1.35), 3)}],
        }

    def _check_low_score_overuse(
        self,
        selected: Sequence[Dict[str, Any]],
        support: Sequence[Dict[str, Any]],
        rejected: Sequence[Dict[str, Any]],
    ) -> Dict[str, Any]:
        weak_selected = [
            seg.get("label")
            for seg in list(selected) + list(support)
            if float(seg.get("editorial_score", seg.get("score", 0.0)) or 0.0) < 0.35
            and float(seg.get("hook_score", 0.0) or 0.0) < 0.45
            and float(seg.get("broll_score", 0.0) or 0.0) < 0.8
        ]
        if len(weak_selected) <= 1:
            return {
                "status": "pass",
                "score": 1.0,
                "code": "LOW_SCORE_USAGE_OK",
                "message": "Low-score segment usage is under control.",
                "detail": {"weak_selected_labels": weak_selected, "rejected_count": len(rejected)},
                "recommendations": [],
                "rewrite_actions": [],
            }
        return {
            "status": "warn",
            "score": round(_clamp(1.0 - 0.16 * len(weak_selected)), 4),
            "code": "LOW_SCORE_OVERUSE",
            "message": "The plan leans too heavily on weak segments.",
            "detail": {"weak_selected_labels": weak_selected, "rejected_count": len(rejected)},
            "recommendations": [{"type": "quality", "message": "Trim the weakest narrative/support picks."}],
            "rewrite_actions": [{"action": "drop_low_score_segments", "labels": weak_selected[1:]}],
        }
