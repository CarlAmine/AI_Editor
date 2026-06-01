"""Build user-facing text overlay plans from reference analysis."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

DEFAULT_TEXT_STYLE = {"box": False, "stroke": True, "shadow": False, "font_size": 42}


def _find_slot_id(slots: List[dict], timestamp: float) -> Optional[int]:
    for slot in slots:
        start = float(slot.get("start_time", 0.0))
        end = float(slot.get("end_time", start))
        if start <= timestamp < end:
            return int(slot.get("slot_id", 0)) or None
    return int(slots[0]["slot_id"]) if slots else None


def _merge_ocr_spans(spans: List[dict], gap: float = 1.5) -> List[Tuple[float, float, str]]:
    """Merge OCR spans that are close in time into single overlay windows."""
    parsed: List[Tuple[float, str]] = []
    for span in spans:
        if isinstance(span, dict):
            text = str(span.get("text", "")).strip()
            timestamp = float(span.get("timestamp", 0.0))
        else:
            text = str(getattr(span, "text", "")).strip()
            timestamp = float(getattr(span, "timestamp", 0.0))
        if not text or text.lower() in {"no text", "n/a"}:
            continue
        parsed.append((timestamp, text))

    if not parsed:
        return []

    parsed.sort(key=lambda item: item[0])
    merged: List[Tuple[float, float, str]] = []
    window_start = parsed[0][0]
    window_end = parsed[0][0] + 1.0
    texts: List[str] = [parsed[0][1]]

    for timestamp, text in parsed[1:]:
        if timestamp - window_end <= gap:
            window_end = max(window_end, timestamp + 1.0)
            if text not in texts:
                texts.append(text)
        else:
            merged.append((window_start, window_end, " ".join(texts)))
            window_start = timestamp
            window_end = timestamp + 1.0
            texts = [text]
    merged.append((window_start, window_end, " ".join(texts)))
    return merged


def build_text_overlays_from_analysis(
    analysis_results: dict,
    slots: Optional[List[dict]] = None,
) -> List[Dict[str, Any]]:
    """
    Extract detected on-screen text windows for chat confirmation.

    Does not auto-render text; action defaults to ask_user with empty render_text.
    """
    slots = slots or []
    windows: List[Tuple[float, float, str, bool]] = []

    ocr_spans = analysis_results.get("ocr_spans") or []
    for start, end, text in _merge_ocr_spans(ocr_spans):
        windows.append((start, end, text, True))

    keyframes = analysis_results.get("keyframes") or []
    for keyframe in keyframes:
        if not isinstance(keyframe, dict):
            continue
        detected = str(keyframe.get("detected_text", "")).strip()
        if not detected or detected.lower() in {"no text", "n/a"}:
            continue
        try:
            timestamp = float(keyframe.get("timestamp", 0.0))
        except (TypeError, ValueError):
            continue
        start = timestamp
        end = timestamp + 1.2
        windows.append((start, end, detected, False))

    if not windows:
        return []

    windows.sort(key=lambda item: item[0])
    deduped: List[Tuple[float, float, str, bool]] = []
    for start, end, text, approximate in windows:
        if deduped:
            prev_start, prev_end, prev_text, prev_approx = deduped[-1]
            if abs(start - prev_start) < 0.35 and text == prev_text:
                deduped[-1] = (prev_start, max(prev_end, end), prev_text, prev_approx or approximate)
                continue
        deduped.append((start, end, text, approximate))

    overlays: List[Dict[str, Any]] = []
    for index, (start, end, text, approximate) in enumerate(deduped, start=1):
        slot_id = _find_slot_id(slots, start)
        overlays.append(
            {
                "overlay_id": f"text_{index}",
                "slot_id": slot_id,
                "start": round(start, 3),
                "end": round(max(end, start + 0.2), 3),
                "detected_text": text,
                "render_text": "",
                "action": "ask_user",
                "position": "center",
                "approximate_timing": approximate,
                "style": dict(DEFAULT_TEXT_STYLE),
            }
        )
    return overlays


def summarize_text_overlays_for_chat(overlays: List[Dict[str, Any]]) -> str:
    if not overlays:
        return ""
    lines = [f"Detected text moments: {len(overlays)}", ""]
    for overlay in overlays[:6]:
        start = overlay.get("start", 0.0)
        end = overlay.get("end", start)
        text = overlay.get("detected_text", "")
        approx = " (approximate timing)" if overlay.get("approximate_timing") else ""
        lines.append(f"{start:.1f}s - {end:.1f}s{approx}: {text}")
    if len(overlays) > 6:
        lines.append(f"... and {len(overlays) - 6} more")
    lines.extend(["", "Use the text replacement form below to remove, keep, or replace each moment."])
    return "\n".join(lines)
