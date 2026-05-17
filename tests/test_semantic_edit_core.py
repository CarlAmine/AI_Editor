import shutil
from pathlib import Path
from uuid import uuid4

from ai_editor.semantic_edit.layer_stack import build_layer_stack
from ai_editor.semantic_edit.object_detector import detect_objects
from ai_editor.semantic_edit.object_tracker import track_objects
from ai_editor.semantic_edit.schemas import (
    ObjectFrameState,
    SemanticEditVerification,
    SemanticVideoGraph,
    TrackedObject,
    VideoLayer,
)
from ai_editor.vision_template.frame_sampler import sample_video_frames
from tests.helpers.semantic_fixtures import generate_synthetic_object_video


def test_synthetic_color_detector_finds_chair():
    tmp_dir = Path("tmp") / "tests" / f"semantic-detector-{uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    try:
        video_path, _graph = generate_synthetic_object_video(str(tmp_dir), "static_chair", fps=8)
        sampled = sample_video_frames(video_path, fps=8.0, size=96)
        detections = detect_objects(sampled.frames, sampled.timestamps, text_queries=["chair"], backend="synthetic_color")
        assert any(detection.label == "chair" for detection in detections)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


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


def test_layer_stack_includes_background_and_object_layers():
    track = TrackedObject(
        object_id="chair_1",
        label="chair",
        confidence=0.9,
        first_seen=0.0,
        last_seen=2.0,
        track=[ObjectFrameState(timestamp=0.0, bbox=[0.1, 0.1, 0.2, 0.2], confidence=0.9, visible=True, occlusion_score=0.0)],
        mask_available=False,
        stable_identity_score=0.8,
        attributes={},
    )
    layers = build_layer_stack([track])
    assert any(layer.layer_type == "background" for layer in layers)
    assert any(layer.object_id == "chair_1" for layer in layers)


def test_semantic_graph_schema_roundtrip():
    tmp_dir = Path("tmp") / "tests" / f"semantic-schema-{uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    try:
        graph = SemanticVideoGraph(
            video_path="video.mp4",
            sampled_fps=8.0,
            duration=3.0,
            objects=[
                TrackedObject(
                    object_id="chair_1",
                    label="chair",
                    confidence=0.9,
                    first_seen=0.0,
                    last_seen=2.5,
                    track=[ObjectFrameState(timestamp=0.0, bbox=[0.1, 0.2, 0.3, 0.4], confidence=0.9, visible=True, occlusion_score=0.0)],
                    mask_available=False,
                    stable_identity_score=0.8,
                    attributes={},
                )
            ],
            layers=[
                VideoLayer(
                    layer_id="background_1",
                    layer_type="background",
                    label="background",
                    object_id=None,
                    start=0.0,
                    end=3.0,
                    region="full",
                    editable=False,
                    confidence=1.0,
                    metadata={},
                )
            ],
            warnings=["ok"],
        )
        path = tmp_dir / "semantic_graph.json"
        graph.to_json_file(path)
        loaded = SemanticVideoGraph.from_json_file(path)
        assert loaded.objects[0].label == "chair"

        verification = SemanticEditVerification(
            passed=True,
            score=0.9,
            target_object_label="chair",
            target_object_ids=["chair_1"],
            changed_objects=["chair_1"],
            preserved_objects=[],
            unintended_changes=[],
            evidence={},
            warnings=[],
        )
        verify_path = tmp_dir / "verification.json"
        verification.to_json_file(verify_path)
        loaded_verification = SemanticEditVerification.from_json_file(verify_path)
        assert loaded_verification.passed is True
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
