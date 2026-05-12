"""Modular analysis package for video understanding foundations."""

from .analysis_schema import (
    AnalysisResult,
    AnalysisStatus,
    EffectType,
    MotionCurve,
    MotionEffect,
    MotionEffectManifest,
    OCRSpan,
    Scene,
    Segment,
    StyleProfile,
    TranscriptResult,
    TranscriptSpan,
    VideoMetadata,
)
from .motion_effect_analyzer import MotionEffectAnalyzer
from .segment_builder import SegmentBuilder
from .segment_scorer import SegmentScorer
from .style_profiler import StyleProfiler
from .transcript_analyzer import TranscriptAnalyzer
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
    "OCRAnalyzer",
    "OCRSpan",
    "Scene",
    "SceneAnalyzer",
    "SegmentBuilder",
    "SegmentScorer",
    "Segment",
    "StyleProfile",
    "StyleProfiler",
    "TranscriptAnalyzer",
    "TranscriptResult",
    "TranscriptSpan",
    "VideoMetadata",
    "VisualSignatureAnalyzer",
]
