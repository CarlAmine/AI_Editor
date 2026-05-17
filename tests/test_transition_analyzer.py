"""Tests for TransitionAnalyzer using synthetic video data."""

import pytest

try:
    import cv2
    import numpy as np

    _CV2 = True
except Exception:  # pragma: no cover - dependency availability varies by environment
    cv2 = None  # type: ignore
    np = None  # type: ignore
    _CV2 = False

from ai_editor.analysis.analysis_schema import MotionEffectManifest, Scene, TransitionEvent, TransitionType
from ai_editor.analysis.transition_analyzer import TransitionAnalyzer


def _write_video(path, frame_fns, fps=25.0):
    height, width = 360, 640
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    for frame_fn in frame_fns:
        writer.write(frame_fn(width, height))
    writer.release()


@pytest.mark.skipif(not _CV2, reason="cv2 not available")
class TestTransitionAnalyzer:
    def test_hard_cut_is_default(self, tmp_path):
        path = str(tmp_path / "hc.mp4")
        bright = lambda width, height: np.full((height, width, 3), 180, dtype=np.uint8)
        dark = lambda width, height: np.full((height, width, 3), 40, dtype=np.uint8)
        frames = [bright] * 25 + [dark] * 25
        _write_video(path, frames)
        scenes = [
            Scene(1, 0.0, 1.0, 1.0, 0, 24),
            Scene(2, 1.0, 2.0, 1.0, 25, 49),
        ]
        result = TransitionAnalyzer().analyze(path, scenes)
        assert len(result) == 1
        assert result[0].transition_type == TransitionType.HARD_CUT

    def test_fade_to_black_detected(self, tmp_path):
        path = str(tmp_path / "ftb.mp4")
        frames = []
        for index in range(25):
            luma = max(0, int(180 - (index / 24) * 180)) if index >= 13 else 180
            frames.append(lambda width, height, l=luma: np.full((height, width, 3), l, dtype=np.uint8))
        for _ in range(25):
            frames.append(lambda width, height: np.full((height, width, 3), 150, dtype=np.uint8))
        _write_video(path, frames)
        scenes = [
            Scene(1, 0.0, 1.0, 1.0, 0, 24),
            Scene(2, 1.0, 2.0, 1.0, 25, 49),
        ]
        result = TransitionAnalyzer().analyze(path, scenes)
        assert len(result) == 1
        assert result[0].transition_type == TransitionType.FADE_TO_BLACK

    def test_dissolve_detected(self, tmp_path):
        path = str(tmp_path / "dissolve.mp4")
        frames = [lambda width, height: np.full((height, width, 3), 130, dtype=np.uint8)] * 50
        _write_video(path, frames)
        scenes = [
            Scene(1, 0.0, 1.0, 1.0, 0, 24),
            Scene(2, 1.0, 2.0, 1.0, 25, 49),
        ]
        result = TransitionAnalyzer().analyze(path, scenes)
        assert len(result) == 1
        assert result[0].transition_type in (TransitionType.CROSS_DISSOLVE, TransitionType.HARD_CUT)

    def test_returns_n_minus_one_events(self, tmp_path):
        path = str(tmp_path / "multi.mp4")
        frames = [lambda width, height: np.full((height, width, 3), 100, dtype=np.uint8)] * 75
        _write_video(path, frames)
        scenes = [
            Scene(1, 0.0, 1.0, 1.0, 0, 24),
            Scene(2, 1.0, 2.0, 1.0, 25, 49),
            Scene(3, 2.0, 3.0, 1.0, 50, 74),
        ]
        result = TransitionAnalyzer().analyze(path, scenes)
        assert len(result) == 2

    def test_schema_roundtrip(self, tmp_path):
        del tmp_path
        event = TransitionEvent(
            boundary_frame_index=25,
            outgoing_shot_index=0,
            incoming_shot_index=1,
            transition_type=TransitionType.FADE_TO_BLACK,
            duration_frames=12,
            duration_sec=0.48,
            intensity=0.95,
            luminance_curve=[180.0, 150.0, 100.0, 50.0, 10.0],
            metadata={"slope": 14.2},
        )
        manifest = MotionEffectManifest(
            video_path="ref.mp4",
            fps=25.0,
            total_frames=50,
            transitions_detected=[event],
        )
        restored = MotionEffectManifest.from_dict(manifest.to_dict())
        assert len(restored.transitions_detected) == 1
        restored_event = restored.transitions_detected[0]
        assert restored_event.transition_type == TransitionType.FADE_TO_BLACK
        assert restored_event.duration_frames == 12
        assert restored_event.intensity == 0.95
        assert restored_event.luminance_curve == [180.0, 150.0, 100.0, 50.0, 10.0]
