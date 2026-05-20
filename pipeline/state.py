from __future__ import annotations

import json
import os
import re
import hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from ai_editor.generation_modes import is_vision_mode as _is_generation_vision_mode


class StageName(str, Enum):
    PROVIDER_READINESS = "PROVIDER_READINESS"
    CONTROLLER_DECISION = "CONTROLLER_DECISION"
    RUN_ANALYSIS = "RUN_ANALYSIS"
    GENERATE_PLAN = "GENERATE_PLAN"
    REVISE_PLAN = "REVISE_PLAN"
    VALIDATE_PLAN = "VALIDATE_PLAN"
    RENDER_PREVIEW = "RENDER_PREVIEW"
    RENDER_FINAL = "RENDER_FINAL"
    REQUEST_USER_INPUT = "REQUEST_USER_INPUT"
    ABORT_JOB = "ABORT_JOB"
    FINISH = "FINISH"
    INGEST = "INGEST"
    FETCH_PRIMARY = "FETCH_PRIMARY"
    ANALYZE_PRIMARY = "ANALYZE_PRIMARY"
    FETCH_SOURCES = "FETCH_SOURCES"
    ALIGN_SOURCES = "ALIGN_SOURCES"
    AUDIO_PLAN = "AUDIO_PLAN"
    VISION_TEMPLATE_TRAIN = "VISION_TEMPLATE_TRAIN"
    VISION_TEMPLATE_DECODE = "VISION_TEMPLATE_DECODE"
    VISION_TEMPLATE_TRANSFER = "VISION_TEMPLATE_TRANSFER"
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


class JobStatus(str, Enum):
    RUNNING = "running"
    WAITING_USER_INPUT = "waiting_user_input"
    SUCCEEDED = "succeeded"
    ABORTED = "aborted"
    FAILED = "failed"


class ControllerStatus(str, Enum):
    INITIALIZING = "initializing"
    ANALYZING = "analyzing"
    PLANNING = "planning"
    VISION_TEMPLATE_TRAINING = "vision_template_training"
    VISION_TEMPLATE_TRANSFERRING = "vision_template_transferring"
    REVISING = "revising"
    VALIDATING = "validating"
    RENDERING = "rendering"
    AWAITING_USER_INPUT = "awaiting_user_input"
    BLOCKED_BY_UNAPPLIED_EDITS = "blocked_by_unapplied_edits"
    REVISION_LIMIT_EXHAUSTED = "revision_limit_exhausted"
    FAILED = "failed"
    ABORTED = "aborted"
    FINISHED = "finished"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class StageEntry:
    status: StageStatus = StageStatus.PENDING
    updated_at: str = field(default_factory=utc_now_iso)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DecisionTraceEntry:
    step_index: int
    chosen_action: str
    confidence: float
    rationale: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=utc_now_iso)
    source: str = "model"
    error: Optional[str] = None
    overridden: bool = False


@dataclass
class JobState:
    job_id: str
    created_at: str
    updated_at: str
    input_summary: Dict[str, Any]
    request_payload: Dict[str, Any]
    requirements: Dict[str, Any]
    user_goal: str = ""
    status: JobStatus = JobStatus.RUNNING
    controller_status: ControllerStatus = ControllerStatus.INITIALIZING
    controller_status_detail: str = ""
    terminal_status: Optional[str] = None
    failure_reason: Optional[str] = None
    failure_code: Optional[str] = None
    failure_detail: Any = None
    waiting_for_user_input: bool = False
    requested_user_input: Dict[str, Any] = field(default_factory=dict)
    provider_status: Dict[str, Any] = field(default_factory=dict)
    source_status: Dict[str, Any] = field(default_factory=dict)
    analysis_available: bool = False
    transcript_available: bool = False
    analysis_summary: str = ""
    analysis: Dict[str, Any] = field(default_factory=dict)
    style_profile_summary: Dict[str, Any] = field(default_factory=dict)
    segment_summary: Dict[str, Any] = field(default_factory=dict)
    current_plan: Dict[str, Any] = field(default_factory=dict)
    plan_summary: Dict[str, Any] = field(default_factory=dict)
    plan_validation: Dict[str, Any] = field(default_factory=dict)
    plan_validation_score: Optional[float] = None
    plan_needs_validation: bool = False
    overlay_plan: Dict[str, Any] = field(default_factory=dict)
    audio_plan: Dict[str, Any] = field(default_factory=dict)
    render_spec: Dict[str, Any] = field(default_factory=dict)
    render_summary: Dict[str, Any] = field(default_factory=dict)
    motion_effects_path: Optional[str] = None
    revision_attempts: int = 0
    render_attempts: int = 0
    stalled_revision_count: int = 0
    last_revision_fingerprint: str = ""
    latest_user_feedback: str = ""
    applied_edit_requests: List[str] = field(default_factory=list)
    decision_trace: List[DecisionTraceEntry] = field(default_factory=list)
    decision_history: List[Dict[str, Any]] = field(default_factory=list)
    last_decision: Dict[str, Any] = field(default_factory=dict)
    invalid_decision_count: int = 0
    low_confidence_decision_count: int = 0
    final_response: Dict[str, Any] = field(default_factory=dict)
    work_dir: str = ""
    youtube_uploaded: bool = False
    stages: Dict[str, StageEntry] = field(default_factory=dict)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)

    def set_motion_effects_path(self, path: str) -> None:
        self.motion_effects_path = path
        touch(self)

    def is_vision_mode(self) -> bool:
        generation_mode = str(self.requirements.get("generation_mode", "") or "").strip().lower()
        return _is_generation_vision_mode(generation_mode)


def default_stages() -> Dict[str, StageEntry]:
    return {stage.value: StageEntry() for stage in StageName}


def state_file(job_dir: str) -> str:
    return os.path.join(job_dir, "state.json")


def _extract_latest_feedback(requirements: Dict[str, Any]) -> str:
    for key in ("edit_requests", "user_requests"):
        values = requirements.get(key) or []
        if isinstance(values, list):
            for item in reversed(values):
                text = str(item or "").strip()
                if text:
                    return text
    return ""


def _collect_request_items(requirements: Dict[str, Any], *keys: str) -> List[str]:
    items: List[str] = []
    for key in keys:
        values = requirements.get(key) or []
        if not isinstance(values, list):
            continue
        for item in values:
            text = str(item or "").strip()
            if text:
                items.append(text)
    return _dedupe_preserve_order(items)


def extract_edit_requests(requirements: Dict[str, Any]) -> List[str]:
    """Return normalized user edit requests in stable order."""

    return _collect_request_items(requirements, "edit_requests")


def new_state(job_id: str, input_summary: Dict[str, Any], requirements: Dict[str, Any]) -> JobState:
    now = utc_now_iso()
    return JobState(
        job_id=job_id,
        created_at=now,
        updated_at=now,
        input_summary=input_summary,
        request_payload={},
        requirements=requirements,
        user_goal=str(requirements.get("prompt", "") or ""),
        latest_user_feedback=_extract_latest_feedback(requirements),
        work_dir="",
        stages=default_stages(),
    )


def touch(state: JobState) -> None:
    state.updated_at = utc_now_iso()


def summarize_style_profile(analysis: Dict[str, Any]) -> Dict[str, Any]:
    style = analysis.get("style_profile") or {}
    return {
        "pacing_label": style.get("pacing_label"),
        "intro_pacing_label": style.get("intro_pacing_label"),
        "avg_shot_length": _round_optional(style.get("avg_shot_length")),
        "short_form_likelihood": _round_optional(style.get("short_form_likelihood")),
        "text_density": _round_optional(style.get("text_density")),
        "ocr_density": _round_optional(style.get("ocr_density")),
        "scene_count": style.get("scene_count"),
    }


def summarize_segments(analysis: Dict[str, Any], limit: int = 5) -> Dict[str, Any]:
    segments = list(analysis.get("segments") or [])
    ranked = sorted(
        segments,
        key=lambda segment: (
            -float(segment.get("editorial_score", segment.get("score", 0.0)) or 0.0),
            -float(segment.get("hook_score", 0.0) or 0.0),
            -float(segment.get("broll_score", 0.0) or 0.0),
            float(segment.get("start", 0.0) or 0.0),
        ),
    )
    return {
        "segment_count": len(segments),
        "top_candidate_segments": [
            {
                "label": segment.get("label"),
                "start": _round_optional(segment.get("start")),
                "end": _round_optional(segment.get("end")),
                "editorial_score": _round_optional(segment.get("editorial_score", segment.get("score"))),
                "hook_score": _round_optional(segment.get("hook_score")),
                "broll_score": _round_optional(segment.get("broll_score")),
                "visual_cluster_id": segment.get("visual_cluster_id"),
            }
            for segment in ranked[:limit]
        ],
    }


def summarize_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    selected = list(plan.get("selected_segments") or [])
    support = list(plan.get("support_segments") or [])
    debug = plan.get("planning_debug") or {}
    return {
        "planning_strategy": plan.get("planning_strategy"),
        "target_pacing": plan.get("target_pacing"),
        "target_segment_duration": _round_optional(plan.get("target_segment_duration")),
        "target_segment_count": plan.get("target_segment_count"),
        "selected_count": len(selected),
        "support_count": len(support),
        "selected_segment_ids": [segment.get("label") for segment in selected[:6]],
        "support_segment_ids": [segment.get("label") for segment in support[:4]],
        "edit_directive_count": len(plan.get("edit_directives") or []),
        "rewrite_applied": bool(debug.get("rewrite_applied")),
    }


def summarize_plan_patch(plan: Dict[str, Any]) -> Dict[str, Any]:
    patch = plan.get("plan_patch") or {}
    applied_operations = list(patch.get("applied_operations") or [])
    deferred_operations = list(patch.get("deferred_operations") or [])
    return {
        "patch_strategy": patch.get("patch_strategy"),
        "operation_count": int(patch.get("operation_count", len(applied_operations)) or 0),
        "applied_operation_count": len(applied_operations),
        "deferred_operation_count": len(deferred_operations),
        "applied_request_count": len(patch.get("applied_requests") or []),
        "edit_patch_ran": bool((plan.get("planning_debug") or {}).get("edit_patch_ran")),
    }


def build_plan_change_fingerprint(plan: Dict[str, Any]) -> str:
    if not plan:
        return ""

    def _segment_signature(segment: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "label": segment.get("label"),
            "scene_id": segment.get("scene_id"),
            "start": _round_optional(segment.get("start")),
            "end": _round_optional(segment.get("end")),
            "text": str(segment.get("text", "") or "").strip(),
            "video_src": str(
                segment.get("video_src")
                or segment.get("videoSrc")
                or ""
            ).strip(),
            "trim": _round_optional(segment.get("trim")),
        }

    overlay_entries = plan.get("overlay_plan") or []
    if isinstance(overlay_entries, dict):
        overlay_entries = overlay_entries.get("overlays") or []

    fingerprint_payload = {
        "plan_summary": summarize_plan(plan),
        "plan_patch_summary": summarize_plan_patch(plan),
        "selected_segments": [
            _segment_signature(segment)
            for segment in list(plan.get("selected_segments") or [])
        ],
        "support_segments": [
            _segment_signature(segment)
            for segment in list(plan.get("support_segments") or [])
        ],
        "edit_directives": list(plan.get("edit_directives") or []),
        "overlay_plan": [
            {
                "timestamp": _round_optional(item.get("timestamp")),
                "duration": _round_optional(item.get("duration")),
                "text": str(item.get("text", "") or "").strip(),
                "position": item.get("position"),
            }
            for item in list(overlay_entries or [])
        ],
        "rewrite_actions_applied": list(
            ((plan.get("planning_debug") or {}).get("rewrite_actions_applied") or [])
        ),
    }
    payload_text = json.dumps(
        fingerprint_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha1(payload_text.encode("utf-8")).hexdigest()


def pending_edit_requests(state: JobState) -> List[str]:
    applied = set(state.applied_edit_requests or [])
    return [item for item in extract_edit_requests(state.requirements) if item not in applied]


def build_decision_state_snapshot(state: JobState) -> Dict[str, Any]:
    validation = state.plan_validation or {}
    validation_warnings = [
        warning.get("code") or warning.get("message")
        for warning in list(validation.get("warnings") or [])[:4]
    ]
    edit_requests = extract_edit_requests(state.requirements)
    pending_requests = pending_edit_requests(state)
    return {
        "job_id": state.job_id,
        "user_goal": state.user_goal or state.requirements.get("prompt", ""),
        "source_status": state.source_status,
        "analysis_available": state.analysis_available,
        "transcript_available": state.transcript_available,
        "analysis_summary": state.analysis_summary[:700],
        "style_profile_summary": state.style_profile_summary,
        "segment_summary": state.segment_summary,
        "current_plan_present": bool(state.current_plan),
        "plan_summary": state.plan_summary,
        "plan_validation_score": state.plan_validation_score,
        "plan_validation_warnings": validation_warnings,
        "plan_needs_validation": state.plan_needs_validation,
        "revision_attempts": state.revision_attempts,
        "render_attempts": state.render_attempts,
        "stalled_revision_count": state.stalled_revision_count,
        "latest_user_feedback": state.latest_user_feedback,
        "latest_edit_request": edit_requests[-1] if edit_requests else "",
        "pending_edit_request_count": len(pending_requests),
        "pending_edit_requests_preview": pending_requests[:3],
        "applied_edit_request_count": len(state.applied_edit_requests),
        "plan_patch_summary": summarize_plan_patch(state.current_plan),
        "requested_user_input": state.requested_user_input,
        "status": state.status.value,
        "controller_status": state.controller_status.value,
        "controller_status_category": controller_status_category(state.controller_status),
        "controller_status_detail": state.controller_status_detail,
        "terminal_status": state.terminal_status,
        "failure_reason": state.failure_reason,
        "failure_code": state.failure_code,
        "invalid_decision_count": state.invalid_decision_count,
        "low_confidence_decision_count": state.low_confidence_decision_count,
        "decision_trace_count": len(state.decision_trace),
        "provider_status": state.provider_status,
        "warnings_count": len(state.warnings),
        "errors_count": len(state.errors),
        "render_summary": state.render_summary,
    }


def apply_analysis(state: JobState, analysis: Dict[str, Any], summary: str) -> None:
    transcript = analysis.get("transcript") or {}
    state.analysis_available = bool(analysis)
    state.analysis = analysis
    state.analysis_summary = str(summary or "").strip()
    state.transcript_available = bool(transcript.get("spans"))
    state.style_profile_summary = summarize_style_profile(analysis)
    state.segment_summary = summarize_segments(analysis)
    touch(state)


def apply_plan(
    state: JobState,
    plan: Dict[str, Any],
    *,
    overlay_plan: Optional[Dict[str, Any]] = None,
    audio_plan: Optional[Dict[str, Any]] = None,
    render_spec: Optional[Dict[str, Any]] = None,
    needs_validation: bool = True,
) -> None:
    state.current_plan = plan or {}
    state.plan_summary = summarize_plan(state.current_plan)
    if overlay_plan is not None:
        state.overlay_plan = overlay_plan
    if audio_plan is not None:
        state.audio_plan = audio_plan
    if render_spec is not None:
        state.render_spec = render_spec
    state.plan_needs_validation = needs_validation
    if needs_validation:
        state.plan_validation = {}
        state.plan_validation_score = None
    elif plan.get("plan_validation"):
        apply_plan_validation(state, plan.get("plan_validation") or {})
    touch(state)


def apply_plan_validation(state: JobState, validation: Dict[str, Any]) -> None:
    state.plan_validation = validation or {}
    state.plan_validation_score = _coerce_optional_float(validation.get("validation_score"))
    state.plan_needs_validation = False
    if state.current_plan:
        updated = dict(state.current_plan)
        updated["plan_validation"] = state.plan_validation
        state.current_plan = updated
        state.plan_summary = summarize_plan(updated)
    touch(state)


def clear_plan_validation(state: JobState) -> None:
    state.plan_validation = {}
    state.plan_validation_score = None
    state.plan_needs_validation = True
    if state.current_plan:
        updated = dict(state.current_plan)
        updated.pop("plan_validation", None)
        state.current_plan = updated
    touch(state)


def set_source_status(state: JobState, status: Dict[str, Any]) -> None:
    state.source_status = status or {}
    touch(state)


def set_provider_status(state: JobState, status: Dict[str, Any]) -> None:
    state.provider_status = status or {}
    touch(state)


def set_latest_user_feedback(state: JobState, feedback: str) -> None:
    state.latest_user_feedback = str(feedback or "").strip()
    touch(state)


def set_controller_status(
    state: JobState,
    status: ControllerStatus,
    *,
    detail: str = "",
) -> None:
    state.controller_status = status
    state.controller_status_detail = str(detail or "").strip()
    touch(state)


def mark_edit_requests_applied(state: JobState, requests: List[str]) -> None:
    if not requests:
        return
    applied = _dedupe_preserve_order([*(state.applied_edit_requests or []), *requests])
    state.applied_edit_requests = applied
    touch(state)


def set_render_summary(state: JobState, summary: Dict[str, Any], final_response: Optional[Dict[str, Any]] = None) -> None:
    state.render_summary = summary or {}
    if final_response is not None:
        state.final_response = final_response
    touch(state)


def set_requested_user_input(state: JobState, request: Dict[str, Any]) -> None:
    state.waiting_for_user_input = True
    state.requested_user_input = request or {}
    state.status = JobStatus.WAITING_USER_INPUT
    state.terminal_status = JobStatus.WAITING_USER_INPUT.value
    set_controller_status(
        state,
        _controller_status_for_user_input_reason((request or {}).get("reason")),
        detail=str((request or {}).get("question") or ""),
    )
    touch(state)


def clear_requested_user_input(state: JobState) -> None:
    state.waiting_for_user_input = False
    state.requested_user_input = {}
    if state.status == JobStatus.WAITING_USER_INPUT:
        state.status = JobStatus.RUNNING
        state.terminal_status = None
        if state.controller_status in {
            ControllerStatus.AWAITING_USER_INPUT,
            ControllerStatus.BLOCKED_BY_UNAPPLIED_EDITS,
            ControllerStatus.REVISION_LIMIT_EXHAUSTED,
        }:
            set_controller_status(state, ControllerStatus.INITIALIZING)
    touch(state)


def mark_terminal(
    state: JobState,
    status: JobStatus,
    *,
    reason: Optional[str] = None,
    code: Optional[str] = None,
    detail: Any = None,
    final_response: Optional[Dict[str, Any]] = None,
) -> None:
    state.status = status
    state.terminal_status = status.value
    state.failure_reason = reason
    state.failure_code = code
    state.failure_detail = detail
    state.waiting_for_user_input = status == JobStatus.WAITING_USER_INPUT
    if status == JobStatus.SUCCEEDED:
        state.failure_reason = None
        state.failure_code = None
        state.failure_detail = None
        set_controller_status(state, ControllerStatus.FINISHED, detail=reason or "")
    elif status == JobStatus.ABORTED:
        set_controller_status(state, ControllerStatus.ABORTED, detail=reason or "")
    elif status == JobStatus.FAILED:
        set_controller_status(state, ControllerStatus.FAILED, detail=reason or "")
    elif status == JobStatus.WAITING_USER_INPUT:
        set_controller_status(state, ControllerStatus.AWAITING_USER_INPUT, detail=reason or "")
    if final_response is not None:
        state.final_response = final_response
    touch(state)


def is_terminal(state: JobState) -> bool:
    return state.status in {
        JobStatus.WAITING_USER_INPUT,
        JobStatus.SUCCEEDED,
        JobStatus.ABORTED,
        JobStatus.FAILED,
    }


def record_decision(
    state: JobState,
    *,
    next_action: str,
    confidence: float,
    rationale: str,
    parameters: Optional[Dict[str, Any]] = None,
    source: str = "model",
    error: Optional[str] = None,
    overridden: bool = False,
) -> None:
    step_index = len(state.decision_trace) + 1
    trace_entry = DecisionTraceEntry(
        step_index=step_index,
        timestamp=utc_now_iso(),
        chosen_action=next_action,
        confidence=round(max(0.0, min(1.0, float(confidence))), 4),
        rationale=str(rationale or "").strip(),
        parameters=parameters or {},
        source=source,
        error=error,
        overridden=overridden,
    )
    entry = {
        "step_index": trace_entry.step_index,
        "timestamp": trace_entry.timestamp,
        "chosen_action": trace_entry.chosen_action,
        "next_action": next_action,
        "confidence": trace_entry.confidence,
        "rationale": trace_entry.rationale,
        "parameters": trace_entry.parameters,
        "source": trace_entry.source,
        "error": trace_entry.error,
        "overridden": trace_entry.overridden,
    }
    state.decision_trace.append(trace_entry)
    state.last_decision = entry
    state.decision_history.append(entry)
    touch(state)


def _to_state(data: Dict[str, Any]) -> JobState:
    stages: Dict[str, StageEntry] = {}
    for key, value in (data.get("stages") or {}).items():
        raw_status = value.get("status", StageStatus.PENDING.value)
        try:
            stage_status = StageStatus(raw_status)
        except ValueError:
            stage_status = StageStatus.PENDING
        stages[key] = StageEntry(
            status=stage_status,
            updated_at=value.get("updated_at", utc_now_iso()),
            meta=value.get("meta") or {},
        )
    for key, entry in default_stages().items():
        stages.setdefault(key, entry)

    raw_status = data.get("status", JobStatus.RUNNING.value)
    try:
        status = JobStatus(raw_status)
    except ValueError:
        status = JobStatus.RUNNING

    raw_controller_status = data.get("controller_status", ControllerStatus.INITIALIZING.value)
    try:
        controller_status = ControllerStatus(raw_controller_status)
    except ValueError:
        controller_status = ControllerStatus.INITIALIZING

    raw_trace = data.get("decision_trace") or data.get("decision_history") or []
    decision_trace: List[DecisionTraceEntry] = []
    for index, value in enumerate(raw_trace, start=1):
        decision_trace.append(
            DecisionTraceEntry(
                step_index=int(value.get("step_index", index) or index),
                timestamp=value.get("timestamp", utc_now_iso()),
                chosen_action=str(value.get("chosen_action") or value.get("next_action") or ""),
                confidence=round(max(0.0, min(1.0, float(value.get("confidence", 0.0) or 0.0))), 4),
                rationale=str(value.get("rationale", "") or ""),
                parameters=value.get("parameters") or {},
                source=str(value.get("source", "model") or "model"),
                error=value.get("error"),
                overridden=bool(value.get("overridden", False)),
            )
        )

    state = JobState(
        job_id=data["job_id"],
        created_at=data.get("created_at", utc_now_iso()),
        updated_at=data.get("updated_at", data.get("created_at", utc_now_iso())),
        input_summary=data.get("input_summary") or {},
        request_payload=data.get("request_payload") or {},
        requirements=data.get("requirements") or {},
        user_goal=data.get("user_goal", ""),
        status=status,
        controller_status=controller_status,
        controller_status_detail=data.get("controller_status_detail", ""),
        terminal_status=data.get("terminal_status"),
        failure_reason=data.get("failure_reason"),
        failure_code=data.get("failure_code"),
        failure_detail=data.get("failure_detail"),
        waiting_for_user_input=bool(data.get("waiting_for_user_input", False)),
        requested_user_input=data.get("requested_user_input") or {},
        provider_status=data.get("provider_status") or {},
        source_status=data.get("source_status") or {},
        analysis_available=bool(data.get("analysis_available", False)),
        transcript_available=bool(data.get("transcript_available", False)),
        analysis_summary=data.get("analysis_summary", ""),
        analysis=data.get("analysis") or {},
        style_profile_summary=data.get("style_profile_summary") or {},
        segment_summary=data.get("segment_summary") or {},
        current_plan=data.get("current_plan") or {},
        plan_summary=data.get("plan_summary") or {},
        plan_validation=data.get("plan_validation") or {},
        plan_validation_score=_coerce_optional_float(data.get("plan_validation_score")),
        plan_needs_validation=bool(data.get("plan_needs_validation", False)),
        overlay_plan=data.get("overlay_plan") or {},
        audio_plan=data.get("audio_plan") or {},
        render_spec=data.get("render_spec") or {},
        render_summary=data.get("render_summary") or {},
        motion_effects_path=data.get("motion_effects_path"),
        revision_attempts=int(data.get("revision_attempts", 0) or 0),
        render_attempts=int(data.get("render_attempts", 0) or 0),
        stalled_revision_count=int(data.get("stalled_revision_count", 0) or 0),
        last_revision_fingerprint=str(data.get("last_revision_fingerprint", "") or ""),
        latest_user_feedback=data.get("latest_user_feedback", ""),
        applied_edit_requests=data.get("applied_edit_requests") or [],
        decision_trace=decision_trace,
        decision_history=data.get("decision_history") or [],
        last_decision=data.get("last_decision") or {},
        invalid_decision_count=int(data.get("invalid_decision_count", 0) or 0),
        low_confidence_decision_count=int(data.get("low_confidence_decision_count", 0) or 0),
        final_response=data.get("final_response") or {},
        work_dir=data.get("work_dir", ""),
        youtube_uploaded=bool(data.get("youtube_uploaded", False)),
        stages=stages,
        warnings=data.get("warnings") or [],
        errors=data.get("errors") or [],
    )
    if not state.user_goal:
        state.user_goal = str(state.requirements.get("prompt", "") or "")
    if not state.latest_user_feedback:
        state.latest_user_feedback = _extract_latest_feedback(state.requirements)
    if not state.applied_edit_requests:
        state.applied_edit_requests = []
    if not state.decision_history and state.decision_trace:
        state.decision_history = [
            {
                "step_index": entry.step_index,
                "timestamp": entry.timestamp,
                "chosen_action": entry.chosen_action,
                "next_action": entry.chosen_action,
                "confidence": entry.confidence,
                "rationale": entry.rationale,
                "parameters": entry.parameters,
                "source": entry.source,
                "error": entry.error,
                "overridden": entry.overridden,
            }
            for entry in state.decision_trace
        ]
    if data.get("controller_status") is None:
        if state.status == JobStatus.SUCCEEDED:
            state.controller_status = ControllerStatus.FINISHED
        elif state.status == JobStatus.ABORTED:
            state.controller_status = ControllerStatus.ABORTED
        elif state.status == JobStatus.FAILED:
            state.controller_status = ControllerStatus.FAILED
        elif state.status == JobStatus.WAITING_USER_INPUT:
            state.controller_status = _controller_status_for_user_input_reason(
                (state.requested_user_input or {}).get("reason")
            )
    if not state.plan_summary and state.current_plan:
        state.plan_summary = summarize_plan(state.current_plan)
    if not state.style_profile_summary and state.analysis:
        state.style_profile_summary = summarize_style_profile(state.analysis)
    if not state.segment_summary and state.analysis:
        state.segment_summary = summarize_segments(state.analysis)
    return state


def _as_dict(state: JobState) -> Dict[str, Any]:
    obj = asdict(state)
    obj["status"] = state.status.value
    obj["controller_status"] = state.controller_status.value
    for key, value in obj["stages"].items():
        value["status"] = state.stages[key].status.value
    return obj


def load_state(job_dir: str) -> Optional[JobState]:
    path = state_file(job_dir)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    return _to_state(data)


def save_state(job_dir: str, state: JobState) -> None:
    os.makedirs(job_dir, exist_ok=True)
    touch(state)
    path = state_file(job_dir)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(_as_dict(state), handle, ensure_ascii=False, indent=2)


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
    touch(state)


def add_warning(state: JobState, code: str, message: str, detail: Any = None) -> None:
    state.warnings.append({"code": code, "message": message, "detail": detail})
    touch(state)


def add_error(state: JobState, stage: StageName, code: str, message: str, detail: Any = None) -> None:
    state.errors.append(
        {"stage": stage.value, "code": code, "message": message, "detail": detail}
    )
    touch(state)


def controller_status_category(status: ControllerStatus | str) -> str:
    raw = status.value if isinstance(status, ControllerStatus) else str(status)
    if raw in {
        ControllerStatus.INITIALIZING.value,
        ControllerStatus.ANALYZING.value,
        ControllerStatus.PLANNING.value,
        ControllerStatus.VISION_TEMPLATE_TRAINING.value,
        ControllerStatus.VISION_TEMPLATE_TRANSFERRING.value,
        ControllerStatus.REVISING.value,
        ControllerStatus.VALIDATING.value,
        ControllerStatus.RENDERING.value,
    }:
        return "working"
    if raw == ControllerStatus.AWAITING_USER_INPUT.value:
        return "waiting_for_user_input"
    if raw in {
        ControllerStatus.BLOCKED_BY_UNAPPLIED_EDITS.value,
        ControllerStatus.REVISION_LIMIT_EXHAUSTED.value,
    }:
        return "blocked"
    if raw == ControllerStatus.FINISHED.value:
        return "complete"
    return "failed"


def build_controller_status_payload(state: JobState) -> Dict[str, Any]:
    return {
        "job_status": state.status.value,
        "controller_status": state.controller_status.value,
        "controller_status_category": controller_status_category(state.controller_status),
        "controller_status_detail": state.controller_status_detail,
        "terminal_status": state.terminal_status,
        "failure_reason": state.failure_reason,
        "failure_code": state.failure_code,
        "waiting_for_user_input": state.waiting_for_user_input,
        "pending_edit_request_count": len(pending_edit_requests(state)),
        "decision_trace_count": len(state.decision_trace),
        "last_decision": _sanitize_decision_trace_entry(state.last_decision) if state.last_decision else {},
        "provider_status": _sanitize_provider_status_payload(state.provider_status),
    }


def sanitize_decision_trace_entries(entries: List[DecisionTraceEntry | Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [_sanitize_decision_trace_entry(entry) for entry in entries]


def _round_optional(value: Any, digits: int = 4) -> Optional[float]:
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _coerce_optional_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _dedupe_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _controller_status_for_user_input_reason(reason: Any) -> ControllerStatus:
    normalized = str(reason or "").strip().lower()
    if normalized == "pending_user_feedback":
        return ControllerStatus.BLOCKED_BY_UNAPPLIED_EDITS
    if normalized in {"max_revision_attempts", "max_revisions_reached"}:
        return ControllerStatus.REVISION_LIMIT_EXHAUSTED
    return ControllerStatus.AWAITING_USER_INPUT


def _sanitize_decision_trace_entry(entry: DecisionTraceEntry | Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(entry, DecisionTraceEntry):
        payload = {
            "step_index": entry.step_index,
            "timestamp": entry.timestamp,
            "chosen_action": entry.chosen_action,
            "confidence": entry.confidence,
            "rationale": entry.rationale,
            "parameters": entry.parameters,
            "source": entry.source,
            "error": entry.error,
            "overridden": entry.overridden,
        }
    else:
        payload = dict(entry)
    payload["parameters"] = _sanitize_trace_value(payload.get("parameters"), key="parameters")
    payload["rationale"] = _sanitize_trace_value(payload.get("rationale"), key="rationale")
    if payload.get("error") is not None:
        payload["error"] = _sanitize_trace_value(payload.get("error"), key="error")
    return payload


def _sanitize_provider_status_payload(status: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(status, dict):
        return {}
    providers = status.get("providers") or {}
    sanitized_providers = {}
    for name, payload in providers.items():
        provider_payload = payload if isinstance(payload, dict) else {}
        sanitized_providers[str(name)] = {
            "name": provider_payload.get("name", name),
            "required": bool(provider_payload.get("required", False)),
            "configured": bool(provider_payload.get("configured", False)),
            "ready": bool(provider_payload.get("ready", False)),
            "code": provider_payload.get("code", ""),
            "message": provider_payload.get("message", ""),
        }
    return {
        "ready": bool(status.get("ready", False)),
        "providers": sanitized_providers,
    }


def _sanitize_trace_value(value: Any, *, key: str = "") -> Any:
    sensitive_key = str(key or "").lower()
    if isinstance(value, dict):
        return {
            str(child_key): _sanitize_trace_value(
                child_value,
                key=str(child_key),
            )
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_trace_value(item, key=key) for item in value]
    if value is None or isinstance(value, (int, float, bool)):
        return value

    text = str(value)
    if any(token in sensitive_key for token in ("key", "token", "secret", "credential", "authorization", "cookie")):
        return "[redacted]"
    if "api_key" in text.lower() or "bearer " in text.lower():
        return "[redacted]"
    text = text.replace("\\", "/")
    if ":/" in text and ("?" in text or "token=" in text.lower() or "key=" in text.lower()):
        return "[redacted_url]"
    if text.startswith("/") or re.match(r"^[a-zA-Z]:/", text):
        return "[redacted_path]"
    return value
