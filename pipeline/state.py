import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class StageName(str, Enum):
    INGEST = "INGEST"
    FETCH_PRIMARY = "FETCH_PRIMARY"
    ANALYZE_PRIMARY = "ANALYZE_PRIMARY"
    FETCH_SOURCES = "FETCH_SOURCES"
    ALIGN_SOURCES = "ALIGN_SOURCES"
    AUDIO_PLAN = "AUDIO_PLAN"
    RENDER_PLAN = "RENDER_PLAN"
    SHOTSTACK_RENDER = "SHOTSTACK_RENDER"
    POSTPROCESS = "POSTPROCESS"
    PUBLISH = "PUBLISH"
    CLEANUP = "CLEANUP"


class StageStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class StageEntry:
    status: StageStatus = StageStatus.PENDING
    updated_at: str = field(default_factory=utc_now_iso)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class JobState:
    job_id: str
    created_at: str
    input_summary: Dict[str, Any]
    requirements: Dict[str, Any]
    stages: Dict[str, StageEntry]
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)


def default_stages() -> Dict[str, StageEntry]:
    return {s.value: StageEntry() for s in StageName}


def state_file(job_dir: str) -> str:
    return os.path.join(job_dir, "state.json")


def new_state(job_id: str, input_summary: Dict[str, Any], requirements: Dict[str, Any]) -> JobState:
    return JobState(
        job_id=job_id,
        created_at=utc_now_iso(),
        input_summary=input_summary,
        requirements=requirements,
        stages=default_stages(),
    )


def _to_state(data: Dict[str, Any]) -> JobState:
    stages = {}
    for k, v in (data.get("stages") or {}).items():
        stages[k] = StageEntry(
            status=StageStatus(v.get("status", StageStatus.PENDING)),
            updated_at=v.get("updated_at", utc_now_iso()),
            meta=v.get("meta") or {},
        )
    # Backfill missing stages
    for k, entry in default_stages().items():
        stages.setdefault(k, entry)

    return JobState(
        job_id=data["job_id"],
        created_at=data.get("created_at", utc_now_iso()),
        input_summary=data.get("input_summary") or {},
        requirements=data.get("requirements") or {},
        stages=stages,
        warnings=data.get("warnings") or [],
        errors=data.get("errors") or [],
    )


def _as_dict(state: JobState) -> Dict[str, Any]:
    obj = asdict(state)
    # Convert enums
    for k, v in obj["stages"].items():
        v["status"] = str(v["status"])
    return obj


def load_state(job_dir: str) -> Optional[JobState]:
    path = state_file(job_dir)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return _to_state(data)


def save_state(job_dir: str, state: JobState) -> None:
    os.makedirs(job_dir, exist_ok=True)
    path = state_file(job_dir)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_as_dict(state), f, ensure_ascii=False, indent=2)


def update_stage(
    state: JobState,
    stage: StageName,
    status: StageStatus,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    entry = state.stages.get(stage.value) or StageEntry()
    entry.status = status
    entry.updated_at = utc_now_iso()
    if meta:
        entry.meta.update(meta)
    state.stages[stage.value] = entry


def add_warning(state: JobState, code: str, message: str, detail: Any = None) -> None:
    state.warnings.append({"code": code, "message": message, "detail": detail})


def add_error(state: JobState, stage: StageName, code: str, message: str, detail: Any = None) -> None:
    state.errors.append(
        {"stage": stage.value, "code": code, "message": message, "detail": detail}
    )
