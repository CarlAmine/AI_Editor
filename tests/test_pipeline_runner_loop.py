import shutil
from pathlib import Path
from uuid import uuid4

from pipeline.decision_engine import DecisionOutcome, PipelineDecision
from pipeline.runner import RunnerGuardrails, run_job
from pipeline.state import JobStatus, apply_plan, apply_plan_validation, load_state, mark_terminal, set_render_summary, set_requested_user_input


def _job_request() -> dict:
    return {
        "primary_url": "https://example.com/reference.mp4",
        "sources": [{"label": 1, "url": "https://example.com/source.mp4"}],
        "prompt": "Make a polished highlight edit",
        "requirements_state": {},
    }


def _job_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def _cleanup(job_id: str) -> None:
    shutil.rmtree(Path("tmp") / "jobs" / job_id, ignore_errors=True)


def _render_response(job_id: str, status: str) -> dict:
    return {
        "success": True,
        "url": "https://example.com/render.mp4",
        "render_id": "render-123",
        "status": status,
        "project_id": job_id,
        "intent_mode": "video",
        "refit_mode": "crop_center",
        "output_mode": "crop_to_9x16",
        "render_aspect": "9:16",
        "preview_url": f"/files/{job_id}/outputs/master_16x9.mp4",
        "preview_mode": "video",
        "warnings": [],
        "errors": [],
    }


class _SequenceDecisionEngine:
    def __init__(self, outcomes, *, repair_outcomes=None):
        self._outcomes = list(outcomes)
        self._repair_outcomes = list(repair_outcomes or [])

    def decide(self, state):
        if self._outcomes:
            return self._outcomes.pop(0)
        return DecisionOutcome(
            decision=PipelineDecision(
                next_action="finish",
                confidence=0.95,
                rationale="done",
                parameters={},
            )
        )

    def repair_decide(self, state, *, error, invalid_payload=None):
        if self._repair_outcomes:
            return self._repair_outcomes.pop(0)
        return DecisionOutcome(
            decision=None,
            source="repair_invalid",
            error=error,
            invalid_payload=invalid_payload,
            repair_attempted=True,
        )


class _FakeExecutor:
    def __init__(self, *, validation_scores=None, apply_pending_feedback_on_revise=False):
        self.actions = []
        self.validation_scores = list(validation_scores or [])
        self.apply_pending_feedback_on_revise = apply_pending_feedback_on_revise

    def execute(self, ctx, decision):
        self.actions.append(decision.next_action)
        if decision.next_action == "run_analysis":
            ctx.state.analysis_available = True
            ctx.state.analysis = {"scenes": [{"scene_id": 1, "duration": 2.0}]}
            ctx.state.analysis_summary = "analysis ready"
            return
        if decision.next_action == "generate_plan":
            apply_plan(
                ctx.state,
                {
                    "planning_strategy": "test_plan",
                    "target_pacing": "medium",
                    "selected_segments": [{"label": "seg_1", "start": 0.0, "end": 2.0}],
                    "support_segments": [],
                },
                overlay_plan={"overlays": [], "text_segments": [], "warnings": []},
                audio_plan={},
                render_spec={},
                needs_validation=True,
            )
            return
        if decision.next_action == "validate_plan":
            score = self.validation_scores.pop(0) if self.validation_scores else 0.92
            apply_plan_validation(
                ctx.state,
                {
                    "validation_score": score,
                    "warnings": [],
                    "checks": {},
                    "rewrite_actions": [],
                    "recommendations": [],
                },
            )
            return
        if decision.next_action == "revise_plan":
            ctx.state.revision_attempts += 1
            ctx.state.plan_needs_validation = True
            ctx.state.plan_validation = {}
            ctx.state.plan_validation_score = None
            if self.apply_pending_feedback_on_revise:
                ctx.state.applied_edit_requests = list(ctx.state.requirements.get("edit_requests") or [])
            return
        if decision.next_action in {"render_preview", "render_final"}:
            ctx.state.render_attempts += 1
            set_render_summary(
                ctx.state,
                {
                    "url": "https://example.com/render.mp4",
                    "preview_url": f"/files/{ctx.job_id}/outputs/master_16x9.mp4",
                    "preview_mode": "video",
                },
                final_response=_render_response(ctx.job_id, "rendered") if decision.next_action == "render_final" else None,
            )
            return
        if decision.next_action == "request_user_input":
            set_requested_user_input(
                ctx.state,
                {
                    "reason": decision.parameters.get("reason", "clarification_required"),
                    "question": decision.parameters.get("question", decision.rationale),
                },
            )
            return
        if decision.next_action == "abort_job":
            mark_terminal(
                ctx.state,
                JobStatus.ABORTED,
                reason=decision.parameters.get("reason") or decision.rationale,
            )
            return
        if decision.next_action == "finish":
            ctx.state.final_response = _render_response(ctx.job_id, "done")
            mark_terminal(ctx.state, JobStatus.SUCCEEDED, final_response=ctx.state.final_response)
            return
        raise AssertionError(f"Unexpected action: {decision.next_action}")


def test_runner_completes_successful_controller_loop():
    job_id = _job_id("runner-success")
    try:
        engine = _SequenceDecisionEngine(
            [
                DecisionOutcome(PipelineDecision(next_action="run_analysis", confidence=0.9, rationale="analyze", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="generate_plan", confidence=0.9, rationale="plan", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="validate_plan", confidence=0.9, rationale="validate", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="revise_plan", confidence=0.9, rationale="revise", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="validate_plan", confidence=0.9, rationale="validate again", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="render_final", confidence=0.95, rationale="render", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="finish", confidence=0.95, rationale="done", parameters={})),
            ]
        )
        executor = _FakeExecutor(validation_scores=[0.42, 0.91])

        result = run_job(job_id, _job_request(), decision_engine=engine, executor=executor)

        assert result["success"] is True
        assert result["status"] == "done"
        assert executor.actions == [
            "run_analysis",
            "generate_plan",
            "validate_plan",
            "revise_plan",
            "validate_plan",
            "render_final",
            "finish",
        ]
    finally:
        _cleanup(job_id)


def test_runner_handles_repeated_invalid_controller_output():
    job_id = _job_id("runner-invalid")
    try:
        engine = _SequenceDecisionEngine(
            [
                DecisionOutcome(
                    decision=None,
                    source="invalid",
                    error="invalid json",
                ),
            ],
            repair_outcomes=[
                DecisionOutcome(
                    decision=None,
                    source="repair_invalid",
                    error="repair failed",
                    repair_attempted=True,
                )
            ],
        )
        executor = _FakeExecutor()

        result = run_job(job_id, _job_request(), decision_engine=engine, executor=executor)

        assert result["success"] is False
        assert result["status"] == "failed"
        assert result["controller_status"] == "failed"
        assert executor.actions == []
    finally:
        _cleanup(job_id)


def test_runner_enforces_final_action_confidence_guardrail():
    job_id = _job_id("runner-confidence")
    try:
        engine = _SequenceDecisionEngine(
            [
                DecisionOutcome(PipelineDecision(next_action="run_analysis", confidence=0.9, rationale="analyze", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="generate_plan", confidence=0.9, rationale="plan", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="render_final", confidence=0.2, rationale="too early", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="render_final", confidence=0.95, rationale="render now", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="finish", confidence=0.95, rationale="finish", parameters={})),
            ]
        )
        executor = _FakeExecutor(validation_scores=[0.93])

        result = run_job(job_id, _job_request(), decision_engine=engine, executor=executor)

        assert result["success"] is True
        assert executor.actions[2] == "validate_plan"
        assert "render_final" in executor.actions
    finally:
        _cleanup(job_id)


def test_runner_stops_after_max_revision_loops():
    job_id = _job_id("runner-revisions")
    try:
        engine = _SequenceDecisionEngine(
            [
                DecisionOutcome(PipelineDecision(next_action="run_analysis", confidence=0.9, rationale="analyze", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="generate_plan", confidence=0.9, rationale="plan", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="validate_plan", confidence=0.9, rationale="validate", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="revise_plan", confidence=0.9, rationale="revise 1", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="validate_plan", confidence=0.9, rationale="validate 2", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="revise_plan", confidence=0.9, rationale="revise 2", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="validate_plan", confidence=0.9, rationale="validate 3", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="revise_plan", confidence=0.9, rationale="revise 3", parameters={})),
            ]
        )
        executor = _FakeExecutor(validation_scores=[0.4, 0.35, 0.3])
        guardrails = RunnerGuardrails(max_revision_attempts=2, max_stalled_revision_attempts=99)

        result = run_job(job_id, _job_request(), decision_engine=engine, executor=executor, guardrails=guardrails)

        assert result["success"] is False
        assert result["status"] == "needs_user_input"
        assert executor.actions[-1] == "request_user_input"
    finally:
        _cleanup(job_id)


def test_runner_requests_input_when_revisions_repeat_without_plan_change():
    job_id = _job_id("runner-stalled")
    try:
        engine = _SequenceDecisionEngine(
            [
                DecisionOutcome(PipelineDecision(next_action="run_analysis", confidence=0.9, rationale="analyze", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="generate_plan", confidence=0.9, rationale="plan", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="validate_plan", confidence=0.9, rationale="validate", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="revise_plan", confidence=0.9, rationale="revise 1", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="validate_plan", confidence=0.9, rationale="validate 2", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="revise_plan", confidence=0.9, rationale="revise 2", parameters={})),
            ]
        )
        executor = _FakeExecutor(validation_scores=[0.4, 0.35])
        guardrails = RunnerGuardrails(max_revision_attempts=5, max_stalled_revision_attempts=2)

        result = run_job(job_id, _job_request(), decision_engine=engine, executor=executor, guardrails=guardrails)
        state = load_state(str(Path("tmp") / "jobs" / job_id))

        assert result["success"] is False
        assert result["status"] == "needs_user_input"
        assert "without a meaningful change" in result["error"].lower()
        assert executor.actions == [
            "run_analysis",
            "generate_plan",
            "validate_plan",
            "revise_plan",
            "validate_plan",
            "revise_plan",
        ]
        assert state is not None
        assert state.stalled_revision_count == 2
        assert any(warning["code"] == "STALLED_REVISION_LOOP" for warning in state.warnings)
    finally:
        _cleanup(job_id)


def test_runner_supports_abort_flow():
    job_id = _job_id("runner-abort")
    try:
        engine = _SequenceDecisionEngine(
            [
                DecisionOutcome(
                    PipelineDecision(
                        next_action="abort_job",
                        confidence=0.99,
                        rationale="materials are unusable",
                        parameters={"reason": "unusable_material"},
                    )
                )
            ]
        )
        executor = _FakeExecutor()

        result = run_job(job_id, _job_request(), decision_engine=engine, executor=executor)

        assert result["success"] is False
        assert result["status"] == "aborted"
        assert executor.actions == ["abort_job"]
    finally:
        _cleanup(job_id)


def test_runner_supports_request_user_input_flow():
    job_id = _job_id("runner-input")
    try:
        engine = _SequenceDecisionEngine(
            [
                DecisionOutcome(
                    PipelineDecision(
                        next_action="request_user_input",
                        confidence=0.9,
                        rationale="Need clarification",
                        parameters={"reason": "missing_brief", "question": "What style direction should I prioritize?"},
                    )
                )
            ]
        )
        executor = _FakeExecutor()

        result = run_job(job_id, _job_request(), decision_engine=engine, executor=executor)

        assert result["success"] is False
        assert result["status"] == "needs_user_input"
        assert executor.actions == ["request_user_input"]
        assert "style direction" in result["error"]
    finally:
        _cleanup(job_id)


def test_runner_revises_before_render_when_pending_edit_requests_exist():
    job_id = _job_id("runner-pending-edit")
    try:
        request = _job_request()
        request["requirements_state"] = {
            "edit_requests": ["edit: make it less cluttered in the middle"]
        }
        engine = _SequenceDecisionEngine(
            [
                DecisionOutcome(PipelineDecision(next_action="run_analysis", confidence=0.9, rationale="analyze", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="generate_plan", confidence=0.9, rationale="plan", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="validate_plan", confidence=0.9, rationale="validate", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="render_final", confidence=0.95, rationale="render too early", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="validate_plan", confidence=0.9, rationale="validate patched", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="render_final", confidence=0.95, rationale="render patched", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="finish", confidence=0.95, rationale="done", parameters={})),
            ]
        )
        executor = _FakeExecutor(validation_scores=[0.9, 0.93], apply_pending_feedback_on_revise=True)

        result = run_job(job_id, request, decision_engine=engine, executor=executor)

        assert result["success"] is True
        assert executor.actions == [
            "run_analysis",
            "generate_plan",
            "validate_plan",
            "revise_plan",
            "validate_plan",
            "render_final",
            "finish",
        ]
    finally:
        _cleanup(job_id)


def test_runner_blocks_pending_unapplied_edits_without_finishing():
    job_id = _job_id("runner-blocked-edits")
    try:
        request = _job_request()
        request["requirements_state"] = {
            "edit_requests": ["edit: make it less cluttered in the middle"]
        }
        engine = _SequenceDecisionEngine(
            [
                DecisionOutcome(PipelineDecision(next_action="run_analysis", confidence=0.9, rationale="analyze", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="generate_plan", confidence=0.9, rationale="plan", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="validate_plan", confidence=0.9, rationale="validate", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="render_final", confidence=0.95, rationale="render", parameters={})),
            ]
        )
        executor = _FakeExecutor()
        guardrails = RunnerGuardrails(max_revision_attempts=0)

        result = run_job(job_id, request, decision_engine=engine, executor=executor, guardrails=guardrails)

        assert result["success"] is False
        assert result["status"] == "needs_user_input"
        assert result["controller_status"] == "blocked_by_unapplied_edits"
        assert result["controller_status_category"] == "blocked"
        assert result["controller_status"] != "finished"
    finally:
        _cleanup(job_id)


def test_runner_marks_revision_limit_exhausted_when_plan_stays_weak():
    job_id = _job_id("runner-revision-limit")
    try:
        engine = _SequenceDecisionEngine(
            [
                DecisionOutcome(PipelineDecision(next_action="run_analysis", confidence=0.9, rationale="analyze", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="generate_plan", confidence=0.9, rationale="plan", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="validate_plan", confidence=0.9, rationale="validate", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="revise_plan", confidence=0.9, rationale="revise", parameters={})),
            ]
        )
        executor = _FakeExecutor(validation_scores=[0.32])
        guardrails = RunnerGuardrails(max_revision_attempts=0)

        result = run_job(job_id, _job_request(), decision_engine=engine, executor=executor, guardrails=guardrails)

        assert result["success"] is False
        assert result["status"] == "needs_user_input"
        assert result["controller_status"] == "revision_limit_exhausted"
        assert result["controller_status_category"] == "blocked"
    finally:
        _cleanup(job_id)


def test_runner_blocks_render_until_validation_exists():
    job_id = _job_id("runner-missing-validation")
    try:
        engine = _SequenceDecisionEngine(
            [
                DecisionOutcome(PipelineDecision(next_action="run_analysis", confidence=0.9, rationale="analyze", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="generate_plan", confidence=0.9, rationale="plan", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="render_final", confidence=0.95, rationale="render too early", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="render_final", confidence=0.95, rationale="render now", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="finish", confidence=0.95, rationale="finish", parameters={})),
            ]
        )
        executor = _FakeExecutor(validation_scores=[0.93])

        result = run_job(job_id, _job_request(), decision_engine=engine, executor=executor)

        assert result["success"] is True
        assert executor.actions[2] == "validate_plan"
        assert executor.actions[3] == "render_final"
    finally:
        _cleanup(job_id)


def test_runner_blocks_render_when_validation_score_is_too_low():
    job_id = _job_id("runner-low-validation")
    try:
        engine = _SequenceDecisionEngine(
            [
                DecisionOutcome(PipelineDecision(next_action="run_analysis", confidence=0.9, rationale="analyze", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="generate_plan", confidence=0.9, rationale="plan", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="validate_plan", confidence=0.9, rationale="validate", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="render_final", confidence=0.95, rationale="render weak plan", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="validate_plan", confidence=0.95, rationale="validate revised", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="render_final", confidence=0.95, rationale="render revised", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="finish", confidence=0.95, rationale="finish", parameters={})),
            ]
        )
        executor = _FakeExecutor(validation_scores=[0.41, 0.93])

        result = run_job(job_id, _job_request(), decision_engine=engine, executor=executor)

        assert result["success"] is True
        assert executor.actions[3] == "revise_plan"
        assert "render_final" in executor.actions
    finally:
        _cleanup(job_id)


def test_decision_trace_entries_accumulate_with_step_indexes():
    job_id = _job_id("runner-trace")
    try:
        engine = _SequenceDecisionEngine(
            [
                DecisionOutcome(PipelineDecision(next_action="run_analysis", confidence=0.9, rationale="analyze", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="generate_plan", confidence=0.9, rationale="plan", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="validate_plan", confidence=0.9, rationale="validate", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="render_final", confidence=0.95, rationale="render", parameters={})),
                DecisionOutcome(PipelineDecision(next_action="finish", confidence=0.95, rationale="finish", parameters={})),
            ]
        )
        executor = _FakeExecutor(validation_scores=[0.94])

        result = run_job(job_id, _job_request(), decision_engine=engine, executor=executor)
        state = load_state(str(Path("tmp") / "jobs" / job_id))

        assert result["success"] is True
        assert result["decision_trace_count"] == 5
        assert state is not None
        assert len(state.decision_trace) == 5
        assert [entry.step_index for entry in state.decision_trace] == [1, 2, 3, 4, 5]
        assert (Path("tmp") / "jobs" / job_id / "decision_trace.json").exists()
    finally:
        _cleanup(job_id)
