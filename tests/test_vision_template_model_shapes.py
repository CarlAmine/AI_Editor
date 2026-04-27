import shutil
from pathlib import Path
from uuid import uuid4

from ai_editor.vision_template.frame_sampler import sample_video_frames
from ai_editor.vision_template.model import OVERLAY_LABELS, TRANSITION_LABELS, TinyVisionEditModel
from ai_editor.vision_template.synthetic_dataset import generate_synthetic_edit_sample


def test_tiny_vision_edit_model_output_shapes():
    tmp_dir = Path("tmp") / "tests" / f"vision-model-{uuid4().hex[:8]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    try:
        reference_path, _template = generate_synthetic_edit_sample(str(tmp_dir), num_slots=3, fps=8, seed=3)
        sampled = sample_video_frames(reference_path, fps=8.0, size=64)
        model = TinyVisionEditModel()
        output = model(sampled.frames)

        steps = sampled.frames.shape[0]
        assert output.boundary_logits.shape[0] == steps
        assert output.motion_logits.shape[0] == steps
        assert output.transition_logits.shape == (steps, len(TRANSITION_LABELS))
        assert output.overlay_logits.shape == (steps, len(OVERLAY_LABELS))
        assert output.crop_params.shape == (steps, 4)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
