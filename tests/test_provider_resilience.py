import shutil
from pathlib import Path
from uuid import uuid4

from pipeline.decision_engine import PipelineDecisionEngine
from pipeline.provider_errors import ProviderFailure
from pipeline.runner import run_job
from pipeline.smoke import SmokeDecisionEngine, SmokePipelineExecutor, build_smoke_request


def _job_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def _cleanup(job_id: str) -> None:
    shutil.rmtree(Path("tmp") / "jobs" / job_id, ignore_errors=True)


def _request() -> dict:
    return {
        "primary_url": "https://example.com/reference.mp4",
        "sources": [{"label": 1, "url": "https://example.com/source.mp4"}],
        "prompt": "Make a polished highlight edit",
        "requirements_state": {},
    }


class _NoOpExecutor:
    def execute(self, ctx, decision):
        raise AssertionError("Executor should not run when the controller provider fails.")


class _FailingSmokeExecutor(SmokePipelineExecutor):
    def _stage_shotstack_render(self, ctx):
        raise ProviderFailure(
            provider="render_provider",
            code="RENDER_PROVIDER_TIMEOUT",
            user_message="The render provider timed out during the smoke render.",
            detail={"provider": "smoke-render"},
            retryable=True,
        )
        
    def _stage_ffmpeg_render(self, ctx):
        raise ProviderFailure(
            provider="render_provider",
            code="RENDER_PROVIDER_TIMEOUT",
            user_message="The render provider timed out during the smoke render.",
            detail={"provider": "smoke-render"},
            retryable=True,
        )

def test_run_job_fails_fast_when_required_providers_are_not_configured(monkeypatch):
    job_id = _job_id("provider-config")
    try:
        for key in ("HF_API_KEY", "OPENROUTER_API_KEY", "GROQ", "SHOTSTACK_KEY", "GOOGLE_APPLICATION_CREDENTIALS"):
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("DRIVE_AUTH_MODE", "oauth_user")
        monkeypatch.setenv("DRIVE_CLIENT_SECRET_FILE", str(Path("tmp") / "missing-drive-client-secret.json"))
        monkeypatch.setenv("DRIVE_TOKEN_FILE", str(Path("tmp") / "missing-drive-token.json"))
        monkeypatch.setenv("RENDER_PROVIDER", "shotstack")

        result = run_job(job_id, _request())

        assert result["success"] is False
        assert result["status"] == "failed"
        assert result["failure_code"] == "PROVIDER_READINESS_FAILED"
        assert result["controller_status"] == "failed"
        assert result["provider_status"]["providers"]["model_provider"]["ready"] is False
        assert result["provider_status"]["providers"]["render_provider"]["ready"] is False
        assert result["provider_status"]["providers"]["drive_storage"]["ready"] is False
    finally:
        _cleanup(job_id)


def test_run_job_surfaces_model_provider_failure_cleanly():
    job_id = _job_id("provider-model")
    try:
        engine = PipelineDecisionEngine(
            json_client=lambda *args, **kwargs: (_ for _ in ()).throw(
                ProviderFailure(
                    provider="model_provider",
                    code="MODEL_PROVIDER_TIMEOUT",
                    user_message="The AI controller timed out while choosing the next action.",
                    detail={"attempt": 1},
                    retryable=True,
                )
            )
        )

        result = run_job(job_id, _request(), decision_engine=engine, executor=_NoOpExecutor())

        assert result["success"] is False
        assert result["status"] == "failed"
        assert result["failure_code"] == "MODEL_PROVIDER_TIMEOUT"
        assert result["controller_status"] == "failed"
        assert result["errors"][-1]["code"] == "MODEL_PROVIDER_TIMEOUT"
    finally:
        _cleanup(job_id)


def test_run_job_surfaces_render_provider_failure_cleanly():
    job_id = _job_id("provider-render")
    try:
        result = run_job(
            job_id,
            build_smoke_request(job_id),
            decision_engine=SmokeDecisionEngine(),
            executor=_FailingSmokeExecutor(),
        )

        assert result["success"] is False
        assert result["status"] == "failed"
        assert result["failure_code"] == "RENDER_PROVIDER_TIMEOUT"
        assert result["controller_status"] == "failed"
        assert result["error"] == "The render provider timed out during the smoke render."
    finally:
        _cleanup(job_id)
