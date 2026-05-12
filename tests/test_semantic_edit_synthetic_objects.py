import shutil
from pathlib import Path
from uuid import uuid4

from ai_editor.semantic_edit.synthetic_objects import generate_synthetic_object_video


def test_synthetic_static_chair_video_produces_chair_object():
    tmp_dir = Path("tmp") / "tests" / f"semantic-synth-{uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    try:
        video_path, graph = generate_synthetic_object_video(str(tmp_dir), "static_chair", fps=8)
        assert Path(video_path).exists()
        assert (tmp_dir / "semantic_ground_truth.json").exists()
        assert any(obj.label == "chair" for obj in graph.objects)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
