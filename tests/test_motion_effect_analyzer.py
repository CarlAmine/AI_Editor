"""
Tests for MotionEffectAnalyzer using synthetic video data.
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

from ai_editor.analysis.analysis_schema import EffectType, MotionEffectManifest, Scene
from ai_editor.analysis.motion_effect_analyzer import MotionEffectAnalyzer


def _write_synthetic_video(path: str, frames_data: list, fps: float = 25.0) -> None:
    height, width = 360, 640
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    for frame_builder in frames_data:
        writer.write(frame_builder(width, height))
    writer.release()


@pytest.mark.skipif(not _CV2, reason="cv2 not available")
class TestMotionEffectAnalyzer:
    def _static_frame(self, color=(100, 150, 200)):
        def build(_width, height):
            frame = np.full((height, 640, 3), color, dtype=np.uint8)
            cv2.rectangle(frame, (180, 100), (460, 260), (255, 255, 255), -1)
            return frame

        return build

    def test_static_video_returns_static_effect(self, tmp_path):
        path = str(tmp_path / "static.mp4")
        frames = [self._static_frame() for _ in range(50)]
        _write_synthetic_video(path, frames)
        scenes = [Scene(scene_id=1, start_time=0.0, end_time=2.0, duration=2.0, start_frame=0, end_frame=49)]
        manifest = MotionEffectAnalyzer().analyze(path, scenes)

        assert manifest.fps > 0
        assert len(manifest.effects) >= 1
        assert EffectType.STATIC in {effect.effect_type for effect in manifest.effects}

    def test_shake_video_detected(self, tmp_path):
        path = str(tmp_path / "shake.mp4")
        base = np.zeros((360, 640, 3), dtype=np.uint8)
        cv2.rectangle(base, (100, 100), (540, 260), (255, 255, 255), -1)

        def shake_frame(index):
            def build(width, height):
                shift = 15 if index % 2 == 0 else -15
                matrix = np.float32([[1, 0, shift], [0, 1, 0]])
                return cv2.warpAffine(base, matrix, (width, height))

            return build

        _write_synthetic_video(path, [shake_frame(i) for i in range(75)])
        scenes = [Scene(scene_id=1, start_time=0.0, end_time=3.0, duration=3.0, start_frame=0, end_frame=74)]
        manifest = MotionEffectAnalyzer().analyze(path, scenes)

        assert EffectType.SHAKE in {effect.effect_type for effect in manifest.effects}

    def test_rhythm_pattern_matches_scenes(self, tmp_path):
        path = str(tmp_path / "rhythm.mp4")
        frames = [self._static_frame((i * 30 % 255, 100, 100)) for i in range(100)]
        _write_synthetic_video(path, frames)
        scenes = [
            Scene(scene_id=1, start_time=0.0, end_time=1.5, duration=1.5, start_frame=0, end_frame=37),
            Scene(scene_id=2, start_time=1.5, end_time=2.5, duration=1.0, start_frame=37, end_frame=62),
            Scene(scene_id=3, start_time=2.5, end_time=4.0, duration=1.5, start_frame=62, end_frame=99),
        ]
        manifest = MotionEffectAnalyzer().analyze(path, scenes)

        assert manifest.rhythm_pattern == [1.5, 1.0, 1.5]

    def test_manifest_serialisation_roundtrip(self, tmp_path):
        path = str(tmp_path / "serial.mp4")
        frames = [self._static_frame() for _ in range(50)]
        _write_synthetic_video(path, frames)
        scenes = [Scene(scene_id=1, start_time=0.0, end_time=2.0, duration=2.0, start_frame=0, end_frame=49)]
        manifest = MotionEffectAnalyzer().analyze(path, scenes)
        restored = MotionEffectManifest.from_dict(manifest.to_dict())

        assert len(restored.effects) == len(manifest.effects)
        assert restored.rhythm_pattern == manifest.rhythm_pattern
        assert restored.fps == manifest.fps
        assert os.path.basename(restored.video_path) == "serial.mp4"
