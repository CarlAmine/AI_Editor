from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
import json

@dataclass
class SlotReplacement:
    slot_id: int
    clip_id: Optional[str] = None
    source_index: Optional[int] = None
    replacement_text: Optional[str] = None
    source_start: Optional[float] = None
    source_end: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SlotReplacement:
        return cls(
            slot_id=int(data.get("slot_id", 0)),
            clip_id=data.get("clip_id"),
            source_index=data.get("source_index"),
            replacement_text=data.get("replacement_text"),
            source_start=data.get("source_start"),
            source_end=data.get("source_end"),
        )

@dataclass
class TextReplacement:
    slot_id: Optional[int] = None
    old_text: Optional[str] = None
    new_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TextReplacement:
        return cls(
            slot_id=data.get("slot_id"),
            old_text=data.get("old_text"),
            new_text=str(data.get("new_text", "")),
        )

@dataclass
class UserPatchedPlan:
    slot_replacements: List[SlotReplacement] = field(default_factory=list)
    text_replacements: List[TextReplacement] = field(default_factory=list)
    preserve: Dict[str, Any] = field(default_factory=dict)
    user_notes: str = ""
    raw_requirements: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["slot_replacements"] = [r.to_dict() for r in self.slot_replacements]
        d["text_replacements"] = [t.to_dict() for t in self.text_replacements]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> UserPatchedPlan:
        slot_reps = [SlotReplacement.from_dict(r) for r in data.get("slot_replacements") or []]
        text_reps = [TextReplacement.from_dict(t) for t in data.get("text_replacements") or []]
        return cls(
            slot_replacements=slot_reps,
            text_replacements=text_reps,
            preserve=dict(data.get("preserve") or {}),
            user_notes=str(data.get("user_notes", "")),
            raw_requirements=dict(data.get("raw_requirements") or {}),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> UserPatchedPlan:
        return cls.from_dict(json.loads(json_str))
