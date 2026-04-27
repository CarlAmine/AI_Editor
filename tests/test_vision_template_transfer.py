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
