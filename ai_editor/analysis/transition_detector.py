"""Detect text transition types (fade-in / fade-out / cut) around OCR span boundaries."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    import cv2
except Exception:
    cv2 = None  # type: ignore

try:
    import numpy as np
except Exception:
    np = None  # type: ignore


def _sample_bbox_brightness(
    cap,
    timestamp: float,
    bbox_norm: List[List[float]],
    src_w: int,
    src_h: int,
) -> Optional[float]:
    """Return mean pixel brightness inside the bbox at timestamp, or None on failure."""
    if cv2 is None or np is None or timestamp < 0:
        return None
    cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
    ret, frame = cap.read()
    if not ret or frame is None:
        return None
    x_coords = [pt[0] * src_w for pt in bbox_norm]
    y_coords = [pt[1] * src_h for pt in bbox_norm]
    x1 = max(0, int(min(x_coords)))
    x2 = min(src_w, int(max(x_coords)) + 1)
    y1 = max(0, int(min(y_coords)))
    y2 = min(src_h, int(max(y_coords)) + 1)
    if x2 <= x1 or y2 <= y1:
        return None
    crop = frame[y1:y2, x1:x2]
    return float(np.mean(crop)) if crop.size > 0 else None


def _is_fade(brightnesses: List[float]) -> bool:
    """Return True when brightness changes gradually (fade) rather than in one jump (cut)."""
    if len(brightnesses) < 3:
        return False
    total_change = abs(brightnesses[-1] - brightnesses[0])
    if total_change < 8.0:
        # Barely any change — not conclusive enough to call it a fade
        return False
    diffs = [abs(brightnesses[i + 1] - brightnesses[i]) for i in range(len(brightnesses) - 1)]
    max_single_step = max(diffs)
    # A fade spreads the change across many steps; a cut concentrates it in one
    return max_single_step < 0.6 * total_change


def detect_text_transitions(
    cap,
    span_start: float,
    span_end: float,
    bbox_norm: List[List[float]],
    src_width: int,
    src_height: int,
    window_sec: float = 0.4,
    n_samples: int = 6,
) -> Dict[str, str]:
    """Analyse brightness inside the text bbox just before/after a text span to classify transitions.

    cap:        An already-opened cv2.VideoCapture (seekable).
    span_start: Timestamp (s) when the text first appears.
    span_end:   Timestamp (s) when the text last appears.
    bbox_norm:  Normalised 4-point bbox [[x1,y1],...] in [0,1] range.
    src_width/src_height: Original frame dimensions.
    window_sec: How many seconds before/after the boundary to sample.
    n_samples:  Number of brightness samples per window.

    Returns {"transition_in": "fade_in"|"cut", "transition_out": "fade_out"|"cut"}.
    """
    if cv2 is None or np is None or not bbox_norm:
        return {"transition_in": "cut", "transition_out": "cut"}

    step = window_sec / max(1, n_samples - 1)

    # Frames leading up to text appearance (transition in)
    in_times = [span_start - window_sec + i * step for i in range(n_samples)]
    in_brightness: List[float] = []
    for t in in_times:
        b = _sample_bbox_brightness(cap, t, bbox_norm, src_width, src_height)
        if b is not None:
            in_brightness.append(b)

    # Frames after text disappears (transition out)
    out_times = [span_end + i * step for i in range(n_samples)]
    out_brightness: List[float] = []
    for t in out_times:
        b = _sample_bbox_brightness(cap, t, bbox_norm, src_width, src_height)
        if b is not None:
            out_brightness.append(b)

    return {
        "transition_in": "fade_in" if _is_fade(in_brightness) else "cut",
        "transition_out": "fade_out" if _is_fade(out_brightness) else "cut",
    }
