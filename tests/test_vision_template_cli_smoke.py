import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4
import shutil


def test_vision_template_cli_smoke_demo():
    out_dir = Path("tmp") / "tests" / f"vision-cli-{uuid4().hex[:8]}"
    try:
        cmd = [
            sys.executable,
            "-m",
            "ai_editor.vision_template.cli",
            "smoke-demo",
            "--out",
            str(out_dir),
            "--num-slots",
            "4",
            "--epochs",
            "2",
            "--fps",
            "8",
            "--size",
            "96",
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)

        assert (out_dir / "edit_template.json").exists()
        assert (out_dir / "canonical_timeline.json").exists()
        assert (out_dir / "training_summary.json").exists()
        assert (out_dir / "metrics.json").exists()
        metrics = json.loads((out_dir / "metrics.json").read_text(encoding="utf-8"))
        assert "slot_count_error" in metrics
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)
