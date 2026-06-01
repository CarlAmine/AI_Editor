from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from ai_editor.generation_modes import (
    FREE_GENERATION_MODE,
    REFERENCE_STYLE_TRANSFER_MODE,
    REFERENCE_EDIT_AGENT_MODE,
    normalize_generation_mode,
)
from pipeline.feedback import build_pipeline_assistant_feedback

from .artifacts import ArtifactRegistry
from .decision_engine import DecisionOutcome, PipelineDecision, PipelineDecisionEngine
from .executor import ExecutionContext, PipelineExecutor
from .provider_errors import ProviderFailure
from .providers import get_provider_health, summarize_missing_required_providers
from .state import (
    ControllerStatus,
    JobState,
    JobStatus,
    StageName,
    StageStatus,
    add_error,
    add_warning,
    build_plan_change_fingerprint,
    build_controller_status_payload,
    clear_requested_user_input,
    is_terminal,
    load_state,
    mark_terminal,
    new_state,
    pending_edit_requests,
    record_decision,
    save_state,
    set_controller_status,
    set_latest_user_feedback,
    set_provider_status,
    set_requested_user_input,
    update_stage,
)


@dataclass
class RunnerGuardrails:
    minimum_validation_score: float = 0.5
    final_action_confidence: float = 0.72
    destructive_action_confidence: float = 0.82
    preview_action_confidence: float = 0.55
    controller_action_confidence: float = 0.45
    max_revision_attempts: int = 5
    max_stalled_revision_attempts: int = 2
    max_render_attempts: int = 2
    max_invalid_decisions: int = 1
    max_low_confidence_decisions: int = 3
    max_loop_iterations: int = 18


def _job_dirs(job_id: str) -> Dict[str, str]:
    root = os.path.join("tmp", "jobs", job_id)
    return {
        "job": root,
        "plans": os.path.join(root, "plans"),
        "media": os.path.join(root, "media"),
        "outputs": os.path.join(root, "outputs"),
        "logs": os.path.join(root, "logs"),
        "debug": os.path.join(root, "debug"),
    }


def _ensure_layout(directories: Dict[str, str]) -> None:
    for path in directories.values():
        os.makedirs(path, exist_ok=True)


def _infer_intent_mode(prompt: str, requirements: Dict[str, Any]) -> str:
    explicit = str(requirements.get("intent_mode", "")).lower().strip()
    if explicit in {"video", "shorts"}:
        return explicit
    lowered = (prompt or "").lower()
    return "shorts" if any(key in lowered for key in ["youtube short", "youtube shorts", "shorts", "short "]) else "video"


def _normalize_requirements(request_payload: Dict[str, Any]) -> Dict[str, Any]:
    req_state = request_payload.get("requirements_state") or {}
    requirements = dict(req_state)
    requirements["prompt"] = request_payload.get("prompt", "")
    requirements["music_mode"] = request_payload.get("music_mode", "original")
    requirements["custom_music_url"] = request_payload.get("custom_music_url")
    requirements["custom_music_start"] = request_payload.get("custom_music_start")
    requirements["custom_music_end"] = request_payload.get("custom_music_end")
    requirements["custom_music_segment"] = request_payload.get("custom_music_segment")
    requirements["custom_music_segments"] = request_payload.get("custom_music_segments")
    requirements["generation_mode"] = normalize_generation_mode(
        requirements.get("generation_mode"),
        default=FREE_GENERATION_MODE,
    )
    if "slot_mapping" not in requirements and request_payload.get("slot_mapping") is not None:
        requirements["slot_mapping"] = request_payload.get("slot_mapping")
    if "expected_slots" not in requirements and request_payload.get("expected_slots") is not None:
        requirements["expected_slots"] = request_payload.get("expected_slots")
    vision_template = dict(requirements.get("vision_template") or {})
    default_vision_template = {
        "fps": 8.0,
        "size": 224,
        "epochs": 5,
        "device": "auto",
        "max_seconds": None,
        "use_pretrained_backbone": False,
        "synthetic_pretrain": False,
        "synthetic_pretrain_samples": 16,
        "synthetic_pretrain_epochs": 1,
    }
    default_vision_template.update(vision_template)
    requirements["vision_template"] = default_vision_template
    semantic_edit = dict(requirements.get("semantic_edit") or {})
    default_semantic_edit = {
        "enabled": False,
        "backend": "auto",
        "text_queries": ["person", "chair", "table", "product"],
        "attach_to_template": True,
    }
    default_semantic_edit.update(semantic_edit)
    requirements["semantic_edit"] = default_semantic_edit
    requirements["edit_mode"] = str(requirements.get("edit_mode", "scene")).lower().strip()
    if requirements["edit_mode"] not in {"scene", "ocr"}:
        requirements["edit_mode"] = "scene"
    requirements["intent_mode"] = _infer_intent_mode(requirements.get("prompt", ""), requirements)
    requirements["output_mode"] = str(requirements.get("output_mode", "")).lower().strip()
    if requirements["output_mode"] not in {"native_9x16", "crop_to_9x16", ""}:
        requirements["output_mode"] = ""
    requirements["refit_mode"] = str(requirements.get("refit_mode", os.getenv("REFIT_MODE", "crop_center"))).lower()
    if requirements["refit_mode"] == "crop":
        requirements["refit_mode"] = "crop_center"
    if requirements["refit_mode"] not in {"crop_center", "pad", "native_9x16"}:
        requirements["refit_mode"] = "crop_center"
    if not requirements["output_mode"]:
        requirements["output_mode"] = "native_9x16" if requirements["refit_mode"] == "native_9x16" else "crop_to_9x16"
    return requirements


def _latest_feedback(requirements: Dict[str, Any]) -> str:
    for key in ("edit_requests", "user_requests"):
        values = requirements.get(key) or []
        if isinstance(values, list):
            for item in reversed(values):
                text = str(item or "").strip()
                if text:
                    return text
    return ""


def _save(ctx: ExecutionContext) -> None:
    save_state(ctx.dirs["job"], ctx.state)
    trace_path = os.path.join(ctx.dirs["job"], "decision_trace.json")
    trace_entries = [
        {
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
        for entry in ctx.state.decision_trace
    ]
    with open(trace_path, "w", encoding="utf-8") as handle:
        json.dump(trace_entries, handle, ensure_ascii=False, indent=2)
    ctx.artifacts.register_file(
        "decision.trace",
        trace_path,
        {"count": len(trace_entries)},
        "application/json",
    )
    ctx.artifacts.save(ctx.dirs["job"])


def _track_revision_progress(
    state: JobState,
    *,
    previous_fingerprint: str,
    guardrails: RunnerGuardrails,
) -> None:
    current_fingerprint = build_plan_change_fingerprint(state.current_plan)
    state.last_revision_fingerprint = current_fingerprint

    if not current_fingerprint or current_fingerprint != previous_fingerprint:
        state.stalled_revision_count = 0
        return

    state.stalled_revision_count += 1
    add_warning(
        state,
        "STALLED_REVISION_LOOP",
        "Plan revision did not make a meaningful structural change.",
        {
            "stalled_revision_count": state.stalled_revision_count,
            "max_stalled_revision_attempts": guardrails.max_stalled_revision_attempts,
            "revision_attempts": state.revision_attempts,
        },
    )
    if state.stalled_revision_count < guardrails.max_stalled_revision_attempts:
        return

    set_requested_user_input(
        state,
        {
            "reason": "stalled_revision_loop",
            "question": (
                "I revised the plan multiple times without a meaningful change. "
                "Please clarify the single highest-priority edit or provide stronger source guidance."
            ),
        },
    )


def _request_user_input_decision(reason: str, question: str) -> PipelineDecision:
    return PipelineDecision(
        next_action="request_user_input",
        confidence=1.0,
        rationale=question,
        parameters={"reason": reason, "question": question},
    )


def _apply_guardrails(
    state: JobState,
    decision: PipelineDecision,
    guardrails: RunnerGuardrails,
) -> Tuple[PipelineDecision, bool]:
    overridden = False
    pending_requests = pending_edit_requests(state)

    if pending_requests and state.current_plan and decision.next_action in {"render_preview", "render_final", "finish"}:
        overridden = True
        set_controller_status(
            state,
            ControllerStatus.BLOCKED_BY_UNAPPLIED_EDITS,
            detail="Pending user edit requests must be applied before rendering or finishing.",
        )
        if state.revision_attempts >= guardrails.max_revision_attempts:
            decision = _request_user_input_decision(
                "pending_user_feedback",
                "I still have unapplied edit requests, but I already hit the revision limit. Please confirm which change matters most so I can continue safely.",
            )
        else:
            decision = PipelineDecision(
                next_action="revise_plan",
                confidence=max(decision.confidence, 0.7),
                rationale="Rendering is blocked until pending user edit requests are applied to the plan.",
                parameters={
                    "guardrail_reason": "pending_user_feedback",
                    "pending_edit_requests": pending_requests[:3],
                },
            )

    if decision.next_action in {"render_preview", "render_final", "finish"}:
        validation_override_reason = _validation_override_reason(decision)
        if not state.current_plan:
            overridden = True
            decision = PipelineDecision(
                next_action="generate_plan",
                confidence=max(decision.confidence, 0.7),
                rationale="Render/finalization blocked because no plan exists yet.",
                parameters={"guardrail_reason": "missing_plan"},
            )
        elif state.plan_needs_validation or not state.plan_validation or state.plan_validation_score is None:
            overridden = True
            decision = PipelineDecision(
                next_action="validate_plan",
                confidence=max(decision.confidence, 0.72),
                rationale="Render/finalization blocked until the current plan has a fresh validation result.",
                parameters={"guardrail_reason": "plan_unvalidated"},
            )
        elif state.plan_validation_score < guardrails.minimum_validation_score and not validation_override_reason:
            overridden = True
            if state.revision_attempts >= guardrails.max_revision_attempts:
                set_controller_status(
                    state,
                    ControllerStatus.REVISION_LIMIT_EXHAUSTED,
                    detail="Validation score stayed below the render threshold after exhausting revisions.",
                )
                decision = _request_user_input_decision(
                    "max_revision_attempts",
                    "I hit the revision limit before the plan reached a safe render score. Please clarify the highest-priority change before I continue.",
                )
            else:
                decision = PipelineDecision(
                    next_action="revise_plan",
                    confidence=max(decision.confidence, 0.74),
                    rationale="Render/finalization blocked because the plan validation score is too low.",
                    parameters={
                        "guardrail_reason": "low_validation_score",
                        "validation_score": state.plan_validation_score,
                    },
                )

    if decision.next_action == "revise_plan" and state.revision_attempts >= guardrails.max_revision_attempts:
        overridden = True
        if (state.plan_validation_score or 0.0) >= guardrails.minimum_validation_score:
            if pending_requests:
                set_controller_status(
                    state,
                    ControllerStatus.BLOCKED_BY_UNAPPLIED_EDITS,
                    detail="Revision limit reached before pending user edits were incorporated.",
                )
                decision = _request_user_input_decision(
                    "pending_user_feedback",
                    "I hit the revision limit before I could incorporate all requested edits. Please confirm the highest-priority change so I can continue safely.",
                )
            else:
                decision = PipelineDecision(
                    next_action="render_final",
                    confidence=0.76,
                    rationale="Revision limit reached; proceeding with the strongest validated plan.",
                    parameters={"guardrail_reason": "max_revision_attempts"},
                )
        else:
            set_controller_status(
                state,
                ControllerStatus.REVISION_LIMIT_EXHAUSTED,
                detail="Revision limit reached before the plan became render-safe.",
            )
            decision = _request_user_input_decision(
                "max_revision_attempts",
                "I hit the plan revision limit before reaching a strong enough edit. Please clarify the priority or provide stronger source guidance.",
            )

    if decision.next_action in {"render_preview", "render_final"} and state.render_attempts >= guardrails.max_render_attempts:
        overridden = True
        decision = PipelineDecision(
            next_action="abort_job",
            confidence=1.0,
            rationale="Render attempt limit reached.",
            parameters={"reason": "max_render_attempts"},
        )

    if decision.next_action == "render_preview" and decision.confidence < guardrails.preview_action_confidence:
        overridden = True
        decision = PipelineDecision(
            next_action="validate_plan",
            confidence=max(decision.confidence, 0.6),
            rationale="Preview render blocked by low controller confidence; validating plan first.",
            parameters={"guardrail_reason": "low_preview_confidence"},
        )

    if decision.next_action in {"render_final", "finish"} and decision.confidence < guardrails.final_action_confidence:
        overridden = True
        decision = PipelineDecision(
            next_action="validate_plan",
            confidence=max(decision.confidence, 0.65),
            rationale="Final action blocked by low controller confidence; validating plan first.",
            parameters={"guardrail_reason": "low_final_confidence"},
        )

    if decision.next_action == "abort_job" and decision.confidence < guardrails.destructive_action_confidence:
        overridden = True
        decision = _request_user_input_decision(
            "low_abort_confidence",
            "The controller was not confident enough to abort automatically. Please confirm whether to stop or adjust the edit direction.",
        )

    return decision, overridden


def _resolve_decision(
    decision_engine: PipelineDecisionEngine,
    state: JobState,
    guardrails: RunnerGuardrails,
) -> DecisionOutcome:
    outcome = decision_engine.decide(state)
    if outcome.source == "provider_error":
        return outcome
    if outcome.decision is not None:
        return outcome

    state.invalid_decision_count += 1
    set_controller_status(
        state,
        ControllerStatus.FAILED,
        detail=str(outcome.error or "Controller returned invalid output."),
    )
    if state.invalid_decision_count > guardrails.max_invalid_decisions:
        return outcome

    repair = decision_engine.repair_decide(
        state,
        error=str(outcome.error or "Controller returned invalid output."),
        invalid_payload=outcome.invalid_payload,
    )
    if repair.decision is not None:
        set_controller_status(
            state,
            ControllerStatus.INITIALIZING,
            detail="Controller decision repaired after invalid output.",
        )
        return repair
    state.invalid_decision_count += 1
    set_controller_status(
        state,
        ControllerStatus.FAILED,
        detail=str(repair.error or outcome.error or "Controller repair failed."),
    )
    return repair


def _handle_invalid_decision_outcome(
    state: JobState,
    outcome: DecisionOutcome,
    *,
    job_id: str,
) -> Dict[str, Any]:
    message = (
        outcome.user_message
        or outcome.error
        or "The controller returned invalid structured output and the repair attempt did not succeed."
    )
    add_error(
        state,
        StageName.CONTROLLER_DECISION,
        outcome.failure_code or "CONTROLLER_DECISION_INVALID",
        message,
        outcome.debug_details or outcome.invalid_payload,
    )
    mark_terminal(
        state,
        JobStatus.FAILED,
        reason=message,
        code=outcome.failure_code or "CONTROLLER_DECISION_INVALID",
        detail=outcome.debug_details or outcome.invalid_payload,
    )
    assistant_feedback = build_pipeline_assistant_feedback(
        error=message,
        stage="CONTROLLER_DECISION",
        requirements=state.requirements,
    )
    return {
        "success": False,
        "error": message,
        "status": "failed",
        "project_id": job_id,
        "warnings": state.warnings,
        "errors": state.errors,
        "assistant_feedback": assistant_feedback,
        **build_controller_status_payload(state),
    }


def _provider_requirements(
    *,
    decision_engine: Optional[PipelineDecisionEngine],
    executor: Optional[PipelineExecutor],
) -> Dict[str, bool]:
    requirements = {"llm": False, "render": executor is None, "drive": executor is None}
    if executor is not None and hasattr(executor, "provider_requirements"):
        reported = getattr(executor, "provider_requirements")()
        requirements["render"] = bool(reported.get("render", requirements["render"]))
        requirements["drive"] = bool(reported.get("drive", requirements["drive"]))
    if decision_engine is not None and hasattr(decision_engine, "provider_requirements"):
        reported = getattr(decision_engine, "provider_requirements")()
        requirements["llm"] = bool(reported.get("llm", requirements["llm"]))
    return requirements


def _should_use_deterministic_style_route(requirements: Dict[str, Any]) -> bool:
    mode = normalize_generation_mode(requirements.get("generation_mode"), default=FREE_GENERATION_MODE)
    return mode in {REFERENCE_STYLE_TRANSFER_MODE, REFERENCE_EDIT_AGENT_MODE}


def _run_deterministic_style_transfer_route(
    ctx: ExecutionContext,
    executor: PipelineExecutor,
) -> None:
    for action in ("run_analysis", "generate_plan", "validate_plan", "render_final", "finish"):
        if is_terminal(ctx.state):
            break
        decision = PipelineDecision(
            next_action=action,
            confidence=1.0,
            rationale="Deterministic reference style-transfer route.",
            parameters={"deterministic_route": True},
        )
        record_decision(
            ctx.state,
            next_action=decision.next_action,
            confidence=decision.confidence,
            rationale=decision.rationale,
            parameters=decision.parameters,
            source="deterministic",
            overridden=False,
        )
        _save(ctx)
        executor.execute(ctx, decision)
        _save(ctx)


def _validate_provider_readiness(
    ctx: ExecutionContext,
    *,
    decision_engine: Optional[PipelineDecisionEngine],
    executor: Optional[PipelineExecutor],
) -> Optional[Dict[str, Any]]:
    preferred_provider = getattr(decision_engine, "preferred_provider", None)
    requirements = _provider_requirements(decision_engine=decision_engine, executor=executor)
    provider_health = get_provider_health(
        require_llm=requirements["llm"],
        require_render=requirements["render"],
        require_drive=requirements["drive"],
        preferred_provider=preferred_provider,
    )
    update_stage(ctx.state, StageName.PROVIDER_READINESS, StageStatus.RUNNING)
    set_provider_status(ctx.state, provider_health)
    missing = summarize_missing_required_providers(provider_health)
    if not missing:
        update_stage(ctx.state, StageName.PROVIDER_READINESS, StageStatus.SUCCEEDED)
        return None

    message = str(missing[0].get("message") or "A required provider is not ready.")
    add_error(
        ctx.state,
        StageName.PROVIDER_READINESS,
        "PROVIDER_READINESS_FAILED",
        message,
        {"providers": missing},
    )
    update_stage(
        ctx.state,
        StageName.PROVIDER_READINESS,
        StageStatus.FAILED,
        {"providers": missing},
    )
    mark_terminal(
        ctx.state,
        JobStatus.FAILED,
        reason=message,
        code="PROVIDER_READINESS_FAILED",
        detail={"providers": missing},
    )
    assistant_feedback = build_pipeline_assistant_feedback(
        error=message,
        stage=StageName.PROVIDER_READINESS.value,
        requirements=ctx.state.requirements,
    )
    return {
        "success": False,
        "error": message,
        "status": "failed",
        "project_id": ctx.job_id,
        "warnings": ctx.state.warnings,
        "errors": ctx.state.errors,
        "assistant_feedback": assistant_feedback,
        **build_controller_status_payload(ctx.state),
    }


def _handle_low_confidence_counter(
    state: JobState,
    decision: PipelineDecision,
    overridden: bool,
    guardrails: RunnerGuardrails,
) -> PipelineDecision:
    if overridden or _is_low_confidence(decision, guardrails):
        state.low_confidence_decision_count += 1
    else:
        state.low_confidence_decision_count = 0
    if state.low_confidence_decision_count > guardrails.max_low_confidence_decisions:
        return _request_user_input_decision(
            "controller_low_confidence",
            "I paused because the controller stayed uncertain for several steps. Please confirm the direction you want before I continue.",
        )
    return decision


def _is_low_confidence(decision: PipelineDecision, guardrails: RunnerGuardrails) -> bool:
    if decision.next_action == "abort_job":
        threshold = guardrails.destructive_action_confidence
    elif decision.next_action in {"render_final", "finish"}:
        threshold = guardrails.final_action_confidence
    elif decision.next_action == "render_preview":
        threshold = guardrails.preview_action_confidence
    else:
        threshold = guardrails.controller_action_confidence
    return decision.confidence < threshold


def _sync_state_with_request(state: JobState, request_payload: Dict[str, Any], requirements: Dict[str, Any], job_dir: str) -> None:
    incoming_feedback = _latest_feedback(requirements)
    if state.waiting_for_user_input and incoming_feedback and incoming_feedback != state.latest_user_feedback:
        clear_requested_user_input(state)
    if incoming_feedback and incoming_feedback != state.latest_user_feedback:
        state.stalled_revision_count = 0
        state.last_revision_fingerprint = build_plan_change_fingerprint(state.current_plan)

    state.input_summary = {
        "primary_url": request_payload.get("primary_url"),
        "has_drive_folder": bool(request_payload.get("gdrive_folder_id")),
        "sources_count": len(request_payload.get("sources") or []),
    }
    state.requirements = requirements
    state.request_payload = dict(request_payload or {})
    state.user_goal = str(requirements.get("prompt", "") or "")
    state.work_dir = job_dir
    set_latest_user_feedback(state, incoming_feedback)


def _build_waiting_user_input_response(state: JobState, job_id: str) -> Dict[str, Any]:
    request = state.requested_user_input or {}
    message = str(request.get("question") or "More input is needed to continue.").strip()
    assistant_feedback = {
        "route_to_chat": True,
        "category": "input",
        "reason": request.get("reason", "clarification_required"),
        "message": message,
        "state_patch": {
            "pipeline_feedback": {
                "stage": "REQUEST_USER_INPUT",
                "error": message,
                "category": "input",
                "reason": request.get("reason", "clarification_required"),
                "route_to_chat": True,
            }
        },
    }
    return {
        "success": False,
        "error": message,
        "status": "needs_user_input",
        "project_id": job_id,
        "warnings": state.warnings,
        "errors": state.errors,
        "assistant_feedback": assistant_feedback,
        **build_controller_status_payload(state),
    }


def _build_failure_response(state: JobState, job_id: str, *, status: str) -> Dict[str, Any]:
    message = state.failure_reason or (state.errors[-1]["message"] if state.errors else "Pipeline failed.")
    stage = state.errors[-1]["stage"] if state.errors else "UNKNOWN"
    assistant_feedback = build_pipeline_assistant_feedback(
        error=message,
        stage=stage,
        requirements=state.requirements,
    )
    return {
        "success": False,
        "error": message,
        "status": status,
        "project_id": job_id,
        "warnings": state.warnings,
        "errors": state.errors,
        "assistant_feedback": assistant_feedback,
        **build_controller_status_payload(state),
    }


def _build_response(ctx: ExecutionContext) -> Dict[str, Any]:
    state = ctx.state
    if state.status == JobStatus.SUCCEEDED and state.final_response:
        return {**state.final_response, **build_controller_status_payload(state)}
    if state.status == JobStatus.WAITING_USER_INPUT:
        return _build_waiting_user_input_response(state, ctx.job_id)
    if state.status == JobStatus.ABORTED:
        return _build_failure_response(state, ctx.job_id, status="aborted")
    if state.status == JobStatus.FAILED:
        return _build_failure_response(state, ctx.job_id, status="failed")
    if state.final_response:
        return {**state.final_response, **build_controller_status_payload(state)}
    return {
        "success": False,
        "error": state.failure_reason or "Pipeline stopped unexpectedly.",
        "status": "failed",
        "project_id": ctx.job_id,
        "warnings": state.warnings,
        "errors": state.errors,
        **build_controller_status_payload(state),
    }


def run_job(
    job_id: str,
    request_payload: Dict[str, Any],
    *,
    decision_engine: Optional[PipelineDecisionEngine] = None,
    executor: Optional[PipelineExecutor] = None,
    guardrails: Optional[RunnerGuardrails] = None,
) -> Dict[str, Any]:
    directories = _job_dirs(job_id)
    _ensure_layout(directories)
    requirements = _normalize_requirements(request_payload)

    state = load_state(directories["job"]) or new_state(
        job_id=job_id,
        input_summary={
            "primary_url": request_payload.get("primary_url"),
            "has_drive_folder": bool(request_payload.get("gdrive_folder_id")),
            "sources_count": len(request_payload.get("sources") or []),
        },
        requirements=requirements,
    )
    _sync_state_with_request(state, request_payload, requirements, directories["job"])
    if not is_terminal(state):
        set_controller_status(state, ControllerStatus.INITIALIZING, detail="Controller loop ready.")
    artifacts = ArtifactRegistry.load(directories["job"])
    ctx = ExecutionContext(
        job_id=job_id,
        request_payload=request_payload,
        requirements=requirements,
        dirs=directories,
        state=state,
        artifacts=artifacts,
        runtime={},
    )

    guardrails = guardrails or RunnerGuardrails()
    use_deterministic_style_route = _should_use_deterministic_style_route(requirements)
    if not use_deterministic_style_route:
        decision_engine = decision_engine or PipelineDecisionEngine(
            minimum_validation_score=guardrails.minimum_validation_score,
            max_revision_attempts=guardrails.max_revision_attempts,
        )
    executor = executor or PipelineExecutor(
        save_hook=_save,
        minimum_validation_score=guardrails.minimum_validation_score,
    )

    readiness_failure = _validate_provider_readiness(
        ctx,
        decision_engine=decision_engine,
        executor=executor,
    )
    _save(ctx)
    if readiness_failure is not None:
        return readiness_failure

    if use_deterministic_style_route:
        try:
            _run_deterministic_style_transfer_route(ctx, executor)
        except ProviderFailure as exc:
            if not is_terminal(ctx.state):
                mark_terminal(
                    ctx.state,
                    JobStatus.FAILED,
                    reason=exc.user_message,
                    code=exc.code,
                    detail=exc.to_error_detail(),
                )
                _save(ctx)
        except Exception as exc:
            if not is_terminal(ctx.state):
                mark_terminal(ctx.state, JobStatus.FAILED, reason=str(exc), code="PIPELINE_EXECUTION_FAILED")
                _save(ctx)
        return _build_response(ctx)

    iterations = 0
    while not is_terminal(ctx.state):
        if iterations >= guardrails.max_loop_iterations:
            set_requested_user_input(
                ctx.state,
                {
                    "reason": "max_loop_iterations",
                    "question": "I paused after too many workflow steps. Please confirm the next edit priority before I continue.",
                },
            )
            _save(ctx)
            break

        outcome = _resolve_decision(decision_engine, ctx.state, guardrails)
        if outcome.decision is None:
            _save(ctx)
            return _handle_invalid_decision_outcome(ctx.state, outcome, job_id=ctx.job_id)
        decision = outcome.decision
        decision, overridden = _apply_guardrails(ctx.state, decision, guardrails)
        decision = _handle_low_confidence_counter(ctx.state, decision, overridden, guardrails)

        record_decision(
            ctx.state,
            next_action=decision.next_action,
            confidence=decision.confidence,
            rationale=decision.rationale,
            parameters=decision.parameters,
            source=outcome.source,
            error=outcome.error,
            overridden=overridden,
        )
        if outcome.decision is not None and outcome.source in {"model", "repair"}:
            ctx.state.failure_reason = None
        _save(ctx)

        revision_fingerprint_before = ""
        if decision.next_action == "revise_plan":
            revision_fingerprint_before = build_plan_change_fingerprint(ctx.state.current_plan)

        try:
            executor.execute(ctx, decision)
        except ProviderFailure as exc:
            if not is_terminal(ctx.state):
                mark_terminal(
                    ctx.state,
                    JobStatus.FAILED,
                    reason=exc.user_message,
                    code=exc.code,
                    detail=exc.to_error_detail(),
                )
                _save(ctx)
            break
        except Exception as exc:
            if not is_terminal(ctx.state):
                mark_terminal(ctx.state, JobStatus.FAILED, reason=str(exc), code="PIPELINE_EXECUTION_FAILED")
                _save(ctx)
            break

        if decision.next_action == "revise_plan" and not is_terminal(ctx.state):
            _track_revision_progress(
                ctx.state,
                previous_fingerprint=revision_fingerprint_before,
                guardrails=guardrails,
            )
            _save(ctx)

        iterations += 1

    return _build_response(ctx)


def _validation_override_reason(decision: PipelineDecision) -> str:
    parameters = decision.parameters or {}
    for key in ("validation_override_reason", "render_gate_override_reason"):
        value = str(parameters.get(key, "") or "").strip()
        if value:
            return value
    return ""
