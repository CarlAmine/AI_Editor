# ai_editor/chat_intake/extractors.py

import re
from typing import Any, Dict, List, Optional, Tuple

URL_REGEX = re.compile(
    r'(https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*))'
)

def extract_urls(text: str) -> List[str]:
    return [url.strip(".,()[]{}<>\"'") for url in URL_REGEX.findall(text)]

def classify_url(url: str) -> str:
    url_lower = url.lower()
    if "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "youtube"
    if "tiktok.com" in url_lower:
        return "tiktok"
    if "drive.google.com" in url_lower:
        return "drive_folder"
    if any(url_lower.endswith(ext) for ext in [".mp4", ".mov", ".mkv", ".webm", ".avi", ".mp3", ".wav", ".aac"]):
        return "direct_video"
    return "unknown"

def extract_time_range(text: str) -> Optional[Tuple[float, float]]:
    def to_seconds(t_str: str) -> Optional[float]:
        try:
            parts = t_str.split(":")
            if len(parts) == 1:
                return float(parts[0])
            elif len(parts) == 2:
                return float(parts[0]) * 60 + float(parts[1])
            elif len(parts) == 3:
                return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        except Exception:
            pass
        return None

    m1 = re.search(r'(\d+(?::\d+){0,2})\s*[-–—to]+\s*(\d+(?::\d+){0,2})', text.lower())
    if m1:
        s = to_seconds(m1.group(1))
        e = to_seconds(m1.group(2))
        if s is not None and e is not None and s < e:
            return (s, e)
    return None

def extract_output_settings(text: str) -> Dict[str, Any]:
    text_low = text.lower()
    res = {}
    
    # Aspect Ratio and Intent Mode
    if any(k in text_low for k in ["vertical", "9:16", "shorts", "tiktok", "reels", "reel", "short"]):
        res["intent_mode"] = "shorts"
        res["aspect_ratio"] = "9:16"
        res["output_mode"] = "crop_to_9x16"
    elif any(k in text_low for k in ["horizontal", "16:9", "youtube video", "youtube"]):
        res["intent_mode"] = "video"
        res["aspect_ratio"] = "16:9"
    elif any(k in text_low for k in ["square", "1:1"]):
        res["intent_mode"] = "video"
        res["aspect_ratio"] = "1:1"

    # Refit Mode
    if any(k in text_low for k in ["pad", "no crop", "keep full frame", "black bars", "letterbox"]):
        res["refit_mode"] = "pad"
    elif any(k in text_low for k in ["crop", "reframe", "fill screen", "fill", "crop center", "crop_center"]):
        res["refit_mode"] = "crop_center"

    return res

def extract_audio_settings(text: str) -> Dict[str, Any]:
    text_low = text.lower()
    res = {}

    if any(k in text_low for k in ["original audio", "original track", "keep original", "reference audio", "same audio"]):
        res["music_mode"] = "original"
    elif any(k in text_low for k in ["custom music", "custom audio", "new music", "background music", "bgm", "custom track", "my music"]):
        res["music_mode"] = "custom"

    urls = extract_urls(text)
    for url in urls:
        cls = classify_url(url)
        if cls in ["youtube", "direct_video", "unknown"]:
            res["custom_music_url"] = url
            break

    time_range = extract_time_range(text)
    if time_range:
        res["custom_music_segment"] = f"{int(time_range[0])}-{int(time_range[1])}"

    return res

def extract_slot_mapping(text: str, available_slots: List[Dict]) -> List[Dict]:
    mapping = []
    text_low = text.lower()
    
    urls = extract_urls(text)
    if not urls:
        return mapping

    # Parse slot mentions
    slot_matches = re.finditer(r'slot\s*(\d+)', text_low)
    slots_found = [int(m.group(1)) for m in slot_matches]

    if len(slots_found) == 1 and len(urls) == 1:
        slot_id = slots_found[0]
        url = urls[0]
        time_range = extract_time_range(text)
        entry = {
            "slot_id": slot_id,
            "clip_url": url
        }
        if time_range:
            entry["source_start"] = time_range[0]
            entry["source_end"] = time_range[1]
        mapping.append(entry)
    elif len(slots_found) > 1 and len(urls) == len(slots_found):
        for i, slot_id in enumerate(slots_found):
            mapping.append({
                "slot_id": slot_id,
                "clip_url": urls[i]
            })
    return mapping


def extract_text_overlay_preferences(
    text: str,
    current_overlays: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Parse user choices for detected reference text overlays."""
    if not current_overlays:
        return {}

    text_low = text.lower().strip()
    updated = [dict(item) for item in current_overlays]

    if any(
        phrase in text_low
        for phrase in (
            "remove all text",
            "no text",
            "no captions",
            "no caption",
            "without text",
            "skip text",
        )
    ):
        for overlay in updated:
            overlay["action"] = "remove"
            overlay["render_text"] = ""
        return {"text_overlays": updated, "text_overlays_resolved": True}

    if any(
        phrase in text_low
        for phrase in ("keep the same text", "keep same text", "keep text", "same text")
    ):
        for overlay in updated:
            overlay["action"] = "render"
            overlay["render_text"] = str(overlay.get("detected_text", "")).strip()
        return {"text_overlays": updated, "text_overlays_resolved": True}

    replace_match = re.search(
        r"(?:slot\s*)?(\d+)\s*(?:text|caption)?\s*(?:with|=|:)\s*['\"]?([^'\"]+)['\"]?",
        text,
        flags=re.IGNORECASE,
    )
    if replace_match:
        slot_id = int(replace_match.group(1))
        replacement = replace_match.group(2).strip()
        for overlay in updated:
            if int(overlay.get("slot_id") or 0) == slot_id:
                overlay["action"] = "render"
                overlay["render_text"] = replacement
        return {"text_overlays": updated, "text_overlays_resolved": True}

    time_match = re.search(
        r"['\"]([^'\"]+)['\"]\s*(?:from|between)\s*(\d+(?::\d+){0,2})\s*(?:to|-)\s*(\d+(?::\d+){0,2})",
        text,
        flags=re.IGNORECASE,
    )
    if time_match:
        replacement = time_match.group(1).strip()

        def _to_seconds(value: str) -> float:
            parts = value.split(":")
            if len(parts) == 1:
                return float(parts[0])
            if len(parts) == 2:
                return float(parts[0]) * 60 + float(parts[1])
            return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])

        start = _to_seconds(time_match.group(2))
        end = _to_seconds(time_match.group(3))
        for overlay in updated:
            if float(overlay.get("start", -1)) <= start < float(overlay.get("end", 0)) + 0.5:
                overlay["action"] = "render"
                overlay["render_text"] = replacement
                overlay["start"] = start
                overlay["end"] = end
        return {"text_overlays": updated, "text_overlays_resolved": True}

    if "no text overlays" in text_low or "text overlays resolved" in text_low:
        return {"text_overlays_resolved": True}

    return {}


def extract_all(text: str, current_state: Dict[str, Any]) -> Dict[str, Any]:
    extracted = {}
    phase = current_state.get("phase", "awaiting_reference")
    urls = extract_urls(text)

    # 1. URL classification based on phase
    if urls:
        if not current_state.get("primary_url") and phase == "awaiting_reference":
            # The first video URL is the reference video
            video_urls = [url for url in urls if classify_url(url) in ["youtube", "tiktok", "direct_video"]]
            if video_urls:
                extracted["primary_url"] = video_urls[0]
        elif phase == "awaiting_custom_music" or (phase == "awaiting_audio" and any(k in text.lower() for k in ["custom", "track", "music"])):
            # If awaiting custom music, the first URL is the custom music URL
            music_urls = [url for url in urls if classify_url(url) in ["youtube", "direct_video", "unknown"]]
            if music_urls:
                extracted["custom_music_url"] = music_urls[0]
                extracted["music_mode"] = "custom"
        else:
            # Treat them as replacement sources
            existing_urls = {src.get("url") if isinstance(src, dict) else src for src in current_state.get("sources", [])}
            new_sources = []
            for url in urls:
                cls = classify_url(url)
                if cls == "drive_folder":
                    extracted["google_drive_link"] = url
                elif cls in ["youtube", "tiktok", "direct_video"]:
                    if url != current_state.get("primary_url") and url not in existing_urls:
                        new_sources.append({
                            "label": len(current_state.get("sources", [])) + len(new_sources) + 1,
                            "url": url
                        })
            if new_sources:
                extracted["sources"] = current_state.get("sources", []) + new_sources

    # 2. Output Settings Extraction
    output_settings = extract_output_settings(text)
    extracted.update(output_settings)

    # 3. Audio Settings Extraction
    audio_settings = extract_audio_settings(text)
    for k, v in audio_settings.items():
        if k == "custom_music_url" and "custom_music_url" in extracted:
            continue
        extracted[k] = v

    # 4. Slot Mapping Extraction
    if current_state.get("reference_slots"):
        slot_mapping = extract_slot_mapping(text, current_state["reference_slots"])
        if slot_mapping:
            existing_mapping = {item["slot_id"]: item for item in current_state.get("slot_mapping", [])}
            for new_item in slot_mapping:
                existing_mapping[new_item["slot_id"]] = new_item
            extracted["slot_mapping"] = list(existing_mapping.values())

    # 5. Text overlay preferences
    if current_state.get("text_overlays"):
        text_prefs = extract_text_overlay_preferences(text, current_state["text_overlays"])
        extracted.update(text_prefs)

    return extracted
