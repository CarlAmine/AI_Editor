import shutil
from pathlib import Path
from uuid import uuid4

from ai_editor.semantic_edit.object_detector import detect_objects
from ai_editor.semantic_edit.object_tracker import track_objects
from ai_editor.semantic_edit.synthetic_objects import generate_synthetic_object_video
from ai_editor.vision_template.frame_sampler import sample_video_frames


def test_iou_tracker_preserves_chair_identity_across_frames():
    tmp_dir = Path("tmp") / "tests" / f"semantic-tracker-{uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    try:
        video_path, _graph = generate_synthetic_object_video(str(tmp_dir), "static_chair", fps=8)
        sampled = sample_video_frames(video_path, fps=8.0, size=96)
        detections = detect_objects(sampled.frames, sampled.timestamps, text_queries=["chair"], backend="synthetic_color")
        tracks = track_objects(detections, sampled.timestamps)
        chair_tracks = [track for track in tracks if track.label == "chair"]
        assert len(chair_tracks) == 1
        assert chair_tracks[0].stable_identity_score > 0.5
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
