import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Artifact:
    key: str
    type: str
    path_or_url: str
    mime: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)


class ArtifactRegistry:
    def __init__(self, items: Optional[Dict[str, Artifact]] = None):
        self.items: Dict[str, Artifact] = items or {}

    def register_file(self, key: str, path: str, meta: Optional[Dict[str, Any]] = None, mime: str = "") -> Artifact:
        art = Artifact(key=key, type="file", path_or_url=path, mime=mime, meta=meta or {})
        self.items[key] = art
        return art

    def register_url(self, key: str, url: str, meta: Optional[Dict[str, Any]] = None, mime: str = "") -> Artifact:
        art = Artifact(key=key, type="url", path_or_url=url, mime=mime, meta=meta or {})
        self.items[key] = art
        return art

    def get(self, key: str) -> Optional[Artifact]:
        return self.items.get(key)

    def exists(self, key: str) -> bool:
        return key in self.items

    def as_dict(self) -> Dict[str, Any]:
        return {k: asdict(v) for k, v in self.items.items()}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArtifactRegistry":
        items: Dict[str, Artifact] = {}
        for k, v in data.items():
            items[k] = Artifact(
                key=v["key"],
                type=v["type"],
                path_or_url=v["path_or_url"],
                mime=v.get("mime", ""),
                meta=v.get("meta") or {},
                created_at=v.get("created_at", utc_now_iso()),
            )
        return cls(items)

    def save(self, job_dir: str) -> None:
        with open(os.path.join(job_dir, "artifacts.json"), "w", encoding="utf-8") as f:
            json.dump(self.as_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, job_dir: str) -> "ArtifactRegistry":
        path = os.path.join(job_dir, "artifacts.json")
        if not os.path.exists(path):
            return cls()
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
