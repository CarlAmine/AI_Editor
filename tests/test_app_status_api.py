import shutil
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

import app as app_module
from app import TMP_JOBS_DIR, app
from pipeline.state import (
    ControllerStatus,
    JobStatus,
    clear_requested_user_input,
    mark_terminal,
    new_state,
    record_decision,
    save_state,
    set_controller_status,
    set_latest_user_feedback,
    set_provider_status,
    set_requested_user_input,
)

client = TestClient(app)


def _job_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def _job_dir(job_id: str) -> Path:
    return TMP_JOBS_DIR / job_id


def _cleanup(job_id: str) -> None:
    shutil.rmtree(_job_dir(job_id), ignore_errors=True)


def _state(job_id: str):
    return new_state(
        job_id,
        input_summary={"primary_url": "https://example.com/ref.mp4", "sources_count": 1},
        requirements={"prompt": "Make a polished highlight edit"},
    )


def test_status_endpoint_reports_running_state():
    job_id = _job_id("api-running")
    try:
        state = _state(job_id)
        set_controller_status(state, ControllerStatus.PLANNING, detail="Generating the first plan.")
        set_provider_status(
            state,
            {
                "ready": True,
                "providers": {
                    "model_provider": {
                        "name": "model_provider",
                        "required": True,
                        "configured": True,
                        "ready": True,
                        "code": "",
                        "message": "ready",
                        "detail": {"path": "C:/secret/provider.json"},
                    }
                },
            },
        )
        save_state(str(_job_dir(job_id)), state)

        response = client.get(f"/jobs/{job_id}/status")

        assert response.status_code == 200
        payload = response.json()
        assert payload["controller_status"] == "planning"
        assert payload["controller_status_category"] == "working"
        assert payload["provider_status"]["providers"]["model_provider"]["ready"] is True
        assert "detail" not in payload["provider_status"]["providers"]["model_provider"]
    finally:
        _cleanup(job_id)


def test_status_endpoint_reports_blocked_state_without_treating_it_as_success():
    job_id = _job_id("api-blocked")
    try:
        state = _state(job_id)
        set_requested_user_input(
            state,
            {
                "reason": "pending_user_feedback",
                "question": "Please confirm which change matters most.",
            },
        )
        save_state(str(_job_dir(job_id)), state)

        response = client.get(f"/jobs/{job_id}/status")

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is False
        assert payload["controller_status"] == "blocked_by_unapplied_edits"
        assert payload["controller_status_category"] == "blocked"
    finally:
        _cleanup(job_id)


def test_status_endpoint_reports_failed_state_and_sanitized_trace():
    job_id = _job_id("api-failed")
    try:
        state = _state(job_id)
        record_decision(
            state,
            next_action="render_final",
            confidence=0.88,
            rationale="Use api_key=secret and C:\\private\\file.mp4",
            parameters={
                "api_key": "secret-value",
                "asset_path": "C:\\private\\file.mp4",
            },
        )
        mark_terminal(
            state,
            JobStatus.FAILED,
            reason="The render provider timed out.",
            code="RENDER_PROVIDER_TIMEOUT",
            detail={"exception": "TimeoutError('boom')"},
        )
        save_state(str(_job_dir(job_id)), state)

        response = client.get(f"/jobs/{job_id}/status", params={"include_trace": "true"})

        assert response.status_code == 200
        payload = response.json()
        assert payload["controller_status"] == "failed"
        assert payload["failure_code"] == "RENDER_PROVIDER_TIMEOUT"
        assert payload["decision_trace"][0]["parameters"]["api_key"] == "[redacted]"
        assert payload["decision_trace"][0]["parameters"]["asset_path"] == "[redacted_path]"
        assert payload["decision_trace"][0]["rationale"] == "[redacted]"
    finally:
        _cleanup(job_id)


def test_status_endpoint_reports_finished_state():
    job_id = _job_id("api-finished")
    try:
        state = _state(job_id)
        mark_terminal(state, JobStatus.SUCCEEDED, final_response={"success": True, "status": "done"})
        save_state(str(_job_dir(job_id)), state)

        response = client.get(f"/jobs/{job_id}/status")

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["controller_status"] == "finished"
        assert payload["controller_status_category"] == "complete"
    finally:
        _cleanup(job_id)


def test_status_endpoint_returns_404_for_missing_job():
    response = client.get("/jobs/does-not-exist/status")

    assert response.status_code == 404


def test_provider_health_endpoint_returns_readiness_summary():
    response = client.get("/health/providers")

    assert response.status_code == 200
    payload = response.json()
    assert "ready" in payload
    assert "providers" in payload
    assert "model_provider" in payload["providers"]
    assert "render_provider" in payload["providers"]
    assert "drive_storage" in payload["providers"]


def test_process_video_url_surfaces_structured_provider_readiness_failure(monkeypatch):
    for key in ("HF_API_KEY", "OPENROUTER_API_KEY", "GROQ", "SHOTSTACK_KEY", "GOOGLE_APPLICATION_CREDENTIALS"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("DRIVE_AUTH_MODE", "oauth_user")
    monkeypatch.setenv("DRIVE_CLIENT_SECRET_FILE", str(Path("tmp") / "missing-drive-client-secret.json"))
    monkeypatch.setenv("DRIVE_TOKEN_FILE", str(Path("tmp") / "missing-drive-token.json"))

    response = client.post(
        "/process-video-url",
        json={
            "primary_url": "https://example.com/reference.mp4",
            "sources": [{"label": 1, "url": "https://example.com/source.mp4"}],
            "prompt": "Make a polished highlight edit",
            "requirements_state": {},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
    assert payload["status"] == "failed"
    assert payload["failure_code"] == "PROVIDER_READINESS_FAILED"
    assert payload["controller_status"] == "failed"


def test_resume_endpoint_continues_existing_waiting_job(monkeypatch):
    job_id = _job_id("api-resume")
    resumed_message = "Continue. Prioritize rendering the current plan."
    calls = []

    def fake_run_job(resume_job_id, payload):
        calls.append((resume_job_id, payload))
        state = app_module.load_state(str(_job_dir(job_id)))
        assert state is not None
        clear_requested_user_input(state)
        set_latest_user_feedback(state, resumed_message)
        state.requirements = payload["requirements_state"]
        state.request_payload = payload
        save_state(str(_job_dir(job_id)), state)
        return {
            "success": False,
            "status": "running",
            "project_id": resume_job_id,
            "job_status": "running",
            "controller_status": "initializing",
            "controller_status_category": "working",
            "waiting_for_user_input": False,
            "requested_user_input": {},
        }

    monkeypatch.setattr(app_module, "run_job", fake_run_job)

    try:
        state = _state(job_id)
        state.request_payload = {
            "primary_url": "https://example.com/ref.mp4",
            "sources": [{"label": 1, "url": "https://example.com/source.mp4"}],
            "prompt": "Make a polished highlight edit",
            "music_mode": "original",
            "requirements_state": {"edit_mode": "scene", "edit_requests": ["Initial direction"]},
        }
        set_requested_user_input(
            state,
            {
                "reason": "max_loop_iterations",
                "question": "Please confirm the next edit priority before I continue.",
            },
        )
        save_state(str(_job_dir(job_id)), state)

        response = client.post(f"/jobs/{job_id}/resume", json={"message": resumed_message})

        assert response.status_code == 200
        payload = response.json()
        assert payload["project_id"] == job_id
        assert payload["job_status"] == "running"
        assert payload["waiting_for_user_input"] is False
        assert calls and calls[0][0] == job_id
        assert calls[0][1]["requirements_state"]["edit_requests"][-1] == resumed_message
        assert calls[0][1]["requirements_state"]["latest_user_feedback"] == resumed_message

        reloaded = app_module.load_state(str(_job_dir(job_id)))
        assert reloaded is not None
        assert reloaded.waiting_for_user_input is False
        assert reloaded.requested_user_input == {}
        assert reloaded.latest_user_feedback == resumed_message
        assert reloaded.requirements["edit_requests"][-1] == resumed_message
        assert not (_job_dir(f"{job_id}-new")).exists()
    finally:
        _cleanup(job_id)
