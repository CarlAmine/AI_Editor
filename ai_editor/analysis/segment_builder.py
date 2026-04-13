from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

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
