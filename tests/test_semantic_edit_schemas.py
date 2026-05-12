import shutil
from pathlib import Path
from uuid import uuid4

from ai_editor.semantic_edit.schemas import ObjectFrameState, SemanticEditVerification, SemanticVideoGraph, TrackedObject, VideoLayer


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
