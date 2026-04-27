import shutil
from pathlib import Path
from uuid import uuid4

from ai_editor.vision_template.schemas import (
    CropSpec,
    EditSlot,
    EditTemplate,
    GlobalStyle,
    MotionSpec,
    OverlaySpec,
    SlotMapping,
    SlotMappingItem,
)


def _temp_dir(name: str) -> Path:
    path = Path("tmp") / "tests" / f"{name}-{uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_edit_template_schema_roundtrip():
    tmp_dir = _temp_dir("vision-schema")
    try:
        template = EditTemplate(
            version="0.1",
            source_reference="ref.mp4",
            fps=8.0,
            total_duration=3.0,
            slots=[
                EditSlot(
                    slot_id=1,
                    start=0.0,
                    end=1.2,
                    duration=1.2,
                    boundary_confidence=0.8,
                    transition_in="cut",
                    transition_out="fade",
                    motion=MotionSpec(kind="zoom_in", confidence=0.7, keyframes=[{"t": 0.0}, {"t": 1.0}]),
                    crop=CropSpec(x=0.0, y=0.0, width=1.0, height=1.0),
                    overlay=OverlaySpec(has_overlay=True, region="top", start_rel=0.0, end_rel=1.0, mask_confidence=0.9),
                    style_vector=[0.1, 0.2],
                ),
                EditSlot(
                    slot_id=2,
                    start=1.2,
                    end=3.0,
                    duration=1.8,
                    transition_in="fade",
                    transition_out="cut",
                    motion=MotionSpec(kind="static", confidence=0.9, keyframes=[]),
                    crop=CropSpec(),
                    overlay=None,
                    style_vector=[0.3, 0.4],
                ),
            ],
            global_style=GlobalStyle(
                avg_slot_duration=1.5,
                rhythm=[1.2, 1.8],
                pacing_label="medium",
                dominant_transition="cut",
                aspect_ratio="16:9",
                style_embedding=[0.5, 0.6],
            ),
            warnings=["experimental"],
        )
        path = tmp_dir / "edit_template.json"
        template.to_json_file(path)
        loaded = EditTemplate.from_json_file(path)

        assert len(loaded.slots) == 2
        assert loaded.slots[0].duration == 1.2
        assert loaded.global_style.rhythm == [1.2, 1.8]
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_slot_mapping_roundtrip():
    tmp_dir = _temp_dir("vision-slot-map")
    try:
        mapping = SlotMapping(items=[SlotMappingItem(slot_id=1, clip_id="clip_1", clip_path="clip.mp4")])
        path = tmp_dir / "slot_mapping.json"
        mapping.to_json_file(path)
        loaded = SlotMapping.from_json_file(path)

        assert loaded.items[0].slot_id == 1
        assert loaded.items[0].clip_id == "clip_1"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
