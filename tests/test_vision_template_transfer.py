import shutil
from pathlib import Path
from uuid import uuid4

from ai_editor.semantic_edit.synthetic_objects import generate_synthetic_object_video
from ai_editor.vision_template.schemas import CropSpec, EditSlot, EditTemplate, GlobalStyle, MotionSpec, SlotMapping, SlotMappingItem
from ai_editor.vision_template.transfer_template import apply_template_to_clips


def test_apply_template_to_clips_preserves_mapping_order_and_durations():
    template = EditTemplate(
        version="0.1",
        fps=8.0,
        total_duration=3.0,
        slots=[
            EditSlot(slot_id=1, start=0.0, end=1.0, duration=1.0, motion=MotionSpec(kind="static", confidence=1.0), crop=CropSpec()),
            EditSlot(slot_id=2, start=1.0, end=2.2, duration=1.2, motion=MotionSpec(kind="zoom_in", confidence=1.0), crop=CropSpec()),
            EditSlot(slot_id=3, start=2.2, end=3.0, duration=0.8, motion=MotionSpec(kind="pan_right", confidence=1.0), crop=CropSpec()),
        ],
        global_style=GlobalStyle(avg_slot_duration=1.0, rhythm=[1.0, 1.2, 0.8], pacing_label="medium", dominant_transition="cut"),
    )
    mapping = SlotMapping(
        items=[
            SlotMappingItem(slot_id=1, clip_id="clip_2"),
            SlotMappingItem(slot_id=2, clip_id="clip_1"),
            SlotMappingItem(slot_id=3, clip_id="clip_3"),
        ]
    )
    transfer = apply_template_to_clips(
        template,
        mapping,
        available_sources={"clip_1": "a.mp4", "clip_2": "b.mp4", "clip_3": "c.mp4"},
    )

    timeline = transfer["timeline"]
    assert len(timeline) == 3
    assert [row["video_src"] for row in timeline] == ["b.mp4", "a.mp4", "c.mp4"]
    assert [row["duration"] for row in timeline] == [1.0, 1.2, 0.8]


def test_apply_template_to_clips_rejects_duplicate_slot_mappings():
    template = EditTemplate(
        version="0.1",
        fps=8.0,
        total_duration=1.0,
        slots=[
            EditSlot(slot_id=1, start=0.0, end=1.0, duration=1.0, motion=MotionSpec(kind="static", confidence=1.0), crop=CropSpec()),
        ],
        global_style=GlobalStyle(avg_slot_duration=1.0, rhythm=[1.0], pacing_label="medium", dominant_transition="cut"),
    )
    mapping = SlotMapping(
        items=[
            SlotMappingItem(slot_id=1, clip_id="clip_a"),
            SlotMappingItem(slot_id=1, clip_id="clip_b"),
        ]
    )

    try:
        apply_template_to_clips(template, mapping, available_sources={"clip_a": "a.mp4", "clip_b": "b.mp4"})
        assert False, "duplicate slot mappings should raise"
    except ValueError as exc:
        assert "Duplicate slot mapping entries" in str(exc)


def test_apply_template_to_clips_preserves_semantic_metadata_and_warns_for_short_sources():
    tmp_dir = Path("tmp") / "tests" / f"vision-transfer-{uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    try:
        video_path, _graph = generate_synthetic_object_video(str(tmp_dir), "static_chair", fps=12, size=(96, 96), seed=3)
        template = EditTemplate(
            version="0.1",
            fps=8.0,
            total_duration=3.0,
            slots=[
                EditSlot(
                    slot_id=1,
                    start=0.0,
                    end=3.0,
                    duration=3.0,
                    motion=MotionSpec(kind="static", confidence=1.0),
                    crop=CropSpec(),
                    visible_objects=["chair_1"],
                    visible_layers=["object:chair_1"],
                    semantic_events=[{"event_type": "object_appeared", "object_id": "chair_1"}],
                    semantic_metadata={"dominant_object_labels": ["chair"], "object_constraints": {"preserve_non_target": True}},
                ),
            ],
            global_style=GlobalStyle(avg_slot_duration=3.0, rhythm=[3.0], pacing_label="medium", dominant_transition="cut"),
        )
        mapping = SlotMapping(items=[SlotMappingItem(slot_id=1, clip_path=str(video_path))])

        transfer = apply_template_to_clips(template, mapping)

        row = transfer["timeline"][0]
        assert transfer["warnings"]
        assert row["metadata"]["semantic_metadata"]["dominant_object_labels"] == ["chair"]
        assert row["metadata"]["object_constraints"]["preserve_non_target"] is True
        assert row["semantic_metadata"]["dominant_object_labels"] == ["chair"]
        assert row["visible_objects"] == ["chair_1"]
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
