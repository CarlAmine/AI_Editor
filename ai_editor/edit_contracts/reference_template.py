from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
import json

@dataclass
class ReferenceSlot:
    slot_id: int
    start: float
    end: float
    duration: float
    role: str
    scene_id: Optional[int] = None
    text_ref: Optional[Dict[str, Any]] = None
    transition_out: Optional[Dict[str, Any]] = None
    motion: Optional[Dict[str, Any]] = None
    style_tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ReferenceSlot:
        return cls(
            slot_id=int(data.get("slot_id", 0)),
            start=float(data.get("start", 0.0)),
            end=float(data.get("end", 0.0)),
            duration=float(data.get("duration", 0.0)),
            role=str(data.get("role", "main")),
            scene_id=data.get("scene_id"),
            text_ref=data.get("text_ref"),
            transition_out=data.get("transition_out"),
            motion=data.get("motion"),
            style_tags=list(data.get("style_tags") or []),
        )

@dataclass
class ReferenceEditTemplate:
    template_id: str
    source_video_path: str
    duration: float
    fps: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    slots: List[ReferenceSlot] = field(default_factory=list)
    transitions: List[Dict[str, Any]] = field(default_factory=list)
    overlays: List[Dict[str, Any]] = field(default_factory=list)
    texts: List[Dict[str, Any]] = field(default_factory=list)
    motion_effects: List[Dict[str, Any]] = field(default_factory=list)
    style_profile: Dict[str, Any] = field(default_factory=dict)
    audio_profile: Dict[str, Any] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["slots"] = [slot.to_dict() for slot in self.slots]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ReferenceEditTemplate:
        slots_data = data.get("slots") or []
        slots = [ReferenceSlot.from_dict(s) for s in slots_data]
        return cls(
            template_id=str(data.get("template_id", "")),
            source_video_path=str(data.get("source_video_path", "")),
            duration=float(data.get("duration", 0.0)),
            fps=data.get("fps"),
            width=data.get("width"),
            height=data.get("height"),
            slots=slots,
            transitions=list(data.get("transitions") or []),
            overlays=list(data.get("overlays") or []),
            texts=list(data.get("texts") or []),
            motion_effects=list(data.get("motion_effects") or []),
            style_profile=dict(data.get("style_profile") or {}),
            audio_profile=dict(data.get("audio_profile") or {}),
            constraints=dict(data.get("constraints") or {}),
            warnings=list(data.get("warnings") or []),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> ReferenceEditTemplate:
        return cls.from_dict(json.loads(json_str))
