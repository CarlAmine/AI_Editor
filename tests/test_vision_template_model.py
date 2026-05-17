import shutil
from pathlib import Path
from uuid import uuid4

import torch

from ai_editor.vision_template.model import OVERLAY_LABELS, TRANSITION_LABELS, TinyVisionEditModel
from ai_editor.vision_template.schemas import CropSpec, EditSlot, EditTemplate, GlobalStyle, MotionSpec
from scripts.generate_synthetic import SyntheticEditDataset, generate_synthetic_edit_sample
from scripts.vision_template_losses import compute_supervised_synthetic_loss
from scripts.vision_template_metrics import boundary_precision_recall_with_tolerance, decode_confidence_summary
from ai_editor.vision_template.frame_sampler import sample_video_frames


def _template(boundaries: list[tuple[float, float, float]]) -> EditTemplate:
    slots = [
        EditSlot(
            slot_id=index + 1,
            start=start,
            end=end,
            duration=duration,
            boundary_confidence=0.7,
            motion=MotionSpec(kind="static", confidence=1.0),
            crop=CropSpec(),
        )
        for index, (start, end, duration) in enumerate(boundaries)
    ]
    return EditTemplate(
        version="0.1",
        fps=8.0,
        total_duration=boundaries[-1][1],
        slots=slots,
        global_style=GlobalStyle(avg_slot_duration=1.0, rhythm=[slot.duration for slot in slots], pacing_label="medium", dominant_transition="cut"),
        warnings=[],
    )


def test_tiny_vision_edit_model_output_shapes():
    tmp_dir = Path("tmp") / "tests" / f"vision-model-{uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    try:
        reference_path, _template_obj = generate_synthetic_edit_sample(str(tmp_dir), num_slots=3, fps=8, seed=3)
        sampled = sample_video_frames(reference_path, fps=8.0, size=64)
        model = TinyVisionEditModel()
        output = model(sampled.frames)

        steps = sampled.frames.shape[0]
        assert output.boundary_logits.shape[0] == steps
        assert output.motion_logits.shape[0] == steps
        assert output.transition_logits.shape == (steps, len(TRANSITION_LABELS))
        assert output.overlay_logits.shape == (steps, len(OVERLAY_LABELS))
        assert output.crop_params.shape == (steps, 4)
        assert not torch.isnan(output.boundary_logits).any()

        batched = model(sampled.frames.unsqueeze(0))
        assert batched.boundary_logits.shape == (1, steps)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_supervised_synthetic_loss_is_finite():
    tmp_dir = Path("tmp") / "tests" / f"vision-loss-{uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    try:
        dataset = SyntheticEditDataset(out_dir=str(tmp_dir), num_slots=4, fps=8, seed=2)
        sample = dataset[0]
        model = TinyVisionEditModel()
        output = model(sample["frames"])
        labels = {
            "boundary": sample["boundary_labels"],
            "motion": sample["motion_labels"],
            "transition": sample["transition_labels"],
            "overlay": sample["overlay_labels"],
            "crop": sample["crop_labels"],
        }
        loss = compute_supervised_synthetic_loss(output, labels)

        assert torch.isfinite(loss)
        assert loss.ndim == 0
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_supervised_synthetic_loss_is_finite_with_no_boundaries():
    tmp_dir = Path("tmp") / "tests" / f"vision-loss-empty-{uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    try:
        dataset = SyntheticEditDataset(out_dir=str(tmp_dir), num_slots=1, fps=8, seed=4)
        sample = dataset[0]
        model = TinyVisionEditModel()
        output = model(sample["frames"])
        labels = {
            "boundary": torch.zeros_like(sample["boundary_labels"]),
            "motion": sample["motion_labels"],
            "transition": sample["transition_labels"],
            "overlay": sample["overlay_labels"],
            "crop": sample["crop_labels"],
        }
        loss = compute_supervised_synthetic_loss(output, labels)
        assert torch.isfinite(loss)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_metrics_boundary_precision_recall():
    pred = _template([(0.0, 1.1, 1.1), (1.1, 2.1, 1.0), (2.1, 3.0, 0.9)])
    target = _template([(0.0, 1.0, 1.0), (1.0, 2.0, 1.0), (2.0, 3.0, 1.0)])
    metrics = boundary_precision_recall_with_tolerance(pred, target, tolerance=0.2)

    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0


def test_decode_confidence_summary_reports_fallback():
    template = _template([(0.0, 1.0, 1.0), (1.0, 2.0, 1.0)])
    template.warnings.append("decoder_fallback_used")
    summary = decode_confidence_summary(template)
    assert summary["fallback_used"] is True
