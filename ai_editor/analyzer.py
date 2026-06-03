from __future__ import annotations

import os
import warnings
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Dict, Optional, Tuple

try:
    import cv2
except Exception:  # pragma: no cover - dependency availability varies by environment
    class _CV2Stub:
        CAP_PROP_FPS = 5
        CAP_PROP_FRAME_COUNT = 7
        CAP_PROP_FRAME_WIDTH = 3
        CAP_PROP_FRAME_HEIGHT = 4

        @staticmethod
        def VideoCapture(_path: str):
            raise ImportError("cv2 is required for video analysis")

    cv2 = _CV2Stub()  # type: ignore

from ai_editor.analysis import (
    AnalysisResult,
    AnalysisStatus,
    OCRAnalyzer,
    MotionEffectAnalyzer,
    SceneAnalyzer,
    SegmentBuilder,
    SegmentScorer,
    StyleProfiler,
    TranscriptResult,
    VideoMetadata,
    VisualSignatureAnalyzer,
)

log = logging.getLogger(__name__)


@dataclass
class AnalysisContext:
    metadata: VideoMetadata
    result: AnalysisResult
    keyframes: list[dict]


class TranscriptAnalyzer:
    """
    Incremental abstraction for transcript backends.

    When no backend such as Whisper or faster-whisper is installed, the
    analyzer returns an empty transcript payload instead of failing the
    pipeline.
    """

    def __init__(self, preferred_backend: Optional[str] = None) -> None:
        self.preferred_backend = preferred_backend or "auto"

    def analyze(self, video_path: str) -> TranscriptResult:
        del video_path
        try:
            import faster_whisper  # type: ignore  # pragma: no cover

            _ = faster_whisper
            return TranscriptResult(
                status=AnalysisStatus.EMPTY.value,
                backend="faster-whisper",
                reason="Transcript backend detected but transcription is not wired in yet.",
                spans=[],
            )
        except Exception:
            pass

        try:
            import whisper  # type: ignore  # pragma: no cover

            _ = whisper
            return TranscriptResult(
                status=AnalysisStatus.EMPTY.value,
                backend="whisper",
                reason="Transcript backend detected but transcription is not wired in yet.",
                spans=[],
            )
        except Exception:
            pass

        return TranscriptResult(
            status=AnalysisStatus.UNAVAILABLE.value,
            backend=None,
            reason="No transcript backend installed. Install whisper or faster-whisper to enable transcripts.",
            spans=[],
        )


class VideoEditAnalyzer:
    """
    Backward-compatible analyzer entrypoint.

    The public methods mirror the previous monolithic analyzer, but the actual
    work now lives in focused sub-analyzers under ``ai_editor.analysis``.
    """

    def __init__(
        self,
        path: str,
        scene_analyzer: Optional[SceneAnalyzer] = None,
        ocr_analyzer: Optional[OCRAnalyzer] = None,
        transcript_analyzer: Optional[TranscriptAnalyzer] = None,
        segment_builder: Optional[SegmentBuilder] = None,
        segment_scorer: Optional[SegmentScorer] = None,
        style_profiler: Optional[StyleProfiler] = None,
        visual_signature_analyzer: Optional[VisualSignatureAnalyzer] = None,
    ):
        self.video_path = path
        self.cap = cv2.VideoCapture(path)
        self.metadata = self._build_metadata(path)
        self.fps = self.metadata.fps
        self.total_frames = self.metadata.total_frames
        self.duration = self.metadata.duration_seconds
        self.video_name = self.metadata.name
        if scene_analyzer is None:
            if SceneAnalyzer is None:
                raise ImportError("Scene analysis dependencies are not installed.")
            scene_analyzer = SceneAnalyzer()
        if ocr_analyzer is None:
            if OCRAnalyzer is None:
                raise ImportError("OCR analysis dependencies are not installed.")
            ocr_analyzer = OCRAnalyzer()
        self.scene_analyzer = scene_analyzer
        self.ocr_analyzer = ocr_analyzer
        self.transcript_analyzer = transcript_analyzer or TranscriptAnalyzer()
        self.segment_builder = segment_builder or SegmentBuilder()
        self.segment_scorer = segment_scorer or SegmentScorer()
        self.style_profiler = style_profiler or StyleProfiler()
        self.visual_signature_analyzer = visual_signature_analyzer or VisualSignatureAnalyzer()
        self._motion_effect_analyzer = MotionEffectAnalyzer()
        self.analysis = AnalysisResult(metadata=self.metadata)
        self.results: Dict = self.analysis.to_dict()
        self._keyframes: list[dict] = []

    def _build_metadata(self, path: str) -> VideoMetadata:
        fps = float(self.cap.get(cv2.CAP_PROP_FPS) or 0.0)
        total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        duration = (total_frames / fps) if fps > 0 else 0.0
        return VideoMetadata(
            path=path,
            name=os.path.basename(path),
            fps=fps,
            total_frames=total_frames,
            duration_seconds=duration,
            width=width,
            height=height,
        )

    def _refresh_results(self) -> Dict:
        self.results = self.analysis.to_dict()
        if self._keyframes:
            self.results["keyframes"] = list(self._keyframes)
        return self.results

    def close(self):
        if self.cap.isOpened():
            self.cap.release()

    def detect_scenes(self, threshold: float = 30.0):
        output = self.scene_analyzer.detect_scenes(self.video_path, threshold=threshold)
        self.analysis.scenes = output
        self._refresh_results()
        return [scene.to_legacy_dict() for scene in output]

    def analyze_pacing(self):
        self.analysis.pacing = self.scene_analyzer.analyze_pacing(self.analysis.scenes, self.duration)
        self._refresh_results()

    def detect_black_frames(self, threshold: float = 15):
        self.analysis.black_frames = self.scene_analyzer.detect_black_frames(self.video_path, self.fps, threshold)
        self._refresh_results()

    def detect_transitions(self):
        try:
            self.analysis.transitions = self.scene_analyzer.detect_transitions(
                self.analysis.scenes,
                self.video_path,
            )
        except TypeError:
            self.analysis.transitions = self.scene_analyzer.detect_transitions(self.analysis.scenes)
        self._refresh_results()

    def extract_and_analyze_keyframes(self, num_frames: int = 12):
        output = self.ocr_analyzer.analyze(self.video_path, self.metadata, num_frames=num_frames)
        self.analysis.ocr_spans = output.ocr_spans
        self._keyframes = output.keyframes
        self._refresh_results()

    def analyze_transcript(self):
        self.analysis.transcript = self.transcript_analyzer.analyze(self.video_path)
        self._refresh_results()

    def build_segments(self):
        build_result = self.segment_builder.build(
            metadata=self.metadata,
            scenes=self.analysis.scenes,
            transcript=self.analysis.transcript,
            ocr_spans=self.analysis.ocr_spans,
        )
        self.analysis.segments = self.segment_scorer.score(
            self.visual_signature_analyzer.annotate_segments(build_result.segments, self._keyframes),
            metadata=self.metadata,
            pacing=self.analysis.pacing,
            transitions=self.analysis.transitions,
        )
        self.analysis.analysis_profile["segment_strategy"] = build_result.strategy
        self._refresh_results()

    def build_style_profile(self):
        self.analysis.style_profile = self.style_profiler.profile(
            metadata=self.metadata,
            scenes=self.analysis.scenes,
            ocr_spans=self.analysis.ocr_spans,
            transcript_spans=self.analysis.transcript.spans,
            segments=self.analysis.segments,
            pacing=self.analysis.pacing,
            transitions=self.analysis.transitions,
            keyframes=self._keyframes,
        )
        self._refresh_results()

    def analyze_motion_effects(self) -> None:
        """
        Analyze editor-applied global motion effects against the already-detected
        scene list and store the manifest on the analysis result.
        """
        if not self.analysis.scenes:
            log.warning("analyze_motion_effects called before scenes were available")
            return
        if not self.video_path:
            return
        manifest = self._motion_effect_analyzer.analyze(self.video_path, self.analysis.scenes)
        self.analysis.motion_effects = manifest
        log.info(
            "Motion effect analysis complete: %d effects across %d shots",
            len(manifest.effects),
            len(self.analysis.scenes),
        )
        self._refresh_results()

    def run_full_analysis(self) -> AnalysisContext:
        scene_output = self.scene_analyzer.analyze(self.video_path, self.metadata)
        self.analysis.scenes = scene_output.scenes
        self.analysis.pacing = scene_output.pacing
        self.analysis.black_frames = scene_output.black_frames
        self.analysis.transitions = scene_output.transitions

        try:
            self.analyze_motion_effects()
        except Exception as exc:
            log.warning("Motion effect analysis failed but full analysis continued: %s", exc)

        ocr_output = self.ocr_analyzer.analyze(self.video_path, self.metadata)
        self.analysis.ocr_spans = ocr_output.ocr_spans
        self._keyframes = ocr_output.keyframes

        self.analysis.transcript = self.transcript_analyzer.analyze(self.video_path)
        self.build_segments()
        self.build_style_profile()
        self.analysis.analysis_profile = {
            "scene_analysis": "enabled",
            "ocr_analysis": "enabled",
            "transcript_analysis": self.analysis.transcript.status,
        }
        self.analysis.analysis_profile["segment_count"] = len(self.analysis.segments)
        self.analysis.analysis_profile["style_profile_ready"] = True
        self._refresh_results()
        return AnalysisContext(metadata=self.metadata, result=self.analysis, keyframes=self._keyframes)


def _generate_summary(metadata: VideoMetadata, result: AnalysisResult, legacy: Dict) -> str:
    summary_lines = []
    summary_lines.append(" VIDEO ANALYSIS SUMMARY")
    summary_lines.append("=" * 40)
    summary_lines.append(f"File: {metadata.name}")
    summary_lines.append(f"Duration: {timedelta(seconds=metadata.duration_seconds)}")
    summary_lines.append(f"FPS: {metadata.fps:.2f}")

    pacing = legacy.get("pacing") or {}
    if pacing:
        summary_lines.append(f"\nPACING: {pacing['pacing_category']}")
        summary_lines.append(f"   • Total Shots: {pacing['total_shots']}")
        summary_lines.append(f"   • Avg Shot Duration: {pacing['avg_shot_duration']:.2f}s")
        summary_lines.append(f"   • Cuts per Minute: {pacing['shots_per_minute']:.1f}")

    transitions = legacy.get("transitions") or []
    if transitions:
        counts = defaultdict(int)
        for transition in transitions:
            counts[str(transition.get("type"))] += 1
        most_common = max(counts, key=counts.get) if counts else "None"
        summary_lines.append("\nEDITING STYLE:")
        summary_lines.append(f"   • Dominant Transition: {most_common}")
        summary_lines.append(f"   • Transition Counts: {dict(counts)}")

    black_frames = legacy.get("black_frames") or []
    if black_frames:
        summary_lines.append(f"\nBLACK SEQUENCES: {len(black_frames)} detected")
        for bf in black_frames[:3]:
            summary_lines.append(
                f"   • At {bf['start_time']:.1f}s ({bf['duration']:.1f}s): {bf['type']}"
            )

    summary_lines.append("\nDETECTED TEXT CONTENT:")
    text_found = False
    for keyframe in legacy.get("keyframes") or []:
        detected_text = keyframe.get("detected_text")
        if detected_text and detected_text != "No text":
            summary_lines.append(f"   • @ {keyframe['timestamp']:.1f}s: {detected_text}")
            text_found = True
    if not text_found:
        summary_lines.append("   • No significant on-screen text detected.")

    transcript = result.transcript
    if transcript.spans:
        summary_lines.append(f"\nTRANSCRIPT: {len(transcript.spans)} spans available")
    elif transcript.reason:
        summary_lines.append(f"\nTRANSCRIPT: {transcript.status} ({transcript.reason})")

    return "\n".join(summary_lines)


def analyze_video_content_with_results(video_path: str) -> Tuple[str, Dict]:
    """
    Run the full modular analysis and return both the human-readable summary and
    the structured results dictionary.
    """
    warnings.filterwarnings("ignore")

    try:
        analyzer = VideoEditAnalyzer(video_path)
        context = analyzer.run_full_analysis()
        payload = context.result.to_dict(include_legacy=True)
        payload["keyframes"] = context.keyframes
        summary = _generate_summary(context.metadata, context.result, payload)
        analyzer.close()
        return summary, payload
    except Exception as exc:
        error_msg = f"Error analyzing video: {str(exc)}"
        return error_msg, {}


def analyze_video_content(video_path: str) -> str:
    """Backwards-compatible wrapper that returns only the textual summary."""
    summary, _ = analyze_video_content_with_results(video_path)
    return summary
