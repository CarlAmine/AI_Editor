import shutil
from pathlib import Path
from uuid import uuid4

import torch

from ai_editor.vision_template.frame_sampler import sample_video_frames
from ai_editor.vision_template.synthetic_dataset import generate_synthetic_edit_sample


def test_sample_video_frames_from_synthetic_reference():
    tmp_dir = Path("tmp") / "tests" / f"vision-sampler-{uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    try:
        reference_path, _template = generate_synthetic_edit_sample(str(tmp_dir), num_slots=4, fps=12, seed=9)
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
