from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import torch

from .object_detector import Detection


@dataclass
class ObjectMask:
    object_label: str
    timestamp: float
    frame_index: int
    mask: np.ndarray
    bbox: List[float]
    confidence: float
    mask_path: Optional[str] = None


def _bbox_to_mask(frame_shape, bbox: List[float]) -> np.ndarray:
    height, width = frame_shape[-2], frame_shape[-1]
    x = max(0, min(width - 1, int(round(bbox[0] * width))))
    y = max(0, min(height - 1, int(round(bbox[1] * height))))
    w = max(1, int(round(bbox[2] * width)))
    h = max(1, int(round(bbox[3] * height)))
    mask = np.zeros((height, width), dtype=np.uint8)
    mask[y : min(height, y + h), x : min(width, x + w)] = 1
    return mask


def segment_objects(
    frames,
    detections,
    backend: str = "auto",
) -> list[ObjectMask]:
    resolved = "bbox_mask" if backend in {"auto", "bbox_mask"} else backend
    if resolved == "sam2_optional":
        return []
    if resolved != "bbox_mask":
        return []
    if isinstance(frames, torch.Tensor):
        frame_shape = frames.shape
    else:
        frame_shape = np.asarray(frames).shape
    masks: List[ObjectMask] = []
    for detection in detections:
        masks.append(
            ObjectMask(
                object_label=detection.label,
                timestamp=detection.timestamp,
                frame_index=detection.frame_index,
                mask=_bbox_to_mask(frame_shape, detection.bbox),
                bbox=list(detection.bbox),
                confidence=float(detection.confidence),
                mask_path=None,
            )
        )
    return masks
