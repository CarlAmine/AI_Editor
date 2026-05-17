from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List

from .analysis_schema import OCRSpan, Scene, Segment, TranscriptResult, TranscriptSpan, VideoMetadata

MIN_SEGMENT_DURATION = 0.75


@dataclass
class SegmentBuildResult:
    segments: List[Segment]
    strategy: str


def _normalize_text(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def _join_unique_texts(values: Iterable[str]) -> str:
    seen = set()
    ordered: List[str] = []
    for value in values:
        normalized = _normalize_text(value)
        key = normalized.lower()
        if normalized and key not in seen:
            ordered.append(normalized)
            seen.add(key)
    return " ".join(ordered)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _clip_range(start: float, end: float, scene: Scene) -> tuple[float, float]:
    clipped_start = max(float(start), float(scene.start_time))
    clipped_end = min(float(end), float(scene.end_time))
    return clipped_start, clipped_end


def _segment_from_scene(scene: Scene, ocr_spans: List[OCRSpan], reason: str, source: str) -> Segment:
    scene_ocr = [
        span.text
        for span in ocr_spans
        if float(scene.start_time) <= float(span.timestamp) < float(scene.end_time) + 1e-6
    ]
    ocr_text = _join_unique_texts(scene_ocr)
    return Segment(
        start=float(scene.start_time),
        end=float(scene.end_time),
        scene_id=scene.scene_id,
        label=f"scene_{scene.scene_id}",
        source=source,
        transcript_text="",
        ocr_text=ocr_text,
        has_transcript=False,
        has_ocr=bool(ocr_text),
        reason=reason,
        metadata={"duration": max(0.0, float(scene.duration))},
    )


class SegmentBuilder:
    """Builds analysis segments from scenes, transcript spans, and OCR spans."""

    def build(
        self,
        metadata: VideoMetadata,
        scenes: List[Scene],
        transcript: TranscriptResult,
        ocr_spans: List[OCRSpan],
    ) -> SegmentBuildResult:
        if transcript.spans:
            transcript_segments = self._build_from_transcript(scenes, transcript.spans, ocr_spans)
            if transcript_segments:
                return SegmentBuildResult(segments=transcript_segments, strategy="transcript_scene_aligned")
        if scenes:
            return SegmentBuildResult(
                segments=[_segment_from_scene(scene, ocr_spans, "Scene-based fallback.", "scene_fallback") for scene in scenes],
                strategy="scene_fallback",
            )
        fallback_end = max(float(metadata.duration_seconds), 0.0)
        fallback_ocr = _join_unique_texts(span.text for span in ocr_spans)
        fallback_segments = []
        if fallback_end > 0:
            fallback_segments.append(
                Segment(
                    start=0.0,
                    end=fallback_end,
                    scene_id=None,
                    label="full_video",
                    source="coarse_fallback",
                    transcript_text="",
                    ocr_text=fallback_ocr,
                    has_transcript=False,
                    has_ocr=bool(fallback_ocr),
                    reason="Fallback segment because scenes/transcript were sparse.",
                    metadata={"duration": fallback_end},
                )
            )
        return SegmentBuildResult(segments=fallback_segments, strategy="coarse_fallback")

    def _build_from_transcript(
        self,
        scenes: List[Scene],
        transcript_spans: List[TranscriptSpan],
        ocr_spans: List[OCRSpan],
    ) -> List[Segment]:
        if not scenes:
            return self._build_without_scenes(transcript_spans, ocr_spans)

        segments: List[Segment] = []
        for scene in scenes:
            scene_transcript = [
                span
                for span in transcript_spans
                if float(span.end_time) > float(scene.start_time) and float(span.start_time) < float(scene.end_time)
            ]
            if not scene_transcript:
                segments.append(_segment_from_scene(scene, ocr_spans, "No transcript in scene; kept scene fallback.", "scene_fallback"))
                continue

            for idx, span in enumerate(scene_transcript, start=1):
                start, end = _clip_range(float(span.start_time), float(span.end_time), scene)
                if end - start < MIN_SEGMENT_DURATION:
                    continue
                segment_ocr = [
                    ocr.text
                    for ocr in ocr_spans
                    if start <= float(ocr.timestamp) < end + 1e-6
                ]
                transcript_text = _normalize_text(span.text)
                ocr_text = _join_unique_texts(segment_ocr)
                segments.append(
                    Segment(
                        start=start,
                        end=end,
                        scene_id=scene.scene_id,
                        label=f"scene_{scene.scene_id}_transcript_{idx}",
                        source="transcript_scene_aligned",
                        transcript_text=transcript_text,
                        ocr_text=ocr_text,
                        has_transcript=bool(transcript_text),
                        has_ocr=bool(ocr_text),
                        reason="Transcript span aligned to scene boundary.",
                        metadata={
                            "duration": max(0.0, end - start),
                            "transcript_span_start": float(span.start_time),
                            "transcript_span_end": float(span.end_time),
                        },
                    )
                )

            if not any(segment.scene_id == scene.scene_id for segment in segments):
                segments.append(_segment_from_scene(scene, ocr_spans, "Transcript spans were too short after clipping; kept scene fallback.", "scene_fallback"))

        return self._merge_adjacent_segments(segments)

    def _build_without_scenes(self, transcript_spans: List[TranscriptSpan], ocr_spans: List[OCRSpan]) -> List[Segment]:
        segments: List[Segment] = []
        for idx, span in enumerate(transcript_spans, start=1):
            start = float(span.start_time)
            end = float(span.end_time)
            if end - start < MIN_SEGMENT_DURATION:
                continue
            segment_ocr = [
                ocr.text
                for ocr in ocr_spans
                if start <= float(ocr.timestamp) < end + 1e-6
            ]
            transcript_text = _normalize_text(span.text)
            ocr_text = _join_unique_texts(segment_ocr)
            segments.append(
                Segment(
                    start=start,
                    end=end,
                    scene_id=None,
                    label=f"transcript_{idx}",
                    source="transcript_only",
                    transcript_text=transcript_text,
                    ocr_text=ocr_text,
                    has_transcript=bool(transcript_text),
                    has_ocr=bool(ocr_text),
                    reason="Transcript span used without scene boundaries.",
                    metadata={"duration": max(0.0, end - start)},
                )
            )
        return self._merge_adjacent_segments(segments)

    def _merge_adjacent_segments(self, segments: List[Segment]) -> List[Segment]:
        if not segments:
            return []
        ordered = sorted(segments, key=lambda item: (float(item.start), float(item.end)))
        merged: List[Segment] = [ordered[0]]
        for seg in ordered[1:]:
            prev = merged[-1]
            same_scene = prev.scene_id == seg.scene_id
            contiguous = abs(float(seg.start) - float(prev.end)) < 0.05
            both_sparse = not prev.has_transcript and not seg.has_transcript
            if same_scene and contiguous and both_sparse:
                prev.end = max(float(prev.end), float(seg.end))
                prev.ocr_text = _join_unique_texts([prev.ocr_text, seg.ocr_text])
                prev.has_ocr = bool(prev.ocr_text)
                prev.metadata["duration"] = max(0.0, float(prev.end) - float(prev.start))
                continue
            merged.append(seg)
        return merged


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
            hardish = sum(
                1
                for item in transitions
                if str(item.get("type", "")).lower() in {"hard cut", "quick fade"}
            )
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
            visual_density = _clamp(
                0.5 * ocr_density + (0.25 if segment.has_ocr else 0.0) + transition_bonus
            )
            transcript_presence = 1.0 if segment.has_transcript else 0.2
            ocr_presence = 1.0 if segment.has_ocr else 0.1
            novelty_score = _clamp(float(segment.novelty_score or 0.0))
            edge_density = _clamp(float(visual_signature.get("edge_density", 0.0) or 0.0) * 4.0)
            contrast = _clamp(float(visual_signature.get("contrast", 0.0) or 0.0) / 96.0)
            visual_interest = _clamp(0.5 * novelty_score + 0.3 * edge_density + 0.2 * contrast)

            quality_score = _clamp(
                0.45 * duration_fit
                + 0.25 * transcript_presence
                + 0.2 * ocr_presence
                + 0.1 * early_bonus
            )
            hook_score = _clamp(
                0.4 * early_bonus
                + 0.22 * ocr_density
                + 0.18 * brevity_fit
                + 0.1 * transcript_density
                + 0.1 * novelty_score
            )
            broll_score = _clamp(
                0.38 * visual_density
                + 0.24 * visual_interest
                + 0.18 * duration_fit
                + 0.12 * (1.0 - transcript_density)
                + 0.08 * (0.4 if segment.has_ocr else 0.0)
            )

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
