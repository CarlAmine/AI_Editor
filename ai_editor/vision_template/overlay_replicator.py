"""OverlayReplicator: pure OpenCV module that detects graphic overlays (circles,
shapes, text regions) in donor video frames via background-subtraction and contour
analysis, then alpha-composites them onto content video frames at matching
temporal positions.

No FFmpeg. No Shotstack. No neural network. Pure OpenCV + NumPy.
"""

from __future__ import annotations

import math
import os
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

try:
    import cv2
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "opencv-python is required for OverlayReplicator. "
        "Install with: pip install opencv-python"
    ) from exc

try:
    import numpy as np
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "numpy is required for OverlayReplicator. Install with: pip install numpy"
    ) from exc


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class OverlayRegion:
    frame_index: int
    timestamp: float
    mask: np.ndarray          # uint8, same size as the sampled frame; 0=bg, 255=overlay
    bbox: Tuple[int, int, int, int]   # (x, y, w, h)
    kind: str                 # "circle" | "rectangle" | "text_region" | "unknown"


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def detect_overlays(
    donor_video_path: str,
    fps: float = 4.0,
    size: Optional[int] = None,
) -> List[OverlayRegion]:
    """Detect graphic overlay regions in a donor video using background subtraction.

    Samples frames at `fps` rate.  For each frame, computes a rolling median of the
    last 5 frames as a background model, then thresholds the absolute difference to
    find foreground overlay regions.  Classifies contours as circle, rectangle,
    text_region, or unknown based on circularity and aspect ratio.

    Returns a list of OverlayRegion dataclass instances.
    """
    cap = cv2.VideoCapture(donor_video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open donor video: {donor_video_path}")

    native_fps = float(cap.get(cv2.CAP_PROP_FPS)) or 30.0
    interval = max(1, int(round(native_fps / max(fps, 0.1))))

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    gray_window: deque = deque(maxlen=5)
    frame_buffer: deque = deque(maxlen=5)   # keep raw frames for donor compositing

    regions: List[OverlayRegion] = []
    frame_index = 0
    sample_index = 0

    while True:
        ok, bgr = cap.read()
        if not ok:
            break

        if frame_index % interval == 0:
            if size is not None:
                bgr = cv2.resize(bgr, (size, size), interpolation=cv2.INTER_AREA)

            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            gray_window.append(gray)
            frame_buffer.append(bgr)

            timestamp = frame_index / native_fps

            if len(gray_window) >= 2:
                # Background = median of rolling window
                stack = np.stack(list(gray_window), axis=0)
                background = np.median(stack, axis=0).astype(np.uint8)

                diff = cv2.absdiff(gray, background)
                _, fg_mask = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
                fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)

                contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                h_frame, w_frame = gray.shape[:2]

                for contour in contours:
                    area = cv2.contourArea(contour)
                    if area < 200:
                        continue

                    perimeter = cv2.arcLength(contour, closed=True)
                    circularity = (4 * math.pi * area / (perimeter ** 2)) if perimeter > 0 else 0.0

                    x, y, w, h = cv2.boundingRect(contour)
                    aspect = w / max(h, 1)

                    if circularity > 0.75:
                        kind = "circle"
                    elif 0.8 <= aspect <= 5.0 and area < 8000:
                        kind = "text_region"
                    elif 0.5 <= aspect <= 2.0:
                        kind = "rectangle"
                    else:
                        kind = "unknown"

                    contour_mask = np.zeros((h_frame, w_frame), dtype=np.uint8)
                    cv2.drawContours(contour_mask, [contour], -1, 255, thickness=cv2.FILLED)

                    regions.append(
                        OverlayRegion(
                            frame_index=frame_index,
                            timestamp=timestamp,
                            mask=contour_mask,
                            bbox=(x, y, w, h),
                            kind=kind,
                        )
                    )

            sample_index += 1

        frame_index += 1

    cap.release()
    return regions


# ---------------------------------------------------------------------------
# Replication
# ---------------------------------------------------------------------------

def replicate_overlays(
    content_video_path: str,
    donor_video_path: str,
    out_path: str,
    blend_alpha: float = 0.85,
) -> Dict[str, Any]:
    """Composite donor overlay regions onto a content video at matching timestamps.

    For each content frame, finds the closest donor overlay group within 0.5 s and
    alpha-composites the overlay pixels from the donor frame onto the content frame.
    Uses OpenCV VideoWriter — no FFmpeg.

    Returns dict: out_path, overlay_count, frame_count.
    """
    # ── Detect overlays ────────────────────────────────────────────────────
    regions = detect_overlays(donor_video_path)

    # Group by rounded timestamp (0.1 s buckets)
    groups: Dict[float, List[OverlayRegion]] = {}
    for region in regions:
        key = round(region.timestamp, 1)
        groups.setdefault(key, []).append(region)
    group_keys = sorted(groups.keys())

    # ── Pre-load donor frames at matching timestamps ────────────────────────
    donor_cap = cv2.VideoCapture(donor_video_path)
    donor_fps = float(donor_cap.get(cv2.CAP_PROP_FPS)) or 30.0
    # Cache donor frames keyed by timestamp bucket
    donor_frames: Dict[float, np.ndarray] = {}
    donor_idx = 0
    while True:
        ok, bgr = donor_cap.read()
        if not ok:
            break
        t = round(donor_idx / donor_fps, 1)
        if t in groups:
            donor_frames[t] = bgr
        donor_idx += 1
    donor_cap.release()

    # ── Process content video ──────────────────────────────────────────────
    content_cap = cv2.VideoCapture(content_video_path)
    if not content_cap.isOpened():
        raise RuntimeError(f"Cannot open content video: {content_video_path}")

    content_fps = float(content_cap.get(cv2.CAP_PROP_FPS)) or 30.0
    content_w = int(content_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    content_h = int(content_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(out_path, fourcc, content_fps, (content_w, content_h))

    frame_count = 0
    overlay_count = 0

    while True:
        ok, content_bgr = content_cap.read()
        if not ok:
            break

        t = frame_count / content_fps

        # Find closest donor overlay group within 0.5 s
        best_key: Optional[float] = None
        best_dist = 0.5  # maximum allowed distance
        for key in group_keys:
            dist = abs(key - t)
            if dist < best_dist:
                best_dist = dist
                best_key = key

        if best_key is not None:
            donor_bgr = donor_frames.get(best_key)
            if donor_bgr is not None:
                donor_resized = cv2.resize(donor_bgr, (content_w, content_h), interpolation=cv2.INTER_LINEAR)

                for region in groups[best_key]:
                    mask_resized = cv2.resize(region.mask, (content_w, content_h), interpolation=cv2.INTER_NEAREST)
                    where = mask_resized > 0

                    content_pixels = content_bgr[where].astype(np.float32)
                    donor_pixels = donor_resized[where].astype(np.float32)
                    blended = (blend_alpha * donor_pixels + (1.0 - blend_alpha) * content_pixels)
                    content_bgr[where] = blended.clip(0, 255).astype(np.uint8)
                    overlay_count += 1

        writer.write(content_bgr)
        frame_count += 1

    content_cap.release()
    writer.release()
    print(f"[OverlayReplicator] {frame_count} frames written, {overlay_count} overlay composites applied → {out_path}")

    return {
        "out_path": out_path,
        "overlay_count": overlay_count,
        "frame_count": frame_count,
    }
