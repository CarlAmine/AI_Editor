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
    # span_end marks the last timestamp where this text was observed before it
    # changed. Set by the change-detection post-processing step in OCRAnalyzer.
    span_end: Optional[float] = None

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
class MotionCurve:
    """
    A time-series of per-frame transform parameters extracted from a video
    segment. All values are normalised to the frame dimensions so curves are
    resolution-independent and can be applied to clips of any size.

    - dx_norm, dy_norm: translation as fraction of frame width/height
    - scale: uniform scale factor (1.0 = no zoom, 1.1 = 10% zoom in)
    - rotation_deg: rotation in degrees (small values typical for shake)
    - residual: mean homography fit error; high values indicate non-rigid
      effects (glitch, distortion, dissolve smear)
    """

    dx_norm: List[float] = field(default_factory=list)
    dy_norm: List[float] = field(default_factory=list)
    scale: List[float] = field(default_factory=list)
    rotation_deg: List[float] = field(default_factory=list)
    residual: List[float] = field(default_factory=list)
    frame_indices: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EffectType(str, Enum):
    SHAKE = "shake"
    ZOOM_IN = "zoom_in"
    ZOOM_OUT = "zoom_out"
    PAN = "pan"
    FREEZE = "freeze"
    SPEED_RAMP = "speed_ramp"
    BLUR_SMEAR = "blur_smear"
    GLITCH = "glitch"
    STATIC = "static"


class TransitionType(str, Enum):
    HARD_CUT = "hard_cut"
    FADE_TO_BLACK = "fade_to_black"
    FADE_FROM_BLACK = "fade_from_black"
    FADE_TO_WHITE = "fade_to_white"
    FADE_FROM_WHITE = "fade_from_white"
    CROSS_DISSOLVE = "cross_dissolve"
    ZOOM_PUNCH = "zoom_punch"
    WHIP_PAN = "whip_pan"
    FLASH_CUT = "flash_cut"
    UNKNOWN = "unknown"


@dataclass
class TransitionEvent:
    """
    A detected transition between two consecutive shots.
    Stored in MotionEffectManifest.transitions_detected.
    """

    boundary_frame_index: int
    outgoing_shot_index: int
    incoming_shot_index: int
    transition_type: TransitionType
    duration_frames: int
    duration_sec: float
    intensity: float
    luminance_curve: List[float] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["transition_type"] = self.transition_type.value
        return payload


@dataclass
class MotionEffect:
    """
    A single detected applied effect event tied to a specific shot and a
    specific temporal position within that shot.

    onset_frac and offset_frac are fractional positions within the shot
    (0.0 = shot start, 1.0 = shot end). Using fractions rather than absolute
    timestamps means the effect scales correctly when applied to a replacement
    clip of different duration.
    """

    shot_index: int
    effect_type: EffectType
    onset_frac: float
    offset_frac: float
    intensity: float
    curve: MotionCurve = field(default_factory=MotionCurve)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["effect_type"] = self.effect_type.value
        return payload


@dataclass
class MotionEffectManifest:
    """
    Complete motion effect layer for an entire reference video.
    One manifest per reference video. Stored as motion_effects.json artifact.
    """

    video_path: str
    fps: float
    total_frames: int
    effects: List[MotionEffect] = field(default_factory=list)
    transitions_detected: List[TransitionEvent] = field(default_factory=list)
    rhythm_pattern: List[float] = field(default_factory=list)
    global_motion_budget: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "video_path": self.video_path,
            "fps": self.fps,
            "total_frames": self.total_frames,
            "effects": [effect.to_dict() for effect in self.effects],
            "transitions_detected": [transition.to_dict() for transition in self.transitions_detected],
            "rhythm_pattern": self.rhythm_pattern,
            "global_motion_budget": self.global_motion_budget,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MotionEffectManifest":
        effects: List[MotionEffect] = []
        for effect_data in data.get("effects", []):
            curve_data = effect_data.get("curve", {})
            curve = MotionCurve(
                dx_norm=curve_data.get("dx_norm", []),
                dy_norm=curve_data.get("dy_norm", []),
                scale=curve_data.get("scale", []),
                rotation_deg=curve_data.get("rotation_deg", []),
                residual=curve_data.get("residual", []),
                frame_indices=curve_data.get("frame_indices", []),
            )
            effects.append(
                MotionEffect(
                    shot_index=int(effect_data.get("shot_index", 0)),
                    effect_type=EffectType(effect_data.get("effect_type", "static")),
                    onset_frac=float(effect_data.get("onset_frac", 0.0)),
                    offset_frac=float(effect_data.get("offset_frac", 1.0)),
                    intensity=float(effect_data.get("intensity", 0.0)),
                    curve=curve,
                    metadata=dict(effect_data.get("metadata") or {}),
                )
            )
        transitions_detected: List[TransitionEvent] = []
        for transition_data in data.get("transitions_detected", []):
            transitions_detected.append(
                TransitionEvent(
                    boundary_frame_index=int(transition_data.get("boundary_frame_index", 0)),
                    outgoing_shot_index=int(transition_data.get("outgoing_shot_index", 0)),
                    incoming_shot_index=int(transition_data.get("incoming_shot_index", 0)),
                    transition_type=TransitionType(transition_data.get("transition_type", "hard_cut")),
                    duration_frames=int(transition_data.get("duration_frames", 1)),
                    duration_sec=float(transition_data.get("duration_sec", 0.0)),
                    intensity=float(transition_data.get("intensity", 0.0)),
                    luminance_curve=list(transition_data.get("luminance_curve", [])),
                    metadata=dict(transition_data.get("metadata") or {}),
                )
            )
        return cls(
            video_path=data.get("video_path", ""),
            fps=float(data.get("fps", 0.0)),
            total_frames=int(data.get("total_frames", 0)),
            effects=effects,
            transitions_detected=transitions_detected,
            rhythm_pattern=list(data.get("rhythm_pattern", [])),
            global_motion_budget=float(data.get("global_motion_budget", 0.0)),
        )


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
    motion_effects: Optional[MotionEffectManifest] = None
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
            "motion_effects": self.motion_effects.to_dict() if self.motion_effects else None,
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
