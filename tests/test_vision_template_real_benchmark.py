import json
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from ai_editor.vision_template.real_benchmark import discover_real_benchmark_cases, run_real_benchmark_suite
from ai_editor.vision_template.synthetic_dataset import generate_synthetic_edit_sample


def _temp_dir(name: str) -> Path:
    path = Path("tmp") / "tests" / f"{name}-{uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _build_benchmark_case(root: Path, case_name: str = "example_001") -> Path:
    case_dir = root / case_name
    case_dir.mkdir(parents=True, exist_ok=True)
    synth_dir = case_dir / "_synth"
    synth_dir.mkdir(parents=True, exist_ok=True)
    reference_path, template = generate_synthetic_edit_sample(str(synth_dir), num_slots=3, fps=8, size=(96, 96), seed=7)
    shutil.copy(reference_path, case_dir / "reference.mp4")
    shutil.copy(synth_dir / "slot_mapping.json", case_dir / "slot_mapping.json")
    shutil.copy(synth_dir / "ground_truth_template.json", case_dir / "ground_truth_template.json")
    for clip_path in sorted(synth_dir.glob("replacement_*.mp4")):
        shutil.copy(clip_path, case_dir / clip_path.name)
    (case_dir / "notes.md").write_text("benchmark notes", encoding="utf-8")
    return case_dir


def test_benchmark_discovery_finds_cases():
    tmp_dir = _temp_dir("vision-real-discover")
    try:
        _build_benchmark_case(tmp_dir)
        cases = discover_real_benchmark_cases(str(tmp_dir))
        assert len(cases) == 1
        assert cases[0].case_id == "example_001"
        assert cases[0].ground_truth_template_path
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_missing_ground_truth_template_is_reported_clearly():
    tmp_dir = _temp_dir("vision-real-missing-gt")
    out_dir = _temp_dir("vision-real-missing-gt-out")
    try:
        case_dir = _build_benchmark_case(tmp_dir)
        (case_dir / "ground_truth_template.json").unlink()
        aggregate = run_real_benchmark_suite(str(tmp_dir), str(out_dir), {"epochs": 2, "fps": 8.0, "size": 96})
        assert aggregate["cases_failed"] == 1
        assert "Missing ground_truth_template.json" in aggregate["results"][0]["error"]
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        shutil.rmtree(out_dir, ignore_errors=True)


def test_invalid_slot_mapping_is_reported_clearly():
    tmp_dir = _temp_dir("vision-real-invalid-map")
    out_dir = _temp_dir("vision-real-invalid-map-out")
    try:
        case_dir = _build_benchmark_case(tmp_dir)
        slot_mapping_path = case_dir / "slot_mapping.json"
        payload = json.loads(slot_mapping_path.read_text(encoding="utf-8"))
        payload["items"] = payload["items"][:1]
        slot_mapping_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        aggregate = run_real_benchmark_suite(str(tmp_dir), str(out_dir), {"epochs": 2, "fps": 8.0, "size": 96})
        assert aggregate["cases_failed"] == 1
        assert "Missing slot mapping entries" in aggregate["results"][0]["error"]
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        shutil.rmtree(out_dir, ignore_errors=True)


def test_eval_real_cli_on_synthetic_benchmark_produces_outputs():
    tmp_dir = _temp_dir("vision-real-cli")
    out_dir = _temp_dir("vision-real-cli-out")
    try:
        _build_benchmark_case(tmp_dir)
        cmd = [
            sys.executable,
            "-m",
            "ai_editor.vision_template.cli",
            "eval-real",
            "--benchmark-dir",
            str(tmp_dir),
            "--out",
            str(out_dir),
            "--epochs",
            "3",
            "--fps",
            "8",
            "--size",
            "96",
            "--synthetic-pretrain",
            "true",
            "--synthetic-pretrain-samples",
            "8",
            "--synthetic-pretrain-epochs",
            "1",
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        case_out = out_dir / "example_001"
        assert (case_out / "predicted_edit_template.json").exists()
        assert (case_out / "canonical_timeline.json").exists()
        assert (case_out / "metrics.json").exists()
        assert (out_dir / "aggregate_metrics.json").exists()
        assert (out_dir / "report.md").exists()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        shutil.rmtree(out_dir, ignore_errors=True)
