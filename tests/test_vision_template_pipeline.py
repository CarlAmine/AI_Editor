import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import torch

from ai_editor.vision_template.decode_template import decode_edit_template
from ai_editor.vision_template.frame_sampler import SampledVideo, sample_video_frames
from ai_editor.vision_template.model import VisionEditOutput
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
from ai_editor.vision_template.transfer_template import apply_template_to_clips
from scripts.generate_synthetic import generate_synthetic_edit_sample
from tests.helpers.semantic_fixtures import generate_synthetic_object_video


def _temp_dir(name: str) -> Path:
    path = Path("tmp") / "tests" / f"{name}-{uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_decode_edit_template_respects_expected_slot_count():
    steps = 20
    boundary_logits = torch.full((steps,), -4.0)
    boundary_logits[4] = 4.0
    boundary_logits[9] = 4.5
    boundary_logits[14] = 4.2
    output = VisionEditOutput(
        boundary_logits=boundary_logits,
        motion_logits=torch.zeros((steps, 8)),
        transition_logits=torch.zeros((steps, 4)),
        overlay_logits=torch.zeros((steps, 6)),
        crop_params=torch.tensor([[0.0, 0.0, 1.0, 1.0]]).repeat(steps, 1),
        style_embedding=torch.zeros((16,)),
        frame_embeddings=torch.zeros((steps, 32)),
        temporal_features=torch.zeros((steps, 32)),
    )
    sampled = SampledVideo(
        frames=torch.zeros((steps, 3, 32, 32)),
        timestamps=[index * 0.5 for index in range(steps)],
        fps=2.0,
        duration=10.0,
        original_width=1920,
        original_height=1080,
        frame_count=steps,
    )

    template = decode_edit_template(output, sampled, expected_slots=4)

    assert len(template.slots) == 4
    assert template.total_duration == 10.0
    assert all(slot.duration > 0 for slot in template.slots)
    assert all(curr.start >= prev.end - 1e-6 for prev, curr in zip(template.slots, template.slots[1:]))


def test_decode_expected_slots_exact_count_low_confidence():
    steps = 25
    boundary_logits = torch.full((steps,), -0.4)
    boundary_logits[4] = 0.25
    boundary_logits[10] = 0.18
    boundary_logits[16] = 0.22
    boundary_logits[21] = 0.2
    output = VisionEditOutput(
        boundary_logits=boundary_logits,
        motion_logits=torch.zeros((steps, 8)),
        transition_logits=torch.zeros((steps, 4)),
        overlay_logits=torch.zeros((steps, 6)),
        crop_params=torch.tensor([[0.0, 0.0, 1.0, 1.0]]).repeat(steps, 1),
        style_embedding=torch.zeros((16,)),
        frame_embeddings=torch.zeros((steps, 48)),
        temporal_features=torch.zeros((steps, 64)),
    )
    sampled = SampledVideo(
        frames=torch.zeros((steps, 3, 32, 32)),
        timestamps=[index * 0.4 for index in range(steps)],
        fps=2.5,
        duration=10.0,
        original_width=1920,
        original_height=1080,
        frame_count=steps,
    )

    template = decode_edit_template(output, sampled, expected_slots=5)

    assert len(template.slots) == 5
    assert all(slot.duration > 0 for slot in template.slots)
    assert any("fallback" in warning.lower() for warning in template.warnings)


def test_sample_video_frames_from_synthetic_reference():
    tmp_dir = _temp_dir("vision-sampler")
    try:
        reference_path, _template_obj = generate_synthetic_edit_sample(str(tmp_dir), num_slots=4, fps=12, seed=9)
        sampled = sample_video_frames(reference_path, fps=6.0, size=96)

        assert sampled.frames.ndim == 4
        assert sampled.frames.shape[1] == 3
        assert sampled.frames.shape[2] == 96
        assert sampled.frames.shape[3] == 96
        assert sampled.frame_count == sampled.frames.shape[0]
        assert len(sampled.timestamps) == sampled.frames.shape[0]
        assert not torch.isnan(sampled.frames).any()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


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
