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
        assert "boundary_precision_05s" in metrics
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_vision_template_cli_quality_demo_structural_smoke():
    out_dir = Path("tmp") / "tests" / f"vision-quality-{uuid4().hex[:8]}"
    try:
        cmd = [
            sys.executable,
            "-m",
            "ai_editor.vision_template.cli",
            "quality-demo",
            "--out",
            str(out_dir),
            "--num-slots",
            "4",
            "--pretrain-samples",
            "8",
            "--pretrain-epochs",
            "1",
            "--adapt-epochs",
            "3",
            "--fps",
            "8",
            "--size",
            "96",
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        assert (out_dir / "edit_template.json").exists()
        assert (out_dir / "ground_truth_template.json").exists()
        assert (out_dir / "boundary_debug.json").exists()
        assert (out_dir / "metrics.json").exists()
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)
