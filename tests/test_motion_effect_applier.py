"""
Tests for MotionEffectApplier.
"""

import os

import pytest

try:
    import cv2
    import numpy as np

    _CV2 = True
except Exception:  # pragma: no cover - dependency availability varies by environment
    cv2 = None  # type: ignore
    np = None  # type: ignore
    _CV2 = False

from ai_editor.analysis.analysis_schema import EffectType, MotionCurve, MotionEffect, MotionEffectManifest
from ai_editor.rendering.motion_effect_applier import MotionEffectApplier


@pytest.mark.skipif(not _CV2, reason="cv2 not available")
class TestMotionEffectApplier:
    def _write_clip(self, path: str, n_frames: int = 50, fps: float = 25.0) -> None:
        height, width = 360, 640
        writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
        base = np.zeros((height, width, 3), dtype=np.uint8)
        cv2.rectangle(base, (200, 100), (440, 260), (0, 200, 100), -1)
        for _ in range(n_frames):
            writer.write(base)
        writer.release()

    def test_no_effects_returns_original_path(self, tmp_path):
        clip = str(tmp_path / "clip.mp4")
        self._write_clip(clip)
        manifest = MotionEffectManifest(
            video_path="ref.mp4",
            fps=25.0,
            total_frames=50,
            effects=[
                MotionEffect(
                    shot_index=0,
                    effect_type=EffectType.STATIC,
                    onset_frac=0.0,
                    offset_frac=1.0,
                    intensity=0.0,
                )
            ],
        )

        result = MotionEffectApplier().apply_to_clip(clip, 0, manifest, str(tmp_path / "out.mp4"))

        assert result == clip

    def test_shake_effect_produces_output_file(self, tmp_path):
        clip = str(tmp_path / "clip.mp4")
        out = str(tmp_path / "out.mp4")
        self._write_clip(clip)
        curve = MotionCurve(
            dx_norm=[0.02, -0.03, 0.04, -0.02, 0.03, -0.04] * 8,
            dy_norm=[0.01, -0.01, 0.02, -0.01, 0.01, -0.02] * 8,
        )
        manifest = MotionEffectManifest(
            video_path="ref.mp4",
            fps=25.0,
            total_frames=50,
            effects=[
                MotionEffect(
                    shot_index=0,
                    effect_type=EffectType.SHAKE,
                    onset_frac=0.0,
                    offset_frac=1.0,
                    intensity=0.6,
                    curve=curve,
                )
            ],
        )

        result = MotionEffectApplier().apply_to_clip(clip, 0, manifest, out)

        assert result == out
        assert os.path.exists(out)
        assert os.path.getsize(out) > 1000

    def test_wrong_shot_index_returns_original(self, tmp_path):
        clip = str(tmp_path / "clip.mp4")
        self._write_clip(clip)
        manifest = MotionEffectManifest(
            video_path="ref.mp4",
            fps=25.0,
            total_frames=50,
            effects=[
                MotionEffect(
                    shot_index=5,
                    effect_type=EffectType.SHAKE,
                    onset_frac=0.0,
                    offset_frac=1.0,
                    intensity=0.5,
                )
            ],
        )

        result = MotionEffectApplier().apply_to_clip(clip, 0, manifest, str(tmp_path / "out.mp4"))

        assert result == clip
