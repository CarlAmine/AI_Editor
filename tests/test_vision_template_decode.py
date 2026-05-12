from dataclasses import dataclass

import torch

from ai_editor.vision_template.decode_template import decode_edit_template
from ai_editor.vision_template.frame_sampler import SampledVideo
from ai_editor.vision_template.model import VisionEditOutput


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
