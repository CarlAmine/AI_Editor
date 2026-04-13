from __future__ import annotations

from typing import Dict, List

from .analysis_schema import Segment, VideoMetadata


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


class SegmentScorer:
    """Deterministic heuristic scorer for analysis segments."""

    def score(
        self,
        segments: List[Segment],
        metadata: VideoMetadata,
        pacing: Dict[str, float] | Dict[str, object] | None = None,
        transitions: List[Dict[str, object]] | None = None,
    ) -> List[Segment]:
        total_duration = max(float(metadata.duration_seconds), 1e-6)
        total_segments = max(len(segments), 1)
        pace_label = str((pacing or {}).get("pacing_category", "")).lower()
        transition_bonus = 0.0
        if transitions:
            hardish = sum(1 for item in transitions if str(item.get("type", "")).lower() in {"hard cut", "quick fade"})
            transition_bonus = _clamp(hardish / max(len(transitions), 1), 0.0, 1.0) * 0.1

        for index, segment in enumerate(sorted(segments, key=lambda item: float(item.start))):
            duration = max(float(segment.end) - float(segment.start), 0.0)
            relative_position = float(segment.start) / total_duration if total_duration > 0 else 0.0
            early_bonus = _clamp(1.0 - (relative_position * 1.6))
            transcript_words = len(str(segment.transcript_text or "").split())
            ocr_words = len(str(segment.ocr_text or "").split())
            visual_signature = dict(segment.visual_signature or {})
            transcript_density = _clamp(transcript_words / 14.0)
            ocr_density = _clamp(ocr_words / 8.0)
            duration_fit = 1.0 - min(abs(duration - 4.0) / 6.0, 1.0)
            brevity_fit = 1.0 - min(abs(duration - 3.0) / 8.0, 1.0)
            visual_density = _clamp(0.5 * ocr_density + (0.25 if segment.has_ocr else 0.0) + transition_bonus)
            transcript_presence = 1.0 if segment.has_transcript else 0.2
            ocr_presence = 1.0 if segment.has_ocr else 0.1
            novelty_score = _clamp(float(segment.novelty_score or 0.0))
            edge_density = _clamp(float(visual_signature.get("edge_density", 0.0) or 0.0) * 4.0)
            contrast = _clamp(float(visual_signature.get("contrast", 0.0) or 0.0) / 96.0)
            visual_interest = _clamp(0.5 * novelty_score + 0.3 * edge_density + 0.2 * contrast)

            quality_score = _clamp(0.45 * duration_fit + 0.25 * transcript_presence + 0.2 * ocr_presence + 0.1 * early_bonus)
            hook_score = _clamp(0.4 * early_bonus + 0.22 * ocr_density + 0.18 * brevity_fit + 0.1 * transcript_density + 0.1 * novelty_score)
            broll_score = _clamp(0.38 * visual_density + 0.24 * visual_interest + 0.18 * duration_fit + 0.12 * (1.0 - transcript_density) + 0.08 * (0.4 if segment.has_ocr else 0.0))

            editorial_base = 0.37 * quality_score + 0.29 * hook_score + 0.24 * broll_score + 0.1 * novelty_score
            if pace_label.startswith("fast"):
                editorial_base += 0.05 * brevity_fit
            elif pace_label.startswith("slow"):
                editorial_base += 0.05 * duration_fit
            editorial_base += 0.03 * (1.0 - (index / total_segments))
            segment.quality_score = round(_clamp(quality_score), 4)
            segment.hook_score = round(_clamp(hook_score), 4)
            segment.broll_score = round(_clamp(broll_score), 4)
            segment.editorial_score = round(_clamp(editorial_base), 4)
            segment.novelty_score = round(novelty_score, 4)
            segment.metadata.setdefault("duration", duration)
            segment.metadata["transcript_word_count"] = transcript_words
            segment.metadata["ocr_word_count"] = ocr_words
            segment.metadata["relative_position"] = round(relative_position, 4)
            segment.metadata["visual_cluster_id"] = segment.visual_cluster_id
            segment.metadata["visual_interest"] = round(visual_interest, 4)
        return segments
