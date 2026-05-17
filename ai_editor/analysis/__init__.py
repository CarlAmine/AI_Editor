"""Modular analysis package for video understanding foundations."""

from .analysis_schema import (
    AnalysisResult,
    AnalysisStatus,
    EffectType,
    MotionCurve,
    MotionEffect,
    MotionEffectManifest,
    TransitionEvent,
    TransitionType,
    OCRSpan,
    Scene,
    Segment,
    StyleProfile,
    TranscriptResult,
    TranscriptSpan,
    VideoMetadata,
)
from .motion_effect_analyzer import MotionEffectAnalyzer
from .segment_builder import SegmentBuilder, SegmentScorer
from .style_profiler import StyleProfiler
from .transition_analyzer import TransitionAnalyzer
from .visual_signature import VisualSignatureAnalyzer

try:
    from .ocr_analyzer import OCRAnalyzer
except Exception:  # pragma: no cover - optional runtime dependency
    OCRAnalyzer = None  # type: ignore

try:
    from .scene_analyzer import SceneAnalyzer
except Exception:  # pragma: no cover - optional runtime dependency
    SceneAnalyzer = None  # type: ignore

__all__ = [
    "AnalysisResult",
    "AnalysisStatus",
    "EffectType",
    "MotionCurve",
    "MotionEffect",
    "MotionEffectAnalyzer",
    "MotionEffectManifest",
    "TransitionAnalyzer",
    "TransitionEvent",
    "TransitionType",
    "OCRAnalyzer",
    "OCRSpan",
    "Scene",
    "SceneAnalyzer",
    "SegmentBuilder",
    "SegmentScorer",
    "Segment",
    "StyleProfile",
    "StyleProfiler",
    "TranscriptResult",
    "TranscriptSpan",
    "VideoMetadata",
    "VisualSignatureAnalyzer",
]
