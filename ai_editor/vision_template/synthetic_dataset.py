from __future__ import annotations

import json
import math
import os
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import cv2
except Exception:  # pragma: no cover - import-safe fallback
    class _CV2Stub:
        FONT_HERSHEY_SIMPLEX = 0
        LINE_AA = 0

        @staticmethod
        def VideoWriter(*_args, **_kwargs):
            raise ImportError("cv2 is required for synthetic video generation")

        @staticmethod
        def VideoWriter_fourcc(*_args):
            return 0

        @staticmethod
        def rectangle(*_args, **_kwargs):
            raise ImportError("cv2 is required for synthetic video generation")

        @staticmethod
        def circle(*_args, **_kwargs):
            raise ImportError("cv2 is required for synthetic video generation")

        @staticmethod
        def line(*_args, **_kwargs):
            raise ImportError("cv2 is required for synthetic video generation")

        @staticmethod
        def putText(*_args, **_kwargs):
            raise ImportError("cv2 is required for synthetic video generation")

    cv2 = _CV2Stub()  # type: ignore
import numpy as np
import torch
from torch.utils.data import Dataset

from .decode_template import decode_edit_template
from .frame_sampler import SampledVideo, sample_video_frames
from .model import MOTION_LABELS, OVERLAY_LABELS, TRANSITION_LABELS, VisionEditOutput
from .schemas import CropSpec, EditSlot, EditTemplate, GlobalStyle, MotionSpec, OverlaySpec, SlotMapping, SlotMappingItem


def _make_canvas(size: Tuple[int, int], base_color: Tuple[int, int, int]) -> np.ndarray:
    frame = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    frame[:, :] = np.array(base_color, dtype=np.uint8)
    return frame


def _draw_pattern(frame: np.ndarray, slot_index: int, frame_idx: int, total_frames: int, motion_kind: str, overlay_region: str) -> np.ndarray:
    height, width = frame.shape[:2]
    progress = frame_idx / max(total_frames - 1, 1)
    if motion_kind == "zoom_in":
        margin = int((1.0 - progress * 0.35) * min(width, height) * 0.25)
        cv2.rectangle(frame, (margin, margin), (width - margin, height - margin), (255, 255, 255), 3)
    elif motion_kind == "zoom_out":
        margin = int((0.2 + progress * 0.35) * min(width, height) * 0.2)
        cv2.rectangle(frame, (margin, margin), (width - margin, height - margin), (255, 255, 255), 3)
    elif motion_kind.startswith("pan_"):
        offset = int(progress * width * 0.35)
        x0 = 20 + (offset if motion_kind == "pan_right" else -offset if motion_kind == "pan_left" else 0)
        y0 = 20 + (offset if motion_kind == "pan_down" else -offset if motion_kind == "pan_up" else 0)
        cv2.circle(frame, (int(np.clip(width / 2 + x0, 0, width - 1)), int(np.clip(height / 2 + y0, 0, height - 1))), 28, (255, 255, 255), -1)
    else:
        for stripe in range(0, width, 30):
            cv2.line(frame, (stripe, 0), (stripe, height), (255, 255, 255), 2)

    cv2.putText(frame, f"S{slot_index}", (20, height - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2, cv2.LINE_AA)
    if overlay_region != "none":
        if overlay_region == "top":
            y1, y2 = 10, 50
        elif overlay_region == "center":
            y1, y2 = height // 2 - 20, height // 2 + 20
        elif overlay_region == "lower_third":
            y1, y2 = int(height * 0.72), int(height * 0.72) + 40
        else:
            y1, y2 = 0, height
        cv2.rectangle(frame, (10, y1), (width - 10, min(y2, height - 1)), (20, 20, 20), -1)
        if overlay_region != "full":
            cv2.rectangle(frame, (25, y1 + 10), (width - 25, min(y2 - 10, height - 10)), (240, 240, 240), -1)
    return frame


def _write_video(path: str, frames: List[np.ndarray], fps: int) -> None:
    height, width = frames[0].shape[:2]
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), float(fps), (width, height))
    for frame in frames:
        writer.write(frame)
    writer.release()


def generate_synthetic_edit_sample(
    out_dir: str,
    num_slots: int = 5,
    fps: int = 12,
    size: tuple[int, int] = (224, 224),
    seed: int | None = None,
) -> tuple[str, EditTemplate]:
    rng = random.Random(seed)
    os.makedirs(out_dir, exist_ok=True)
    motion_cycle = ["static", "zoom_in", "pan_right", "zoom_out", "pan_down", "pan_left"]
    overlay_cycle = ["none", "top", "center", "lower_third", "none", "full"]
    transition_cycle = ["cut", "fade", "wipe", "cut", "fade"]

    reference_frames: List[np.ndarray] = []
    replacement_paths: List[str] = []
    slots: List[EditSlot] = []
    slot_mapping_items: List[SlotMappingItem] = []
    cursor = 0.0
    base_colors = [(220, 80, 80), (80, 200, 120), (80, 120, 220), (220, 180, 80), (180, 80, 220), (80, 220, 220)]

    for slot_id in range(1, num_slots + 1):
        duration = round(0.9 + 0.35 * slot_id + (0.15 if slot_id % 2 == 0 else 0.0), 2)
        total_frames = max(int(round(duration * fps)), 8)
        motion_kind = motion_cycle[(slot_id - 1) % len(motion_cycle)]
        overlay_region = overlay_cycle[(slot_id - 1) % len(overlay_cycle)]
        transition = transition_cycle[(slot_id - 1) % len(transition_cycle)]
        color = base_colors[(slot_id - 1) % len(base_colors)]

        slot_reference_frames: List[np.ndarray] = []
        slot_replacement_frames: List[np.ndarray] = []
        for frame_idx in range(total_frames):
            ref_frame = _make_canvas(size, color)
            ref_frame = _draw_pattern(ref_frame, slot_id, frame_idx, total_frames, motion_kind, overlay_region)
            slot_reference_frames.append(ref_frame)

            repl_color = tuple(int(min(255, channel + 20)) for channel in color)
            repl_frame = _make_canvas(size, repl_color)
            repl_frame = _draw_pattern(repl_frame, slot_id + 10, frame_idx, total_frames, "static", "none")
            slot_replacement_frames.append(repl_frame)

        reference_frames.extend(slot_reference_frames)
        clip_id = f"clip_{slot_id}"
        clip_path = os.path.join(out_dir, f"replacement_clip_{slot_id:03d}.mp4")
        _write_video(clip_path, slot_replacement_frames, fps)
        replacement_paths.append(clip_path)
        slot_mapping_items.append(SlotMappingItem(slot_id=slot_id, clip_id=clip_id, clip_path=clip_path))
        slots.append(
            EditSlot(
                slot_id=slot_id,
                start=cursor,
                end=cursor + duration,
                duration=duration,
                boundary_confidence=1.0,
                transition_in=transition,
                transition_out=transition,
                motion=MotionSpec(kind=motion_kind, confidence=1.0, keyframes=[{"t": 0.0}, {"t": 1.0}]),
                crop=CropSpec(x=0.05 if slot_id % 2 else 0.0, y=0.05 if slot_id % 3 == 0 else 0.0, width=0.9, height=0.9),
                overlay=OverlaySpec(
                    has_overlay=overlay_region != "none",
                    region="unknown" if overlay_region == "none" else overlay_region,
                    start_rel=0.0,
                    end_rel=1.0,
                    mask_confidence=1.0 if overlay_region != "none" else 0.0,
                )
                if overlay_region != "none"
                else None,
                style_vector=[float(slot_id), duration, float(slot_id % 3)],
            )
        )
        cursor += duration

    reference_path = os.path.join(out_dir, "reference.mp4")
    _write_video(reference_path, reference_frames, fps)
    template = EditTemplate(
        version="0.1",
        source_reference=reference_path,
        fps=float(fps),
        total_duration=cursor,
        slots=slots,
        global_style=GlobalStyle(
            avg_slot_duration=sum(slot.duration for slot in slots) / max(len(slots), 1),
            rhythm=[slot.duration for slot in slots],
            pacing_label="medium",
            dominant_transition="cut",
            aspect_ratio="1:1",
            style_embedding=[0.1 * i for i in range(8)],
        ),
        warnings=[],
    )
    template.to_json_file(os.path.join(out_dir, "ground_truth_template.json"))
    SlotMapping(items=slot_mapping_items).to_json_file(os.path.join(out_dir, "slot_mapping.json"))
    return reference_path, template


class SyntheticEditDataset(Dataset):
    def __init__(
        self,
        out_dir: Optional[str] = None,
        num_slots: int = 5,
        fps: int = 12,
        size: tuple[int, int] = (224, 224),
        seed: Optional[int] = 0,
    ) -> None:
        self.root = Path(out_dir or Path("tmp") / "vision_template_dataset")
        reference_path, template = generate_synthetic_edit_sample(str(self.root), num_slots=num_slots, fps=fps, size=size, seed=seed)
        self.reference_path = reference_path
        self.template = template
        self.sampled = sample_video_frames(reference_path, fps=float(fps), size=size[0])
        self._frames = self.sampled.frames
        self._labels = self._build_labels()

    def _build_labels(self) -> Dict[str, torch.Tensor]:
        steps = self._frames.shape[0]
        boundary = torch.zeros(steps, dtype=torch.float32)
        motion = torch.full((steps,), MOTION_LABELS.index("unknown"), dtype=torch.long)
        transition = torch.zeros(steps, dtype=torch.long)
        overlay = torch.zeros(steps, dtype=torch.long)
        crop = torch.zeros((steps, 4), dtype=torch.float32)

        timestamps = self.sampled.timestamps
        for slot in self.template.slots:
            slot_indices = [i for i, ts in enumerate(timestamps) if slot.start - 1e-6 <= ts < slot.end + 1e-6]
            if not slot_indices:
                continue
            motion_idx = MOTION_LABELS.index(slot.motion.kind)
            transition_idx = TRANSITION_LABELS.index(slot.transition_in) if slot.transition_in in TRANSITION_LABELS else 0
            overlay_idx = OVERLAY_LABELS.index(slot.overlay.region) if slot.overlay and slot.overlay.region in OVERLAY_LABELS else 0
            for idx in slot_indices:
                motion[idx] = motion_idx
                transition[idx] = transition_idx
                overlay[idx] = overlay_idx
                crop[idx] = torch.tensor([slot.crop.x, slot.crop.y, slot.crop.width, slot.crop.height], dtype=torch.float32)
            last_idx = min(slot_indices[-1], steps - 1)
            boundary[last_idx] = 1.0
        if steps > 0:
            boundary[-1] = 1.0
        return {
            "boundary": boundary,
            "motion": motion,
            "transition": transition,
            "overlay": overlay,
            "crop": crop,
        }

    def __len__(self) -> int:
        return 1

    def __getitem__(self, index: int) -> Dict[str, object]:
        if index != 0:
            raise IndexError(index)
        return {
            "frames": self._frames,
            "boundary_labels": self._labels["boundary"],
            "motion_labels": self._labels["motion"],
            "overlay_labels": self._labels["overlay"],
            "transition_labels": self._labels["transition"],
            "crop_labels": self._labels["crop"],
            "ground_truth_template": self.template,
        }
