import json
import shutil
from pathlib import Path

from pipeline.smoke import run_smoke_job
from pipeline.state import load_state


def test_smoke_job_runs_end_to_end_with_fake_providers():
    payload = run_smoke_job()
    job_id = payload["job_id"]
    job_dir = Path(payload["job_dir"])
    try:
        assert payload["result"]["success"] is True
        assert payload["result"]["status"] == "done"
        assert payload["state_exists"] is True
        assert payload["artifacts_exists"] is True
        assert payload["decision_trace_exists"] is True

        state = load_state(str(job_dir))
        assert state is not None
        assert state.status.value == "succeeded"
        assert state.controller_status.value == "finished"
        assert state.render_summary.get("url") == f"/files/{job_id}/outputs/master_16x9.mp4"

        artifacts = json.loads(Path(payload["artifacts_path"]).read_text(encoding="utf-8"))
        assert "decision.trace" in artifacts
        assert "render.output_url" in artifacts
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)
