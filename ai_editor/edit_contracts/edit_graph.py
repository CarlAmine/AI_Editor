from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
import json

@dataclass
class EditGraphClip:
    slot_id: int
    clip_id: str
    source_index: Optional[int] = None
    video_src: Optional[str] = None
    source_start: float = 0.0
    duration: float = 0.0
    crop: Dict[str, Any] = field(default_factory=dict)
    motion_effects: List[Dict[str, Any]] = field(default_factory=list)
    transition_out: Optional[Dict[str, Any]] = None
    text: Optional[Dict[str, Any]] = None
    style_ops: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EditGraphClip:
        return cls(
            slot_id=int(data.get("slot_id", 0)),
            clip_id=str(data.get("clip_id", "")),
            source_index=data.get("source_index"),
            video_src=data.get("video_src"),
            source_start=float(data.get("source_start", 0.0)),
            duration=float(data.get("duration", 0.0)),
            crop=dict(data.get("crop") or {}),
            motion_effects=list(data.get("motion_effects") or []),
            transition_out=data.get("transition_out"),
            text=data.get("text"),
            style_ops=list(data.get("style_ops") or []),
            metadata=dict(data.get("metadata") or {}),
        )

@dataclass
class ExecutableEditGraph:
    version: str = "edit_graph_v1"
    timeline: List[EditGraphClip] = field(default_factory=list)
    global_style_ops: List[Dict[str, Any]] = field(default_factory=list)
    audio: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    model_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["timeline"] = [c.to_dict() for c in self.timeline]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExecutableEditGraph:
        clips = [EditGraphClip.from_dict(c) for c in data.get("timeline") or []]
        return cls(
            version=str(data.get("version", "edit_graph_v1")),
            timeline=clips,
            global_style_ops=list(data.get("global_style_ops") or []),
            audio=dict(data.get("audio") or {}),
            warnings=list(data.get("warnings") or []),
            model_metadata=dict(data.get("model_metadata") or {}),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> ExecutableEditGraph:
        return cls.from_dict(json.loads(json_str))
