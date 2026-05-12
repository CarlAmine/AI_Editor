import shutil
from pathlib import Path
from uuid import uuid4

from ai_editor.semantic_edit.synthetic_objects import generate_synthetic_object_video
from ai_editor.semantic_edit.template_integration import attach_semantic_graph_to_template
from ai_editor.vision_template.schemas import CropSpec, EditSlot, EditTemplate, GlobalStyle, MotionSpec
from ai_editor.vision_template.renderer_adapter import build_render_spec_from_vision_template
from ai_editor.vision_template.schemas import SlotMapping, SlotMappingItem


def test_semantic_metadata_attaches_to_edit_template_slots():
    tmp_dir = Path("tmp") / "tests" / f"semantic-template-{uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    try:
        _video_path, graph = generate_synthetic_object_video(str(tmp_dir), "overlay_appears", fps=8)
        template = EditTemplate(
            version="0.1",
            fps=8.0,
            total_duration=graph.duration,
            slots=[
                EditSlot(
                    slot_id=1,
                    start=0.0,
                    end=graph.duration,
                    duration=graph.duration,
                    motion=MotionSpec(kind="static", confidence=1.0),
                    crop=CropSpec(),
                )
            ],
            global_style=GlobalStyle(avg_slot_duration=graph.duration, rhythm=[graph.duration], pacing_label="medium", dominant_transition="cut"),
        )
        attach_semantic_graph_to_template(template, graph)
        assert template.slots[0].visible_objects
        assert "dominant_object_labels" in template.slots[0].semantic_metadata
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_semantic_metadata_survives_template_json_and_render_transfer():
    tmp_dir = Path("tmp") / "tests" / f"semantic-template-roundtrip-{uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    try:
        video_path, graph = generate_synthetic_object_video(str(tmp_dir), "overlay_appears", fps=8)
        template = EditTemplate(
            version="0.1",
            fps=8.0,
            total_duration=graph.duration,
            slots=[
                EditSlot(
                    slot_id=1,
                    start=0.0,
                    end=graph.duration,
                    duration=graph.duration,
                    motion=MotionSpec(kind="static", confidence=1.0),
                    crop=CropSpec(),
                )
            ],
            global_style=GlobalStyle(avg_slot_duration=graph.duration, rhythm=[graph.duration], pacing_label="medium", dominant_transition="cut"),
        )
        attach_semantic_graph_to_template(template, graph)
        template_path = tmp_dir / "template.json"
        template.to_json_file(template_path)

        loaded = EditTemplate.from_json_file(template_path)
        canonical_timeline, _overlay_timing, _edit_summary = build_render_spec_from_vision_template(
            loaded,
            SlotMapping(items=[SlotMappingItem(slot_id=1, clip_path=video_path)]),
            source_artifacts={},
            requirements={"generation_mode": "vision_template_learning"},
        )

        assert loaded.slots[0].visible_objects
        assert loaded.slots[0].semantic_metadata["dominant_object_labels"]
        assert canonical_timeline[0]["metadata"]["semantic_metadata"]["dominant_object_labels"]
        assert canonical_timeline[0]["visible_layers"]
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
