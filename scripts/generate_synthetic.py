from __future__ import annotations

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

        @staticmethod
        def ellipse(*_args, **_kwargs):
            raise ImportError("cv2 is required for synthetic video generation")

        @staticmethod
        def polylines(*_args, **_kwargs):
            raise ImportError("cv2 is required for synthetic video generation")

    cv2 = _CV2Stub()  # type: ignore
import numpy as np
import torch
from torch.utils.data import Dataset

from ai_editor.vision_template.frame_sampler import SampledVideo, sample_video_frames
from ai_editor.vision_template.model import MOTION_LABELS, OVERLAY_LABELS, TRANSITION_LABELS
from ai_editor.vision_template.schemas import (
    CropSpec,
    EditSlot,
    EditTemplate,
    GlobalStyle,
    MotionSpec,
    OverlaySpec,
    SlotMapping,
    SlotMappingItem,
)


def _make_canvas(size: Tuple[int, int], base_color: Tuple[int, int, int]) -> np.ndarray:
    frame = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    frame[:, :] = np.array(base_color, dtype=np.uint8)
    return frame


def _overlay_bounds(region: str, width: int, height: int) -> tuple[int, int]:
    if region == "top":
        return 10, 48
    if region == "center":
        return max(8, height // 2 - 22), min(height - 8, height // 2 + 22)
    if region == "lower_third":
        return int(height * 0.72), min(height - 8, int(height * 0.72) + 38)
    return 0, height


def _draw_slot_pattern(
    frame: np.ndarray,
    *,
    slot_index: int,
    frame_idx: int,
    total_frames: int,
    motion_kind: str,
    overlay_region: str,
    pattern_kind: str,
    accent_color: tuple[int, int, int],
) -> np.ndarray:
    height, width = frame.shape[:2]
    progress = frame_idx / max(total_frames - 1, 1)
    center_x = width // 2
    center_y = height // 2

    # A stable, slot-specific pattern helps the model learn within-slot consistency.
    if pattern_kind == "stripes":
        step = max(16, width // 7)
        for stripe in range(-step, width + step, step):
            cv2.line(frame, (stripe, 0), (stripe + height // 2, height), accent_color, 5)
    elif pattern_kind == "diamond":
        scale = int(min(width, height) * (0.22 + 0.08 * progress if motion_kind == "zoom_in" else 0.28 - 0.08 * progress if motion_kind == "zoom_out" else 0.26))
        points = np.array(
            [
                [center_x, center_y - scale],
                [center_x + scale, center_y],
                [center_x, center_y + scale],
                [center_x - scale, center_y],
            ],
            dtype=np.int32,
        )
        cv2.polylines(frame, [points], True, accent_color, 5)
    elif pattern_kind == "rings":
        radius = int(min(width, height) * 0.12)
        for idx in range(3):
            delta = idx * 18
            cv2.circle(frame, (center_x, center_y), radius + delta, accent_color, 4)
    elif pattern_kind == "grid":
        step = max(18, width // 6)
        for x in range(step // 2, width, step):
            cv2.line(frame, (x, 0), (x, height), accent_color, 3)
        for y in range(step // 2, height, step):
            cv2.line(frame, (0, y), (width, y), accent_color, 3)
    elif pattern_kind == "cross":
        cv2.line(frame, (width // 4, center_y), (width - width // 4, center_y), accent_color, 8)
        cv2.line(frame, (center_x, height // 4), (center_x, height - height // 4), accent_color, 8)
    else:
        cv2.ellipse(frame, (center_x, center_y), (width // 4, height // 6), 20, 0, 360, accent_color, 6)

    # Motion is encoded as smooth object movement rather than random flicker.
    offset_x = 0
    offset_y = 0
    scale = 1.0
    if motion_kind == "pan_right":
        offset_x = int(progress * width * 0.22)
    elif motion_kind == "pan_left":
        offset_x = -int(progress * width * 0.22)
    elif motion_kind == "pan_down":
        offset_y = int(progress * height * 0.18)
    elif motion_kind == "pan_up":
        offset_y = -int(progress * height * 0.18)
    elif motion_kind == "zoom_in":
        scale = 1.0 + 0.18 * progress
    elif motion_kind == "zoom_out":
        scale = 1.18 - 0.18 * progress

    box_w = int(width * 0.18 * scale)
    box_h = int(height * 0.16 * scale)
    x1 = int(np.clip(center_x - box_w // 2 + offset_x, 8, width - box_w - 8))
    y1 = int(np.clip(center_y - box_h // 2 + offset_y, 8, height - box_h - 8))
    cv2.rectangle(frame, (x1, y1), (x1 + box_w, y1 + box_h), (245, 245, 245), -1)
    cv2.rectangle(frame, (x1, y1), (x1 + box_w, y1 + box_h), (30, 30, 30), 2)

    cv2.putText(frame, f"S{slot_index}", (18, height - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (12, 12, 12), 2, cv2.LINE_AA)
    if overlay_region != "none":
        y1, y2 = _overlay_bounds(overlay_region, width, height)
        cv2.rectangle(frame, (10, y1), (width - 10, min(height - 1, y2)), (15, 15, 15), -1)
        if overlay_region != "full":
            cv2.rectangle(frame, (24, y1 + 8), (width - 24, max(y1 + 16, y2 - 8)), (240, 240, 240), -1)
    return frame


def _write_video(path: str, frames: List[np.ndarray], fps: int) -> None:
    height, width = frames[0].shape[:2]
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), float(fps), (width, height))
    for frame in frames:
        writer.write(frame)
    writer.release()


def build_frame_targets_from_template(sampled_video: SampledVideo, template: EditTemplate) -> Dict[str, torch.Tensor]:
    steps = sampled_video.frames.shape[0]
    boundary = torch.zeros(steps, dtype=torch.float32)
    slot_ids = torch.full((steps,), -1, dtype=torch.long)
    motion = torch.full((steps,), MOTION_LABELS.index("unknown"), dtype=torch.long)
    transition = torch.zeros((steps,), dtype=torch.long)
    overlay = torch.zeros((steps,), dtype=torch.long)
    crop = torch.zeros((steps, 4), dtype=torch.float32)

    timestamps = [float(ts) for ts in sampled_video.timestamps]
    for slot in template.slots:
        for idx, ts in enumerate(timestamps):
            is_last_slot = slot.slot_id == template.slots[-1].slot_id
            in_slot = (slot.start - 1e-6) <= ts < (slot.end - 1e-6 if not is_last_slot else slot.end + 1e-6)
            if not in_slot:
                continue
            slot_ids[idx] = int(slot.slot_id)
            motion[idx] = MOTION_LABELS.index(slot.motion.kind) if slot.motion.kind in MOTION_LABELS else MOTION_LABELS.index("unknown")
            transition[idx] = TRANSITION_LABELS.index(slot.transition_in) if slot.transition_in in TRANSITION_LABELS else 0
            overlay[idx] = OVERLAY_LABELS.index(slot.overlay.region) if slot.overlay and slot.overlay.region in OVERLAY_LABELS else 0
            crop[idx] = torch.tensor([slot.crop.x, slot.crop.y, slot.crop.width, slot.crop.height], dtype=torch.float32)

    internal_boundaries = [float(slot.end) for slot in template.slots[:-1]]
    for boundary_time in internal_boundaries:
        nearest = min(range(steps), key=lambda idx: abs(timestamps[idx] - boundary_time))
        boundary[nearest] = 1.0
        if nearest - 1 >= 0:
            boundary[nearest - 1] = max(boundary[nearest - 1], 0.35)
        if nearest + 1 < steps:
            boundary[nearest + 1] = max(boundary[nearest + 1], 0.35)

    motion_per_slot = torch.tensor(
        [
            MOTION_LABELS.index(slot.motion.kind) if slot.motion.kind in MOTION_LABELS else MOTION_LABELS.index("unknown")
            for slot in template.slots
        ],
        dtype=torch.long,
    )
    overlay_per_slot = torch.tensor(
        [
            OVERLAY_LABELS.index(slot.overlay.region) if slot.overlay and slot.overlay.region in OVERLAY_LABELS else 0
            for slot in template.slots
        ],
        dtype=torch.long,
    )
    transition_per_boundary = torch.tensor(
        [
            TRANSITION_LABELS.index(slot.transition_out) if slot.transition_out in TRANSITION_LABELS else 0
            for slot in template.slots[:-1]
        ],
        dtype=torch.long,
    )

    return {
        "boundary": boundary,
        "slot_id": slot_ids,
        "motion": motion,
        "transition": transition,
        "overlay": overlay,
        "crop": crop,
        "motion_per_slot": motion_per_slot,
        "overlay_per_slot": overlay_per_slot,
        "transition_per_boundary": transition_per_boundary,
        "internal_boundary_times": torch.tensor(internal_boundaries, dtype=torch.float32),
    }


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
    transition_cycle = ["cut", "fade", "wipe", "cut", "fade", "wipe"]
    pattern_cycle = ["stripes", "diamond", "rings", "grid", "cross", "ellipse"]
    base_colors = [(210, 70, 70), (55, 170, 100), (65, 95, 210), (215, 170, 55), (165, 70, 210), (55, 195, 200)]
    accent_colors = [(255, 250, 235), (255, 235, 120), (240, 255, 245), (255, 245, 255), (235, 250, 255), (255, 240, 210)]

    reference_frames: List[np.ndarray] = []
    slots: List[EditSlot] = []
    slot_mapping_items: List[SlotMappingItem] = []
    cursor = 0.0

    for slot_id in range(1, num_slots + 1):
        duration = round(0.8 + 0.25 * slot_id + rng.uniform(0.05, 0.3), 2)
        total_frames = max(int(round(duration * fps)), 10)
        motion_kind = motion_cycle[(slot_id - 1) % len(motion_cycle)]
        overlay_region = overlay_cycle[(slot_id - 1) % len(overlay_cycle)]
        transition = transition_cycle[(slot_id - 1) % len(transition_cycle)]
        color = base_colors[(slot_id - 1) % len(base_colors)]
        accent = accent_colors[(slot_id - 1) % len(accent_colors)]
        pattern = pattern_cycle[(slot_id - 1) % len(pattern_cycle)]

        slot_reference_frames: List[np.ndarray] = []
        slot_replacement_frames: List[np.ndarray] = []
        for frame_idx in range(total_frames):
            ref_frame = _make_canvas(size, color)
            _draw_slot_pattern(
                ref_frame,
                slot_index=slot_id,
                frame_idx=frame_idx,
                total_frames=total_frames,
                motion_kind=motion_kind,
                overlay_region=overlay_region,
                pattern_kind=pattern,
                accent_color=accent,
            )
            slot_reference_frames.append(ref_frame)

            repl_color = tuple(int(min(255, channel + 18)) for channel in color)
            repl_frame = _make_canvas(size, repl_color)
            _draw_slot_pattern(
                repl_frame,
                slot_index=slot_id + 10,
                frame_idx=frame_idx,
                total_frames=total_frames,
                motion_kind="static",
                overlay_region="none",
                pattern_kind=pattern,
                accent_color=(245, 245, 245),
            )
            slot_replacement_frames.append(repl_frame)

        reference_frames.extend(slot_reference_frames)
        clip_id = f"clip_{slot_id}"
        clip_path = os.path.join(out_dir, f"replacement_clip_{slot_id:03d}.mp4")
        _write_video(clip_path, slot_replacement_frames, fps)
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
                motion=MotionSpec(kind=motion_kind, confidence=1.0, keyframes=[{"t": 0.0, "value": 0.0}, {"t": 1.0, "value": 1.0}]),
                crop=CropSpec(x=0.04 if slot_id % 2 else 0.0, y=0.03 if slot_id % 3 == 0 else 0.0, width=0.92, height=0.92),
                overlay=OverlaySpec(
                    has_overlay=overlay_region != "none",
                    region=overlay_region,
                    start_rel=0.12 if overlay_region != "full" else 0.0,
                    end_rel=0.88 if overlay_region != "full" else 1.0,
                    mask_confidence=1.0 if overlay_region != "none" else 0.0,
                )
                if overlay_region != "none"
                else None,
                style_vector=[float(slot_id), duration, float((slot_id - 1) % len(pattern_cycle))],
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
            style_embedding=[0.08 * i for i in range(8)],
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
        self._labels = build_frame_targets_from_template(self.sampled, self.template)

    def __len__(self) -> int:
        return 1

    def __getitem__(self, index: int) -> Dict[str, object]:
        if index != 0:
            raise IndexError(index)
        return {
            "frames": self._frames,
            "boundary_labels": self._labels["boundary"],
            "slot_id_per_frame": self._labels["slot_id"],
            "boundary_labels_per_frame": self._labels["boundary"],
            "motion_labels": self._labels["motion"],
            "motion_label_per_slot": self._labels["motion_per_slot"],
            "overlay_labels": self._labels["overlay"],
            "overlay_label_per_frame": self._labels["overlay"],
            "transition_labels": self._labels["transition"],
            "transition_label_per_boundary": self._labels["transition_per_boundary"],
            "crop_labels": self._labels["crop"],
            "ground_truth_template": self.template,
        }
