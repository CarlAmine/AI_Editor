from ai_editor.semantic_edit.layer_stack import build_layer_stack
from ai_editor.semantic_edit.schemas import ObjectFrameState, TrackedObject


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
