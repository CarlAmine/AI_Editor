from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


LayerType = Literal[
    "background",
    "foreground_subject",
    "object",
    "overlay",
    "motion_effect",
    "color_effect",
    "unknown",
]
SemanticEventType = Literal[
    "object_appeared",
    "object_disappeared",
    "object_removed",
    "object_inserted",
    "object_replaced",
    "object_masked",
    "object_scale_changed",
    "object_position_changed",
    "object_color_changed",
    "possible_jump_cut",
    "possible_inpainting",
    "overlay_appeared",
    "overlay_disappeared",
]


def _model_dump(instance: BaseModel) -> Dict[str, Any]:
    if hasattr(instance, "model_dump"):
        return instance.model_dump()
    return instance.dict()


class ObjectFrameState(BaseModel):
    timestamp: float
    bbox: List[float]
    confidence: float
    visible: bool
    occlusion_score: float = 0.0
    mask_path: Optional[str] = None


class TrackedObject(BaseModel):
    object_id: str
    label: str
    confidence: float
    first_seen: float
    last_seen: float
    track: List[ObjectFrameState] = Field(default_factory=list)
    mask_available: bool = False
    stable_identity_score: float = 0.0
    attributes: Dict[str, Any] = Field(default_factory=dict)


class VideoLayer(BaseModel):
    layer_id: str
    layer_type: LayerType
    label: Optional[str] = None
    object_id: Optional[str] = None
    start: float
    end: float
    region: Optional[str] = None
    editable: bool = True
    confidence: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ActionEvent(BaseModel):
    subject_id: Optional[str] = None
    verb: str
    object_id: Optional[str] = None
    start: float
    end: float
    confidence: float = 0.0


class SemanticEditEvent(BaseModel):
    event_type: SemanticEventType
    object_id: Optional[str] = None
    layer_id: Optional[str] = None
    start: float
    end: float
    confidence: float = 0.0
    evidence: Dict[str, Any] = Field(default_factory=dict)


class SemanticVideoGraph(BaseModel):
    video_path: Optional[str] = None
    sampled_fps: float = 0.0
    duration: float = 0.0
    objects: List[TrackedObject] = Field(default_factory=list)
    layers: List[VideoLayer] = Field(default_factory=list)
    actions: List[ActionEvent] = Field(default_factory=list)
    edit_events: List[SemanticEditEvent] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    def to_json_file(self, path: str | Path) -> str:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            json.dump(_model_dump(self), handle, ensure_ascii=False, indent=2)
        return str(target)

    @classmethod
    def from_json_file(cls, path: str | Path) -> "SemanticVideoGraph":
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if hasattr(cls, "model_validate"):
            return cls.model_validate(payload)
        return cls.parse_obj(payload)


class SemanticEditVerification(BaseModel):
    passed: bool
    score: float
    target_object_label: Optional[str] = None
    target_object_ids: List[str] = Field(default_factory=list)
    changed_objects: List[str] = Field(default_factory=list)
    preserved_objects: List[str] = Field(default_factory=list)
    unintended_changes: List[str] = Field(default_factory=list)
    evidence: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)

    def to_json_file(self, path: str | Path) -> str:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            json.dump(_model_dump(self), handle, ensure_ascii=False, indent=2)
        return str(target)

    @classmethod
    def from_json_file(cls, path: str | Path) -> "SemanticEditVerification":
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if hasattr(cls, "model_validate"):
            return cls.model_validate(payload)
        return cls.parse_obj(payload)
