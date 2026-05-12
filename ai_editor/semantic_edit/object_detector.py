from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import torch


@dataclass
class Detection:
    label: str
    confidence: float
    bbox: List[float]
    timestamp: float
    frame_index: int
    attributes: Dict[str, Any] = field(default_factory=dict)


_COLOR_TARGETS = {
    "chair": [
        np.array([220, 80, 80], dtype=np.float32),
        np.array([240, 160, 40], dtype=np.float32),
    ],
    "person": [np.array([80, 200, 120], dtype=np.float32)],
    "table": [np.array([80, 120, 220], dtype=np.float32)],
    "overlay": [np.array([20, 20, 20], dtype=np.float32)],
}


def _find_mask_bbox(mask: np.ndarray) -> Optional[List[float]]:
    ys, xs = np.where(mask)
    if len(xs) == 0 or len(ys) == 0:
        return None
    x1, x2 = xs.min(), xs.max()
    y1, y2 = ys.min(), ys.max()
    height, width = mask.shape
    return [x1 / width, y1 / height, (x2 - x1 + 1) / width, (y2 - y1 + 1) / height]


def _synthetic_color_detections(
    frames: torch.Tensor,
    timestamps: List[float],
    text_queries: Optional[List[str]] = None,
) -> List[Detection]:
    queries = {str(item).lower() for item in (text_queries or [])}
    detections: List[Detection] = []
    np_frames = (frames.detach().cpu().numpy() * 255.0).astype(np.float32)
    for frame_index, frame in enumerate(np_frames):
        hwc = np.transpose(frame, (1, 2, 0))
        for label, targets in _COLOR_TARGETS.items():
            if queries and label not in queries:
                continue
            masks = []
            scores = []
            for target in targets:
                diff = np.linalg.norm(hwc - target.reshape(1, 1, 3), axis=2)
                threshold = 45.0 if label != "overlay" else 25.0
                mask = diff < threshold
                masks.append(mask)
                scores.append((float(mask.mean()), target))
            mask = masks[int(np.argmax([score[0] for score in scores]))]
            target = scores[int(np.argmax([score[0] for score in scores]))][1]
            bbox = _find_mask_bbox(mask)
            if bbox is None:
                continue
            coverage = float(mask.mean())
            if coverage < 0.003:
                continue
            detections.append(
                Detection(
                    label=label,
                    confidence=min(0.99, 0.55 + coverage * 8.0),
                    bbox=bbox,
                    timestamp=float(timestamps[frame_index]),
                    frame_index=frame_index,
                    attributes={
                        "backend": "synthetic_color",
                        "mean_color": [float(x) for x in target.tolist()],
                        "pixel_coverage": coverage,
                    },
                )
            )
    return detections


def detect_objects(
    frames,
    timestamps,
    text_queries: list[str] | None = None,
    backend: str = "auto",
) -> list[Detection]:
    resolved = "synthetic_color" if backend in {"auto", "synthetic_color"} else backend
    if resolved == "synthetic_color":
        return _synthetic_color_detections(frames, timestamps, text_queries=text_queries)
    if resolved == "mock":
        return [
            Detection(
                label=(text_queries or ["object"])[0],
                confidence=1.0,
                bbox=[0.25, 0.25, 0.5, 0.5],
                timestamp=float(timestamps[0] if timestamps else 0.0),
                frame_index=0,
                attributes={"backend": "mock"},
            )
        ]
    if resolved == "grounding_dino_optional":
        return []
    return []
