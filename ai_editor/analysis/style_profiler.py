from __future__ import annotations

from typing import Dict, List, Sequence

from .analysis_schema import OCRSpan, Scene, Segment, StyleProfile, TranscriptSpan, VideoMetadata


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _label_for_duration(avg_duration: float) -> str:
    if avg_duration <= 0:
        return "unknown"
    if avg_duration < 2.0:
        return "fast"
    if avg_duration < 5.0:
        return "medium"
    return "slow"


def _window_scenes(scenes: Sequence[Scene], start: float, end: float) -> List[Scene]:
    return [
        scene
        for scene in scenes
        if float(scene.end_time) > float(start) and float(scene.start_time) < float(end)
    ]


class StyleProfiler:
    """Build a deterministic reusable style profile from analysis outputs."""

    def profile(
        self,
        metadata: VideoMetadata,
        scenes: List[Scene],
        ocr_spans: List[OCRSpan],
        transcript_spans: List[TranscriptSpan],
        segments: List[Segment],
        pacing: Dict[str, object] | None = None,
        transitions: List[Dict[str, object]] | None = None,
        keyframes: List[Dict[str, object]] | None = None,
    ) -> StyleProfile:
        duration = max(float(metadata.duration_seconds), 1e-6)
        scene_durations = [float(scene.duration) for scene in scenes if float(scene.duration) > 0]
        avg_shot_length = sum(scene_durations) / len(scene_durations) if scene_durations else duration
        pacing_label = str((pacing or {}).get("pacing_category") or _label_for_duration(avg_shot_length))

        scene_count = len(scenes)
        ocr_count = len([span for span in ocr_spans if str(span.text or "").strip()])
        transcript_word_count = sum(len(str(span.text or "").split()) for span in transcript_spans)
        transition_density = round(len(transitions or []) / max(scene_count, 1), 4)
        ocr_density = round(ocr_count / duration, 4)
        text_density = round((transcript_word_count / duration) + (ocr_count / max(duration, 1.0) * 0.5), 4)

        third = duration / 3.0
        intro_pacing_label = _label_for_duration(self._average_duration(_window_scenes(scenes, 0.0, third)))
        mid_pacing_label = _label_for_duration(self._average_duration(_window_scenes(scenes, third, third * 2.0)))
        outro_pacing_label = _label_for_duration(self._average_duration(_window_scenes(scenes, third * 2.0, duration)))

        hook_window_seconds = self._hook_window_seconds(duration, segments)
        short_form_likelihood = self._short_form_likelihood(
            duration=duration,
            avg_shot_length=avg_shot_length,
            ocr_density=ocr_density,
            text_density=text_density,
            hook_window_seconds=hook_window_seconds,
        )

        notes: List[str] = []
        if ocr_density >= 0.15 or text_density >= 0.35:
            notes.append("Text-heavy visual profile.")
        if short_form_likelihood >= 0.7:
            notes.append("High short-form likelihood from pacing and early hooks.")
        if intro_pacing_label == "fast" and outro_pacing_label == "slow":
            notes.append("Front-loaded pacing eases off later in the video.")
        if not notes:
            notes.append("Style profile derived from deterministic scene, text, and segment heuristics.")

        return StyleProfile(
            avg_shot_length=round(avg_shot_length, 4),
            scene_count=scene_count,
            pacing_label=pacing_label,
            text_density=text_density,
            ocr_density=ocr_density,
            transition_density=transition_density,
            hook_window_seconds=round(hook_window_seconds, 4),
            intro_pacing_label=intro_pacing_label,
            mid_pacing_label=mid_pacing_label,
            outro_pacing_label=outro_pacing_label,
            short_form_likelihood=round(short_form_likelihood, 4),
            notes=notes,
            metadata={
                "ocr_span_count": ocr_count,
                "transcript_word_count": transcript_word_count,
                "keyframe_count": len(keyframes or []),
                "segment_count": len(segments),
            },
        )

    def _average_duration(self, scenes: Sequence[Scene]) -> float:
        durations = [float(scene.duration) for scene in scenes if float(scene.duration) > 0]
        if not durations:
            return 0.0
        return sum(durations) / len(durations)

    def _hook_window_seconds(self, duration: float, segments: Sequence[Segment]) -> float:
        if not segments:
            return min(duration, 3.0)
        ordered = sorted(segments, key=lambda segment: (float(segment.start), -float(segment.editorial_score)))
        strong = [
            segment
            for segment in ordered
            if float(segment.start) <= min(duration * 0.35, 20.0)
            and (float(segment.hook_score) >= 0.55 or float(segment.editorial_score) >= 0.6)
        ]
        if strong:
            return max(2.0, min(float(strong[-1].end), min(duration * 0.4, 20.0)))
        first = ordered[0]
        return max(2.0, min(float(first.end), min(duration * 0.25, 10.0)))

    def _short_form_likelihood(
        self,
        duration: float,
        avg_shot_length: float,
        ocr_density: float,
        text_density: float,
        hook_window_seconds: float,
    ) -> float:
        duration_score = _clamp(1.0 - max(duration - 60.0, 0.0) / 180.0)
        pace_score = _clamp(1.0 - min(avg_shot_length / 6.0, 1.0))
        text_score = _clamp(0.6 * min(ocr_density / 0.6, 1.0) + 0.4 * min(text_density / 3.0, 1.0))
        hook_score = _clamp(1.0 - min(hook_window_seconds / 12.0, 1.0))
        return _clamp(0.35 * duration_score + 0.3 * pace_score + 0.2 * text_score + 0.15 * hook_score)
