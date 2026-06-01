# ai_editor/chat_intake/payload_builder.py

from typing import Dict, Any

def build_pipeline_payload(state: Dict[str, Any]) -> Dict[str, Any]:
    primary_url = state.get("primary_url", "")
    sources = []
    for idx, src in enumerate(state.get("sources", [])):
        if isinstance(src, str):
            sources.append({
                "label": idx + 1,
                "url": src
            })
        elif isinstance(src, dict):
            sources.append({
                "label": src.get("label", idx + 1),
                "url": src.get("url", ""),
                "segments": src.get("segments")
            })

    prompt = state.get("prompt", "")
    if not prompt:
        lines = []
        lines.append("Replicate the editing style and rhythm of the reference video.")
        if primary_url:
            lines.append(f"Reference video: {primary_url}")
        if state.get("reference_style_summary"):
            lines.append(f"Style Summary: {state['reference_style_summary']}")
        if state.get("aspect_ratio"):
            lines.append(f"Output Format: {state['aspect_ratio']}")
        if state.get("refit_mode"):
            lines.append(f"Fitting Style: {state['refit_mode']}")
        if state.get("music_mode"):
            if state.get("music_mode") == "custom" and state.get("custom_music_url"):
                lines.append(f"Audio: Custom track from {state['custom_music_url']}")
                if state.get("custom_music_segment"):
                    lines.append(f"Audio segment: {state['custom_music_segment']}")
            else:
                lines.append("Audio: Original track from the reference video.")
        prompt = "\n".join(lines)

    music_mode = "custom" if state.get("music_mode") == "custom" else "original"
    
    aspect_ratio = state.get("aspect_ratio", "")
    intent_mode = state.get("intent_mode") or ("shorts" if aspect_ratio == "9:16" else "video")

    return {
        "primary_url": primary_url,
        "sources": sources,
        "prompt": prompt,
        "music_mode": music_mode,
        "custom_music_url": state.get("custom_music_url") if music_mode == "custom" else None,
        "custom_music_segment": state.get("custom_music_segment") if music_mode == "custom" else None,
        "google_drive_link": state.get("google_drive_link") or None,
        "requirements_state": {
            **state,
            "intent_mode": intent_mode,
            "aspect_ratio": aspect_ratio
        }
    }
