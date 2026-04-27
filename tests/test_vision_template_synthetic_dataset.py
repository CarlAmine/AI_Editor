import shutil
from pathlib import Path
from uuid import uuid4

from ai_editor.vision_template.synthetic_dataset import SyntheticEditDataset, generate_synthetic_edit_sample


def _temp_dir(name: str) -> Path:
    path = Path("tmp") / "tests" / f"{name}-{uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_generate_synthetic_edit_sample():
    tmp_dir = _temp_dir("vision-synth")
    try:
        reference_path, template = generate_synthetic_edit_sample(str(tmp_dir), num_slots=4, fps=10, seed=7)

        assert reference_path.endswith("reference.mp4")
        assert (tmp_dir / "reference.mp4").exists()
        assert (tmp_dir / "ground_truth_template.json").exists()
        assert (tmp_dir / "slot_mapping.json").exists()
        assert len(template.slots) == 4
        assert all(slot.duration > 0 for slot in template.slots)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_synthetic_edit_dataset_returns_training_labels():
    tmp_dir = _temp_dir("vision-dataset")
    try:
        dataset = SyntheticEditDataset(out_dir=str(tmp_dir), num_slots=3, fps=8, seed=11)
        sample = dataset[0]

        assert sample["frames"].shape[1] == 3
        assert sample["boundary_labels"].shape[0] == sample["frames"].shape[0]
        assert sample["ground_truth_template"].total_duration > 0
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
