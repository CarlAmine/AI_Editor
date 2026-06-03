"""Build user-facing text overlay plans from reference analysis."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

DEFAULT_TEXT_STYLE = {"box": False, "stroke": True, "shadow": False, "font_size": 42}


def _find_slot_id(slots: List[dict], timestamp: float) -> Optional[int]:
    for slot in slots:
        start = float(slot.get("start_time", 0.0))
        end = float(slot.get("end_time", start))
        if start <= timestamp < end:
            return int(slot.get("slot_id", 0)) or None
    return int(slots[0]["slot_id"]) if slots else None


def _merge_ocr_spans(spans: List[Any], gap: float = 1.5) -> List[Dict[str, Any]]:
    """Merge OCR spans close in time into overlay windows.

    Returns a list of dicts with start, end, text, bbox, extracted_style,
    transition_in, transition_out, detected_position.  The first span's
    spatial metadata is kept; transition_out is taken from the last span
    in each window.
    """
    parsed: List[Dict[str, Any]] = []
    for span in spans:
        if isinstance(span, dict):
            text = str(span.get("text", "")).strip()
            timestamp = float(span.get("timestamp", 0.0))
            bbox = span.get("bbox")
            extracted_style = span.get("extracted_style")
            transition_in = span.get("transition_in")
            transition_out = span.get("transition_out")
            detected_position = span.get("position")
        else:
            text = str(getattr(span, "text", "")).strip()
            timestamp = float(getattr(span, "timestamp", 0.0))
            bbox = getattr(span, "bbox", None)
            extracted_style = getattr(span, "extracted_style", None)
            transition_in = getattr(span, "transition_in", None)
            transition_out = getattr(span, "transition_out", None)
            detected_position = getattr(span, "position", None)

        if not text or text.lower() in {"no text", "n/a"}:
            continue
        parsed.append(
            {
                "timestamp": timestamp,
                "text": text,
                "bbox": bbox,
                "extracted_style": extracted_style,
                "transition_in": transition_in,
                "transition_out": transition_out,
                "detected_position": detected_position,
            }
        )

    if not parsed:
        return []

    parsed.sort(key=lambda item: item["timestamp"])

    merged: List[Dict[str, Any]] = []
    first = parsed[0]
    window_start = first["timestamp"]
    window_end = first["timestamp"] + 1.0
    texts: List[str] = [first["text"]]
    first_bbox = first["bbox"]
    first_style = first["extracted_style"]
    first_transition_in = first["transition_in"]
    last_transition_out = first["transition_out"]
    first_position = first["detected_position"]

    for item in parsed[1:]:
        timestamp = item["timestamp"]
        text = item["text"]
        if timestamp - window_end <= gap:
            window_end = max(window_end, timestamp + 1.0)
            if text not in texts:
                texts.append(text)
            if item["transition_out"]:
                last_transition_out = item["transition_out"]
        else:
            merged.append(
                {
                    "start": window_start,
                    "end": window_end,
                    "text": " ".join(texts),
                    "bbox": first_bbox,
                    "extracted_style": first_style,
                    "transition_in": first_transition_in,
                    "transition_out": last_transition_out,
                    "detected_position": first_position,
                }
            )
            window_start = timestamp
            window_end = timestamp + 1.0
            texts = [text]
            first_bbox = item["bbox"]
            first_style = item["extracted_style"]
            first_transition_in = item["transition_in"]
            last_transition_out = item["transition_out"]
            first_position = item["detected_position"]

    merged.append(
        {
            "start": window_start,
            "end": window_end,
            "text": " ".join(texts),
            "bbox": first_bbox,
            "extracted_style": first_style,
            "transition_in": first_transition_in,
            "transition_out": last_transition_out,
            "detected_position": first_position,
        }
    )
    return merged


def build_text_overlays_from_analysis(
    analysis_results: dict,
    slots: Optional[List[dict]] = None,
) -> List[Dict[str, Any]]:
    """Extract detected on-screen text windows for chat confirmation.

    Does not auto-render text; action defaults to ask_user with empty render_text.
    Carries bbox (normalized [0-1] coords), extracted_style, transition types, and
    source video dimensions so the renderer can replicate position and style exactly.
    """
    slots = slots or []
    video_meta = analysis_results.get("video_metadata") or {}
    src_width = int(video_meta.get("width", 0))
    src_height = int(video_meta.get("height", 0))

    # Each window: dict with start, end, text, approximate, bbox, extracted_style,
    # transition_in, transition_out, detected_position
    windows: List[Dict[str, Any]] = []

    ocr_spans = analysis_results.get("ocr_spans") or []
    for merged in _merge_ocr_spans(ocr_spans):
        windows.append(
            {
                "start": merged["start"],
                "end": merged["end"],
                "text": merged["text"],
                "approximate": True,
                "bbox": merged.get("bbox"),
                "extracted_style": merged.get("extracted_style"),
                "transition_in": merged.get("transition_in"),
                "transition_out": merged.get("transition_out"),
                "detected_position": merged.get("detected_position"),
            }
        )

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
        windows.append(
            {
                "start": timestamp,
                "end": timestamp + 1.2,
                "text": detected,
                "approximate": False,
                "bbox": None,
                "extracted_style": None,
                "transition_in": None,
                "transition_out": None,
                "detected_position": None,
            }
        )

    if not windows:
        return []

    windows.sort(key=lambda item: item["start"])

    # Deduplicate windows that start within 350 ms with identical text
    deduped: List[Dict[str, Any]] = []
    for window in windows:
        if deduped:
            prev = deduped[-1]
            if abs(window["start"] - prev["start"]) < 0.35 and window["text"] == prev["text"]:
                prev["end"] = max(prev["end"], window["end"])
                prev["approximate"] = prev["approximate"] or window["approximate"]
                continue
        deduped.append(window)

    overlays: List[Dict[str, Any]] = []
    for index, window in enumerate(deduped, start=1):
        slot_id = _find_slot_id(slots, window["start"])

        # Build style: start from default then layer extracted info on top
        overlay_style = dict(DEFAULT_TEXT_STYLE)
        ext_style = window.get("extracted_style") or {}
        if ext_style.get("has_background"):
            overlay_style["box"] = True
        if ext_style.get("font_size_est"):
            overlay_style["font_size"] = int(ext_style["font_size_est"])

        overlays.append(
            {
                "overlay_id": f"text_{index}",
                "slot_id": slot_id,
                "start": round(window["start"], 3),
                "end": round(max(window["end"], window["start"] + 0.2), 3),
                "detected_text": window["text"],
                "render_text": "",
                "action": "ask_user",
                "position": "center",
                "approximate_timing": window["approximate"],
                "style": overlay_style,
                # Spatial + style metadata for 1:1 replication
                "bbox": window.get("bbox"),
                "extracted_style": ext_style or None,
                "transition_in": window.get("transition_in"),
                "transition_out": window.get("transition_out"),
                "src_width": src_width,
                "src_height": src_height,
                "detected_position": window.get("detected_position"),
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
        pos = overlay.get("detected_position")
        pos_str = f" [{pos}]" if pos else ""
        lines.append(f"{start:.1f}s - {end:.1f}s{approx}{pos_str}: {text}")
    if len(overlays) > 6:
        lines.append(f"... and {len(overlays) - 6} more")
    lines.extend(["", "Use the text replacement form below to remove, keep, or replace each moment."])
    return "\n".join(lines)
