from __future__ import annotations

from typing import Any, Dict, List, Optional


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


class SegmentRanker:
    """Rank analysis segments into narrative and support roles."""

    def rank(
        self,
        segments: List[Dict[str, Any]],
        style_profile: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        style_profile = style_profile or {}
        ranked_narrative: List[Dict[str, Any]] = []
        ranked_support: List[Dict[str, Any]] = []
        rejected: List[Dict[str, Any]] = []
        seen_ranges = set()
        short_form = _clamp(float(style_profile.get("short_form_likelihood", 0.0) or 0.0))
        text_density = _clamp(float(style_profile.get("text_density", 0.0) or 0.0))
        ocr_density = _clamp(float(style_profile.get("ocr_density", 0.0) or 0.0))

        for segment in segments:
            start = round(float(segment.get("start", 0.0)), 2)
            end = round(float(segment.get("end", start)), 2)
            if end <= start:
                continue
            key = (start, end, segment.get("scene_id"))
            if key in seen_ranges:
                continue
            seen_ranges.add(key)

            editorial = float(segment.get("editorial_score", segment.get("score", 0.0)) or 0.0)
            hook = float(segment.get("hook_score", 0.0) or 0.0)
            broll = float(segment.get("broll_score", 0.0) or 0.0)
            novelty = float(segment.get("novelty_score", 0.0) or 0.0)
            has_transcript = bool(segment.get("has_transcript"))
            has_ocr = bool(segment.get("has_ocr"))
            duration = max(0.0, end - start)
            text_signal = 1.0 if has_transcript else 0.15
            ocr_signal = 1.0 if has_ocr else 0.0
            duration_bonus = 0.15 if 1.2 <= duration <= 6.5 else (0.08 if duration <= 8.0 else 0.0)

            narrative_score = _clamp(
                0.55 * editorial
                + 0.3 * hook
                + 0.08 * text_signal
                + 0.03 * ocr_signal
                + duration_bonus
                + 0.04 * short_form * hook
                + 0.06 * novelty
            )
            support_score = _clamp(
                0.5 * broll
                + 0.18 * editorial
                + 0.16 * ocr_signal
                + 0.08 * (1.0 if not has_transcript else 0.2)
                + 0.05 * max(text_density, ocr_density) * max(broll, ocr_signal)
                + 0.08 * novelty
            )

            enriched = dict(segment)
            enriched["narrative_rank_score"] = round(narrative_score, 4)
            enriched["support_rank_score"] = round(support_score, 4)
            enriched["planner_signals"] = {
                "editorial_score": round(editorial, 4),
                "hook_score": round(hook, 4),
                "broll_score": round(broll, 4),
                "novelty_score": round(novelty, 4),
                "duration": round(duration, 3),
                "short_form_likelihood": round(short_form, 4),
                "text_density": round(text_density, 4),
                "ocr_density": round(ocr_density, 4),
                "visual_cluster_id": segment.get("visual_cluster_id"),
            }

            if editorial < 0.2 and hook < 0.2 and broll < 0.2:
                enriched["rejection_reason"] = "low_score"
                rejected.append(enriched)
                continue
            if narrative_score < 0.24 and support_score < 0.24:
                enriched["rejection_reason"] = "below_rank_threshold"
                rejected.append(enriched)
                continue

            if support_score > narrative_score + 0.08 and broll >= editorial:
                enriched["planner_role"] = "support_broll"
                ranked_support.append(enriched)
            else:
                enriched["planner_role"] = "primary_narrative"
                ranked_narrative.append(enriched)

        ranked_narrative.sort(
            key=lambda segment: (
                -float(segment.get("narrative_rank_score", 0.0)),
                float(segment.get("start", 0.0)),
            )
        )
        ranked_support.sort(
            key=lambda segment: (
                -float(segment.get("support_rank_score", 0.0)),
                -float(segment.get("novelty_score", 0.0)),
                float(segment.get("start", 0.0)),
            )
        )
        rejected.sort(
            key=lambda segment: (
                float(segment.get("start", 0.0)),
                float(segment.get("end", 0.0)),
            )
        )
        return {
            "narrative": ranked_narrative,
            "support": ranked_support,
            "rejected": rejected,
        }
