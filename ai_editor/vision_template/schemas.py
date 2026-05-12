from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence

from pydantic import BaseModel, Field

try:  # pragma: no cover - import compatibility
    from pydantic import model_validator
except ImportError:  # pragma: no cover
    model_validator = None

MotionKind = Literal[
    "static",
    "zoom_in",
    "zoom_out",
    "pan_left",
    "pan_right",
    "pan_up",
    "pan_down",
    "unknown",
]
OverlayRegion = Literal["top", "center", "lower_third", "full", "unknown"]
PacingLabel = Literal["slow", "medium", "fast", "variable"]


def _model_dump(instance: BaseModel) -> Dict[str, Any]:
    if hasattr(instance, "model_dump"):
        return instance.model_dump()
    return instance.dict()


class CropSpec(BaseModel):
    x: float = 0.0
    y: float = 0.0
    width: float = 1.0
    height: float = 1.0

    if model_validator:
        @model_validator(mode="after")
        def _clamp(self):
            self.x = min(max(float(self.x), 0.0), 1.0)
            self.y = min(max(float(self.y), 0.0), 1.0)
            self.width = min(max(float(self.width), 1e-6), 1.0)
            self.height = min(max(float(self.height), 1e-6), 1.0)
            if self.x + self.width > 1.0:
                self.x = max(0.0, 1.0 - self.width)
            if self.y + self.height > 1.0:
                self.y = max(0.0, 1.0 - self.height)
            return self


class MotionSpec(BaseModel):
    kind: MotionKind = "unknown"
    confidence: float = 0.0
    keyframes: List[Dict[str, Any]] = Field(default_factory=list)


class OverlaySpec(BaseModel):
    has_overlay: bool = False
    region: OverlayRegion = "unknown"
    start_rel: float = 0.0
    end_rel: float = 0.0
    mask_confidence: float = 0.0

    if model_validator:
        @model_validator(mode="after")
        def _normalize(self):
            self.start_rel = min(max(float(self.start_rel), 0.0), 1.0)
            self.end_rel = min(max(float(self.end_rel), self.start_rel), 1.0)
            self.mask_confidence = min(max(float(self.mask_confidence), 0.0), 1.0)
            return self


class EditSlot(BaseModel):
    slot_id: int
    start: float
    end: float
    duration: float
    boundary_confidence: float = 0.0
    transition_in: str = "cut"
    transition_out: str = "cut"
    motion: MotionSpec = Field(default_factory=MotionSpec)
    crop: CropSpec = Field(default_factory=CropSpec)
    overlay: Optional[OverlaySpec] = None
    style_vector: Optional[List[float]] = None
    visible_objects: List[str] = Field(default_factory=list)
    visible_layers: List[str] = Field(default_factory=list)
    semantic_events: List[Dict[str, Any]] = Field(default_factory=list)
    semantic_metadata: Dict[str, Any] = Field(default_factory=dict)

    if model_validator:
        @model_validator(mode="after")
        def _normalize(self):
            self.start = float(self.start)
            self.end = float(self.end)
            self.duration = float(self.duration)
            if self.duration <= 0 and self.end > self.start:
                self.duration = self.end - self.start
            self.boundary_confidence = min(max(float(self.boundary_confidence), 0.0), 1.0)
            return self


class GlobalStyle(BaseModel):
    avg_slot_duration: float = 0.0
    rhythm: List[float] = Field(default_factory=list)
    pacing_label: PacingLabel = "medium"
    dominant_transition: str = "cut"
    aspect_ratio: Optional[str] = None
    style_embedding: Optional[List[float]] = None


class TrainingSummary(BaseModel):
    epochs: int = 0
    final_loss: Optional[float] = None
    boundary_loss: Optional[float] = None
    self_supervised_loss: Optional[float] = None
    device: str = "cpu"
    model_type: str = "tiny_cnn_gru"
    used_pretrained_backbone: bool = False
    warning_count: int = 0


class EditTemplate(BaseModel):
    version: str = "0.1"
    source_reference: Optional[str] = None
    fps: float
    total_duration: float
    slots: List[EditSlot] = Field(default_factory=list)
    global_style: GlobalStyle = Field(default_factory=GlobalStyle)
    training_summary: Optional[TrainingSummary] = None
    warnings: List[str] = Field(default_factory=list)

    def to_json_file(self, path: str | Path) -> str:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            json.dump(_model_dump(self), handle, ensure_ascii=False, indent=2)
        return str(target)

    @classmethod
    def from_json_file(cls, path: str | Path) -> "EditTemplate":
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if hasattr(cls, "model_validate"):
            return cls.model_validate(payload)
        return cls.parse_obj(payload)


class SlotMappingItem(BaseModel):
    slot_id: int
    clip_id: Optional[str] = None
    clip_path: Optional[str] = None
    clip_url: Optional[str] = None
    source_start: Optional[float] = None
    source_end: Optional[float] = None


class SlotMapping(BaseModel):
    items: List[SlotMappingItem] = Field(default_factory=list)

    def to_json_file(self, path: str | Path) -> str:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            json.dump(_model_dump(self), handle, ensure_ascii=False, indent=2)
        return str(target)

    @classmethod
    def from_json_file(cls, path: str | Path) -> "SlotMapping":
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, list):
            payload = {"items": payload}
        if hasattr(cls, "model_validate"):
            return cls.model_validate(payload)
        return cls.parse_obj(payload)

    def as_slot_dict(self) -> Dict[int, SlotMappingItem]:
        return {int(item.slot_id): item for item in self.items}


def validate_monotonic_slots(template: EditTemplate) -> None:
    previous_end = 0.0
    for index, slot in enumerate(template.slots, start=1):
        if slot.duration <= 0:
            raise ValueError(f"Slot {index} has non-positive duration.")
        if slot.start < previous_end - 1e-6:
            raise ValueError(f"Slot {index} starts before the previous slot ends.")
        if slot.end <= slot.start:
            raise ValueError(f"Slot {index} end must be greater than start.")
        previous_end = slot.end


def validate_slot_mapping(template: EditTemplate, mapping: SlotMapping | Sequence[SlotMappingItem]) -> None:
    slot_items = mapping.items if isinstance(mapping, SlotMapping) else list(mapping)
    seen_slot_ids = set()
    duplicate_slot_ids = []
    for item in slot_items:
        slot_id = int(item.slot_id)
        if slot_id in seen_slot_ids:
            duplicate_slot_ids.append(slot_id)
        seen_slot_ids.add(slot_id)
    if duplicate_slot_ids:
        duplicates = sorted(set(duplicate_slot_ids))
        raise ValueError(f"Duplicate slot mapping entries found for slots: {duplicates}")

    by_id = {int(item.slot_id): item for item in slot_items}
    missing = [slot.slot_id for slot in template.slots if slot.slot_id not in by_id]
    if missing:
        raise ValueError(f"Missing slot mapping entries for slots: {missing}")
    for slot in template.slots:
        item = by_id.get(slot.slot_id)
        if item is None:
            continue
        if not any([item.clip_id, item.clip_path, item.clip_url]):
            raise ValueError(f"Slot {slot.slot_id} mapping must include clip_id, clip_path, or clip_url.")
        if item.source_start is not None and item.source_start < 0:
            raise ValueError(f"Slot {slot.slot_id} source_start must be non-negative.")
        if item.source_end is not None and item.source_end < 0:
            raise ValueError(f"Slot {slot.slot_id} source_end must be non-negative.")
        if (
            item.source_start is not None
            and item.source_end is not None
            and float(item.source_end) <= float(item.source_start)
        ):
            raise ValueError(f"Slot {slot.slot_id} source_end must be greater than source_start.")
