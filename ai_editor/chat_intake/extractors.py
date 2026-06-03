# ai_editor/chat_intake/extractors.py

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from ai_editor.llm_client import chat_json

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


def _llm_extract(
    text: str,
    current_state: Dict[str, Any],
    classified_urls: List[Dict[str, str]],
) -> Optional[Dict[str, Any]]:
    phase = current_state.get("phase", "awaiting_reference")
    existing_source_urls = {
        src.get("url") if isinstance(src, dict) else src
        for src in current_state.get("sources") or []
    }
    text_overlays = current_state.get("text_overlays") or []

    context = {
        "phase": phase,
        "has_primary_url": bool(current_state.get("primary_url")),
        "reference_slots": current_state.get("reference_slots") or [],
        "sources_count": len(current_state.get("sources") or []),
        "existing_slot_mapping_ids": [
            item["slot_id"]
            for item in (current_state.get("slot_mapping") or [])
            if isinstance(item, dict)
        ],
        "music_mode": current_state.get("music_mode", ""),
        "has_text_overlays": bool(text_overlays),
        "text_overlays": text_overlays,
    }

    prompt = (
        "You are parsing a user message in a video editing chatbot intake flow.\n\n"
        f"Phase: {phase}\n"
        f"Context: {json.dumps(context, ensure_ascii=False)}\n"
        f"URLs detected in message: {json.dumps(classified_urls, ensure_ascii=False)}\n"
        "Existing source URLs (already added, do not re-add): "
        f"{json.dumps(list(existing_source_urls), ensure_ascii=False)}\n"
        f"User message: {json.dumps(text, ensure_ascii=False)}\n\n"
        "Extract ONLY what the user explicitly said. Return a JSON object. "
        "Omit any field not clearly mentioned.\n\n"
        "Fields you may return:\n"
        '- "primary_url": string — reference video URL; only when phase="awaiting_reference" '
        "and has_primary_url=false\n"
        '- "sources": array of {"label": int, "url": string} — replacement clips '
        "(not the reference video, not music, not a drive folder)\n"
        '- "google_drive_link": string — Google Drive folder URL\n'
        '- "music_mode": "original" | "custom"\n'
        '- "custom_music_url": string — music URL\n'
        '- "custom_music_segment": string — time range as "START-END" seconds, e.g. "30-90"\n'
        '- "aspect_ratio": "16:9" | "9:16" | "1:1"\n'
        '- "intent_mode": "video" | "shorts"\n'
        '- "output_mode": "crop_to_9x16" | "native_9x16"\n'
        '- "refit_mode": "crop_center" | "pad"\n'
        '- "slot_mapping": array of {"slot_id": int, "clip_url": string} — explicit slot assignments only\n'
        '- "text_overlays_action": "keep_all" | "remove_all" | "replace_one"\n'
        '- "text_overlay_replace": {"slot_id": int, "text": string}\n\n'
        "Signal rules:\n"
        '- vertical / 9:16 / shorts / tiktok / reels → intent_mode="shorts", aspect_ratio="9:16"\n'
        '- horizontal / 16:9 / youtube → intent_mode="video", aspect_ratio="16:9"\n'
        '- pad / black bars / letterbox / keep full frame → refit_mode="pad"\n'
        '- crop / fill screen → refit_mode="crop_center"\n'
        '- "original audio" / "keep audio" / "reference audio" / "same audio" / "keep original" '
        '→ music_mode="original"\n'
        '- "custom music" / "new music" / "background music" / "bgm" / "my music" '
        '→ music_mode="custom"\n'
        '- "no text" / "remove text" / "no captions" → text_overlays_action="remove_all"\n'
        '- "keep text" / "same text" / "keep captions" → text_overlays_action="keep_all"\n\n'
        "Return {} if nothing applies."
    )

    result = chat_json(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a structured data extractor for a video editing intake chatbot. "
                    "Output valid JSON only. Include only fields explicitly mentioned by the user."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
    )
    return result if isinstance(result, dict) else None


def _apply_llm_result(
    result: Dict[str, Any],
    current_state: Dict[str, Any],
) -> Dict[str, Any]:
    extracted: Dict[str, Any] = {}
    existing_source_urls = {
        src.get("url") if isinstance(src, dict) else src
        for src in current_state.get("sources") or []
    }
    primary_url = current_state.get("primary_url", "")

    if result.get("primary_url") and not primary_url:
        extracted["primary_url"] = result["primary_url"]

    if result.get("sources"):
        new_sources = [
            s for s in result["sources"]
            if isinstance(s, dict)
            and s.get("url")
            and s.get("url") not in existing_source_urls
            and s.get("url") != primary_url
        ]
        if new_sources:
            existing = list(current_state.get("sources") or [])
            for i, src in enumerate(new_sources):
                src["label"] = len(existing) + i + 1
            extracted["sources"] = existing + new_sources

    for field in ("google_drive_link", "custom_music_url"):
        if result.get(field):
            extracted[field] = result[field]

    if result.get("music_mode") in {"original", "custom"}:
        extracted["music_mode"] = result["music_mode"]

    if result.get("custom_music_segment"):
        extracted["custom_music_segment"] = str(result["custom_music_segment"])

    for field in ("aspect_ratio", "output_mode"):
        if result.get(field):
            extracted[field] = result[field]

    if result.get("intent_mode") in {"video", "shorts"}:
        extracted["intent_mode"] = result["intent_mode"]

    if result.get("refit_mode") in {"crop_center", "pad"}:
        extracted["refit_mode"] = result["refit_mode"]

    if result.get("slot_mapping"):
        existing_mapping = {
            item["slot_id"]: item
            for item in (current_state.get("slot_mapping") or [])
            if isinstance(item, dict) and "slot_id" in item
        }
        for item in result["slot_mapping"]:
            if isinstance(item, dict) and "slot_id" in item:
                existing_mapping[item["slot_id"]] = item
        extracted["slot_mapping"] = list(existing_mapping.values())

    text_overlays = current_state.get("text_overlays") or []
    action = result.get("text_overlays_action")
    if text_overlays and action:
        updated = [dict(item) for item in text_overlays]
        if action == "remove_all":
            for overlay in updated:
                overlay["action"] = "remove"
                overlay["render_text"] = ""
            extracted["text_overlays"] = updated
            extracted["text_overlays_resolved"] = True
        elif action == "keep_all":
            for overlay in updated:
                overlay["action"] = "render"
                overlay["render_text"] = str(overlay.get("detected_text", "")).strip()
            extracted["text_overlays"] = updated
            extracted["text_overlays_resolved"] = True
        elif action == "replace_one" and result.get("text_overlay_replace"):
            replace_info = result["text_overlay_replace"]
            slot_id = int(replace_info.get("slot_id", -1))
            new_text = str(replace_info.get("text", "")).strip()
            for overlay in updated:
                if int(overlay.get("slot_id") or 0) == slot_id:
                    overlay["action"] = "render"
                    overlay["render_text"] = new_text
            extracted["text_overlays"] = updated
            extracted["text_overlays_resolved"] = True

    return extracted


def _regex_extract_fallback(
    text: str,
    current_state: Dict[str, Any],
    urls: List[str],
) -> Dict[str, Any]:
    """Regex-based extraction used when no LLM provider is available."""
    extracted = {}
    phase = current_state.get("phase", "awaiting_reference")

    if urls:
        if not current_state.get("primary_url") and phase == "awaiting_reference":
            video_urls = [url for url in urls if classify_url(url) in ["youtube", "tiktok", "direct_video"]]
            if video_urls:
                extracted["primary_url"] = video_urls[0]
        elif phase == "awaiting_custom_music" or (
            phase == "awaiting_audio" and any(k in text.lower() for k in ["custom", "track", "music"])
        ):
            music_urls = [url for url in urls if classify_url(url) in ["youtube", "direct_video", "unknown"]]
            if music_urls:
                extracted["custom_music_url"] = music_urls[0]
                extracted["music_mode"] = "custom"
        else:
            existing_urls = {
                src.get("url") if isinstance(src, dict) else src
                for src in current_state.get("sources", [])
            }
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

    output_settings = extract_output_settings(text)
    extracted.update(output_settings)

    audio_settings = extract_audio_settings(text)
    for k, v in audio_settings.items():
        if k == "custom_music_url" and "custom_music_url" in extracted:
            continue
        extracted[k] = v

    if current_state.get("reference_slots"):
        slot_mapping = extract_slot_mapping(text, current_state["reference_slots"])
        if slot_mapping:
            existing_mapping = {item["slot_id"]: item for item in current_state.get("slot_mapping", [])}
            for new_item in slot_mapping:
                existing_mapping[new_item["slot_id"]] = new_item
            extracted["slot_mapping"] = list(existing_mapping.values())

    if current_state.get("text_overlays"):
        text_prefs = extract_text_overlay_preferences(text, current_state["text_overlays"])
        extracted.update(text_prefs)

    return extracted


def extract_all(text: str, current_state: Dict[str, Any]) -> Dict[str, Any]:
    urls = extract_urls(text)
    classified_urls = [{"url": url, "type": classify_url(url)} for url in urls]

    llm_result = _llm_extract(text, current_state, classified_urls)
    if llm_result is not None:
        return _apply_llm_result(llm_result, current_state)

    return _regex_extract_fallback(text, current_state, urls)
