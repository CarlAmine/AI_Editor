from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
import json

@dataclass
class SourceClipInventory:
    clip_id: str
    source_index: int
    path: str
    duration: float
    fps: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    candidate_segments: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SourceClipInventory:
        return cls(
            clip_id=str(data.get("clip_id", "")),
            source_index=int(data.get("source_index", 0)),
            path=str(data.get("path", "")),
            duration=float(data.get("duration", 0.0)),
            fps=data.get("fps"),
            width=data.get("width"),
            height=data.get("height"),
            candidate_segments=list(data.get("candidate_segments") or []),
            metadata=dict(data.get("metadata") or {}),
        )

@dataclass
class SourceInventory:
    clips: List[SourceClipInventory] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["clips"] = [c.to_dict() for c in self.clips]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SourceInventory:
        clips = [SourceClipInventory.from_dict(c) for c in data.get("clips") or []]
        return cls(
            clips=clips,
            warnings=list(data.get("warnings") or []),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> SourceInventory:
        return cls.from_dict(json.loads(json_str))
