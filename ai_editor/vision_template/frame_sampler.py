from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

try:
    import cv2
except Exception:  # pragma: no cover - import-safe fallback
    class _CV2Stub:
        COLOR_BGR2RGB = 0
        CAP_PROP_FPS = 5
        CAP_PROP_FRAME_COUNT = 7
        CAP_PROP_FRAME_WIDTH = 3
        CAP_PROP_FRAME_HEIGHT = 4
        INTER_AREA = 3

        @staticmethod
        def VideoCapture(_path: str):
            raise ImportError("cv2 is required for vision template frame sampling")

    cv2 = _CV2Stub()  # type: ignore
import numpy as np
import torch

from . import VisionTemplateError


@dataclass
class SampledVideo:
    frames: torch.Tensor
    timestamps: List[float]
    fps: float
    duration: float
    original_width: int
    original_height: int
    frame_count: int


def sample_video_frames(
    video_path: str,
    fps: float = 8.0,
    size: int = 224,
    max_seconds: Optional[float] = None,
) -> SampledVideo:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise VisionTemplateError(f"Could not open reference video: {video_path}")

    native_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    duration = (total_frames / native_fps) if native_fps > 0 else 0.0
    if max_seconds is not None:
        duration = min(duration, float(max_seconds))
    if native_fps <= 0:
        cap.release()
        raise VisionTemplateError(f"Reference video FPS is invalid: {video_path}")

    interval = max(native_fps / max(float(fps), 0.1), 1.0)
    sampled_frames: List[torch.Tensor] = []
    timestamps: List[float] = []
    frame_index = 0
    next_sample_at = 0.0
    max_frame_index = int(duration * native_fps) if duration > 0 else total_frames

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if max_frame_index and frame_index > max_frame_index:
            break
        if frame_index + 1e-6 >= next_sample_at:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            resized = cv2.resize(rgb, (size, size), interpolation=cv2.INTER_AREA)
            tensor = torch.from_numpy(resized).permute(2, 0, 1).float() / 255.0
            sampled_frames.append(tensor)
            timestamps.append(frame_index / native_fps)
            next_sample_at += interval
        frame_index += 1

    cap.release()
    if len(sampled_frames) < 8:
        raise VisionTemplateError(
            f"Reference video produced too few sampled frames ({len(sampled_frames)}). Need at least 8."
        )

    frames = torch.stack(sampled_frames, dim=0)
    if torch.isnan(frames).any():
        raise VisionTemplateError("Sampled video contains NaN frame values.")

    sampled_duration = timestamps[-1] if timestamps else 0.0
    return SampledVideo(
        frames=frames,
        timestamps=timestamps,
        fps=float(fps),
        duration=max(sampled_duration, duration),
        original_width=width,
        original_height=height,
        frame_count=len(sampled_frames),
    )
