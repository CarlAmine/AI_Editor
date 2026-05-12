import shutil
from pathlib import Path
from uuid import uuid4

from ai_editor.semantic_edit.synthetic_objects import generate_synthetic_object_video


def test_chair_disappears_produces_object_removed_like_event():
    tmp_dir = Path("tmp") / "tests" / f"semantic-events-{uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    try:
        _video_path, graph = generate_synthetic_object_video(str(tmp_dir), "chair_disappears", fps=8)
        event_types = {event.event_type for event in graph.edit_events}
        assert "object_removed" in event_types or "object_disappeared" in event_types
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_chair_occluded_does_not_classify_permanent_removal():
    tmp_dir = Path("tmp") / "tests" / f"semantic-occlusion-{uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    try:
        _video_path, graph = generate_synthetic_object_video(str(tmp_dir), "chair_occluded", fps=8)
        chair_events = [event.event_type for event in graph.edit_events if event.object_id == "chair_1"]
        assert "object_removed" not in chair_events
        assert "object_disappeared" not in chair_events
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
