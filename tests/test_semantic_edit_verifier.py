import shutil
from pathlib import Path
from uuid import uuid4

from ai_editor.semantic_edit.synthetic_objects import generate_synthetic_object_video
from ai_editor.semantic_edit.verifier import verify_object_edit


def test_verifier_passes_when_chair_changes():
    tmp_dir = Path("tmp") / "tests" / f"semantic-verify-pass-{uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    try:
        _before_path, before_graph = generate_synthetic_object_video(str(tmp_dir / "before"), "static_chair", fps=8)
        _after_path, after_graph = generate_synthetic_object_video(str(tmp_dir / "after"), "chair_replaced", fps=8)
        verification = verify_object_edit(before_graph, after_graph, "change the chair")
        assert verification.target_object_label == "chair"
        assert verification.score >= 0.6
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_verifier_flags_unintended_person_change_during_chair_edit():
    tmp_dir = Path("tmp") / "tests" / f"semantic-verify-fail-{uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    try:
        _before_path, before_graph = generate_synthetic_object_video(str(tmp_dir / "before"), "person_and_chair", fps=8)
        _after_path, after_graph = generate_synthetic_object_video(str(tmp_dir / "after"), "chair_occluded", fps=8)
        verification = verify_object_edit(before_graph, after_graph, "change the chair")
        assert verification.unintended_changes or verification.warnings
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
