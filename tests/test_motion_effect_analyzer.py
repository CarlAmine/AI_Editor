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

    def test_handheld_wobble_not_classified_as_shake(self, tmp_path):
        path = str(tmp_path / "wobble.mp4")
        base = np.zeros((360, 640, 3), dtype=np.uint8)
        cv2.rectangle(base, (100, 100), (540, 260), (200, 200, 200), -1)
        rng = np.random.default_rng(42)

        def wobble_frame(_idx):
            shift = int(rng.integers(-3, 4))
            matrix = np.float32([[1, 0, shift], [0, 1, 0]])
            return lambda width, height: cv2.warpAffine(base, matrix, (width, height))

        frames = [wobble_frame(i) for i in range(75)]
        _write_synthetic_video(path, frames)
        scenes = [Scene(scene_id=1, start_time=0.0, end_time=3.0, duration=3.0, start_frame=0, end_frame=74)]
        manifest = MotionEffectAnalyzer().analyze(path, scenes)
        types = {effect.effect_type for effect in manifest.effects}

        assert EffectType.SHAKE not in types, f"Handheld wobble incorrectly classified as shake. Effects: {types}"

    def test_pan_detected_with_uneven_velocity(self, tmp_path):
        path = str(tmp_path / "pan.mp4")
        base = np.zeros((360, 640, 3), dtype=np.uint8)
        cv2.rectangle(base, (50, 100), (200, 260), (180, 100, 50), -1)
        velocities = ([1] * 5) + ([3] * 10) + ([5] * 15) + ([3] * 10) + ([1] * 5)
        cumulative = 0

        def pan_frame(idx):
            nonlocal cumulative
            if idx < len(velocities):
                cumulative += velocities[idx]
            matrix = np.float32([[1, 0, cumulative], [0, 1, 0]])
            return lambda width, height: cv2.warpAffine(base, matrix, (width, height))

        frames = [pan_frame(i) for i in range(45)] + [pan_frame(44)] * 5
        _write_synthetic_video(path, frames, fps=15.0)
        duration = 50 / 15
        scenes = [Scene(scene_id=1, start_time=0.0, end_time=duration, duration=duration, start_frame=0, end_frame=49)]
        manifest = MotionEffectAnalyzer().analyze(path, scenes)
        types = {effect.effect_type for effect in manifest.effects}

        assert EffectType.PAN in types, f"Pan with uneven velocity not detected. Effects: {types}"

    def test_shake_frequency_preserved_across_different_clip_lengths(self, tmp_path):
        from ai_editor.analysis.analysis_schema import EffectType, MotionCurve, MotionEffect, MotionEffectManifest
        from ai_editor.rendering.motion_effect_applier import MotionEffectApplier

        clip_path = str(tmp_path / "clip.mp4")
        base = np.full((360, 640, 3), 128, dtype=np.uint8)
        height, width = 360, 640
        writer = cv2.VideoWriter(clip_path, cv2.VideoWriter_fourcc(*"mp4v"), 25.0, (width, height))
        for _ in range(100):
            writer.write(base)
        writer.release()

        shake_curve = MotionCurve(
            dx_norm=[0.025 * ((-1) ** i) for i in range(50)],
            dy_norm=[0.012 * ((-1) ** (i + 1)) for i in range(50)],
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
                    intensity=0.8,
                    curve=shake_curve,
                    metadata={"curve_frame_count": 50, "reference_fps": 25.0},
                )
            ],
        )

        out_path = str(tmp_path / "out.mp4")
        result = MotionEffectApplier().apply_to_clip(clip_path, 0, manifest, out_path)

        assert result == out_path
        assert os.path.exists(out_path)
        cap = cv2.VideoCapture(out_path)
        out_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        assert out_frames == 100, f"Expected 100 frames, got {out_frames}"
