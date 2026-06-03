"""Extract visual text style from a video frame crop bounded by an OCR bbox."""

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


def _rgb_to_hex(rgb) -> str:
    r = max(0, min(255, int(round(float(rgb[0])))))
    g = max(0, min(255, int(round(float(rgb[1])))))
    b = max(0, min(255, int(round(float(rgb[2])))))
    return f"#{r:02x}{g:02x}{b:02x}"


def _default_style() -> Dict[str, Any]:
    return {
        "text_color": "#ffffff",
        "bg_color": "#000000",
        "has_background": False,
        "font_size_est": 42,
        "is_bold": False,
        "font_style_hint": "regular",
    }


def extract_text_style(
    frame,
    bbox_norm: List[List[float]],
    src_width: int,
    src_height: int,
    text: Optional[str] = None,
) -> Dict[str, Any]:
    """Extract text color, background, font size, and style hint from an OCR bbox region.

    frame:      BGR numpy array (OpenCV frame).
    bbox_norm:  4-point bbox [[x1,y1],[x2,y2],[x3,y3],[x4,y4]] with coords in [0, 1].
    src_width/src_height: frame dimensions used to de-normalize the bbox.
    text:       The detected text string — used to estimate character proportions
                and classify the font style (impact / bold / regular).
    """
    if cv2 is None or np is None or frame is None:
        return _default_style()
    if not bbox_norm or len(bbox_norm) < 4:
        return _default_style()
    try:
        x_coords = [pt[0] * src_width for pt in bbox_norm]
        y_coords = [pt[1] * src_height for pt in bbox_norm]
        x1 = max(0, int(min(x_coords)))
        x2 = min(src_width, int(max(x_coords)) + 1)
        y1 = max(0, int(min(y_coords)))
        y2 = min(src_height, int(max(y_coords)) + 1)

        if x2 <= x1 or y2 <= y1:
            return _default_style()

        crop = frame[y1:y2, x1:x2]
        if crop.size == 0 or crop.shape[0] < 3 or crop.shape[1] < 3:
            return _default_style()

        crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

        # Otsu threshold separates text strokes from background
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        white_frac = float(np.mean(thresh == 255))
        # Text is the minority class (white text on dark, or dark text on light)
        text_mask = (thresh == 255) if white_frac < 0.5 else (thresh == 0)
        bg_mask = ~text_mask

        text_color = "#ffffff"
        bg_color = "#000000"
        if text_mask.sum() > 0:
            text_color = _rgb_to_hex(np.mean(crop_rgb[text_mask], axis=0))
        if bg_mask.sum() > 0:
            bg_color = _rgb_to_hex(np.mean(crop_rgb[bg_mask], axis=0))

        # Low variance in background region → solid background box present
        bg_std = float(np.std(gray[bg_mask])) if bg_mask.sum() > 10 else 100.0
        has_background = bg_std < 25.0

        # Height of the bbox in source pixels (used as fallback font_size_est)
        bbox_h_px = y2 - y1
        bbox_w_px = x2 - x1
        font_size_est = max(12, int(bbox_h_px * 0.85))

        # High text-pixel density → bold
        text_density = float(text_mask.sum()) / max(1, text_mask.shape[0] * text_mask.shape[1])
        is_bold = text_density > 0.4

        # ── Font style hint from character aspect ratio ───────────────────────
        # avg_char_ratio = (bbox_width / char_count) / bbox_height
        # Impact-style fonts are very narrow (~0.3-0.4 per char)
        # Bold sans-serif is ~0.45-0.55
        # Regular is ~0.55+
        font_style_hint = "regular"
        if text:
            char_count = max(1, len(text.replace(" ", "")))
            avg_char_ratio = (bbox_w_px / char_count) / max(1, bbox_h_px)
            if avg_char_ratio < 0.38:
                font_style_hint = "impact"
            elif avg_char_ratio < 0.56 or is_bold:
                font_style_hint = "bold"
        elif is_bold:
            font_style_hint = "bold"

        return {
            "text_color": text_color,
            "bg_color": bg_color,
            "has_background": has_background,
            "font_size_est": font_size_est,
            "is_bold": is_bold,
            "font_style_hint": font_style_hint,
        }
    except Exception:
        return _default_style()
