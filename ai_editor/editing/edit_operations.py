from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional


@dataclass
class TimeWindowTarget:
    start: Optional[float] = None
    end: Optional[float] = None
    label: str = "global"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EditOperation:
    operation: str
    target: Optional[str] = None
    value: Optional[str] = None
    intensity: float = 1.0
    scope: str = "global"
    time_window: Optional[TimeWindowTarget] = None
    source_target: Optional[str] = None
    segment_target: Optional[str] = None
    section_label: Optional[str] = None
    position: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        if self.time_window is not None:
            payload["time_window"] = self.time_window.to_dict()
        return payload
