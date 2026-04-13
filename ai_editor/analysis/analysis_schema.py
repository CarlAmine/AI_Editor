from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class AnalysisStatus(str, Enum):
    AVAILABLE = "available"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


@dataclass
class VideoMetadata:
    path: str
    name: str
    fps: float = 0.0
    total_frames: int = 0
    duration_seconds: float = 0.0
    width: int = 0
    height: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Scene:
    scene_id: int
    start_time: float
    end_time: float
    duration: float
    start_frame: int
    end_frame: int

    def to_legacy_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OCRSpan:
    timestamp: float
    frame_number: int
    text: str
    source: str = "easyocr"
    confidence: Optional[float] = None
    position: Optional[str] = None
    bbox: Optional[List[List[float]]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TranscriptSpan:
    start_time: float
    end_time: float
    text: str
    confidence: Optional[float] = None
    source: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Segment:
    start: float
    end: float
    scene_id: Optional[int] = None
    label: str = "segment"
    source: str = "scene_fallback"
    transcript_text: str = ""
    ocr_text: str = ""
    has_transcript: bool = False
    has_ocr: bool = False
    quality_score: float = 0.0
    hook_score: float = 0.0
    broll_score: float = 0.0
    editorial_score: float = 0.0
    novelty_score: float = 0.0
    visual_cluster_id: str = "unknown"
    visual_signature: Dict[str, Any] = field(default_factory=dict)
    reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["start_time"] = self.start
        payload["end_time"] = self.end
        payload["score"] = self.editorial_score
        payload["notes"] = self.reason
        return payload


@dataclass
class StyleProfile:
    avg_shot_length: float = 0.0
    scene_count: int = 0
    pacing_label: str = "unknown"
    text_density: float = 0.0
    ocr_density: float = 0.0
    transition_density: float = 0.0
    hook_window_seconds: float = 0.0
    intro_pacing_label: str = "unknown"
    mid_pacing_label: str = "unknown"
    outro_pacing_label: str = "unknown"
    short_form_likelihood: float = 0.0
    notes: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TranscriptResult:
    status: str = AnalysisStatus.UNAVAILABLE.value
    backend: Optional[str] = None
    reason: Optional[str] = None
    spans: List[TranscriptSpan] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "backend": self.backend,
            "reason": self.reason,
            "spans": [span.to_dict() for span in self.spans],
        }


@dataclass
class AnalysisResult:
    metadata: VideoMetadata
    scenes: List[Scene] = field(default_factory=list)
    ocr_spans: List[OCRSpan] = field(default_factory=list)
    transcript: TranscriptResult = field(default_factory=TranscriptResult)
    segments: List[Segment] = field(default_factory=list)
    pacing: Dict[str, Any] = field(default_factory=dict)
    black_frames: List[Dict[str, Any]] = field(default_factory=list)
    transitions: List[Dict[str, Any]] = field(default_factory=list)
    style_profile: StyleProfile = field(default_factory=StyleProfile)
    analysis_profile: Dict[str, Any] = field(default_factory=dict)

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "video_metadata": self.metadata.to_dict(),
            "scenes": [scene.to_legacy_dict() for scene in self.scenes],
            "ocr_spans": [span.to_dict() for span in self.ocr_spans],
            "transcript": self.transcript.to_dict(),
            "transcript_spans": [span.to_dict() for span in self.transcript.spans],
            "segments": [segment.to_dict() for segment in self.segments],
            "pacing": dict(self.pacing),
            "black_frames": list(self.black_frames),
            "transitions": list(self.transitions),
            "style_profile": self.style_profile.to_dict(),
            "analysis_profile": dict(self.analysis_profile),
        }

    def to_legacy_dict(self) -> Dict[str, Any]:
        keyframes: List[Dict[str, Any]] = []
        grouped: Dict[tuple[float, int], Dict[str, Any]] = {}
        for span in self.ocr_spans:
            key = (round(float(span.timestamp), 6), int(span.frame_number))
            entry = grouped.setdefault(
                key,
                {
                    "timestamp": float(span.timestamp),
                    "frame_number": int(span.frame_number),
                    "brightness": None,
                    "detected_text": "",
                    "easyocr_details": [],
                },
            )
            normalized_text = str(span.text or "").strip()
            if normalized_text and normalized_text not in entry["easyocr_details"]:
                entry["easyocr_details"].append(normalized_text)
        for key in sorted(grouped.keys()):
            entry = grouped[key]
            details = [d for d in entry["easyocr_details"] if d]
            entry["detected_text"] = "; ".join(details) if details else "No text"
            keyframes.append(entry)
        return {
            "scenes": [scene.to_legacy_dict() for scene in self.scenes],
            "pacing": dict(self.pacing),
            "black_frames": list(self.black_frames),
            "transitions": list(self.transitions),
            "keyframes": keyframes,
        }

    def to_dict(self, include_legacy: bool = True) -> Dict[str, Any]:
        payload = self.to_canonical_dict()
        if include_legacy:
            payload.update(self.to_legacy_dict())
        return payload
