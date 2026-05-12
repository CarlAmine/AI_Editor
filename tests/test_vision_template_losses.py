import shutil
from pathlib import Path
from uuid import uuid4

import torch

from ai_editor.vision_template.losses import compute_supervised_synthetic_loss
from ai_editor.vision_template.model import TinyVisionEditModel
from ai_editor.vision_template.synthetic_dataset import SyntheticEditDataset


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
