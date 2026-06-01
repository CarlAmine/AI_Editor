from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
import json

@dataclass
class RenderCompileResult:
    render_spec: Dict[str, Any]
    canonical_timeline: List[Dict[str, Any]]
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RenderCompileResult:
        return cls(
            render_spec=dict(data.get("render_spec") or {}),
            canonical_timeline=list(data.get("canonical_timeline") or []),
            warnings=list(data.get("warnings") or []),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> RenderCompileResult:
        return cls.from_dict(json.loads(json_str))
