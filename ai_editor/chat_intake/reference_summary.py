# ai_editor/chat_intake/reference_summary.py

def infer_slot_role(slot_index: int, total_slots: int) -> str:
    if slot_index == 0:
        return "hook"
    if slot_index == total_slots - 1:
        return "outro"
    if total_slots > 3 and slot_index == total_slots - 2:
        return "climax"
    if slot_index == 1:
        return "reveal"
    return "b-roll"

def build_reference_slots(analysis_results: dict, duration: float) -> list:
    slots = []
    scenes = analysis_results.get("scenes") or []
    
    parsed_scenes = []
    for s in scenes:
        start_time = 0.0
        end_time = 0.0
        if isinstance(s, dict):
            start_time = s.get("start_time", 0.0)
            end_time = s.get("end_time", 0.0)
        else:
            try:
                start_time = getattr(s, "start_time", 0.0)
                end_time = getattr(s, "end_time", 0.0)
            except Exception:
                pass
        
        try:
            start_time = float(start_time)
            end_time = float(end_time)
        except (ValueError, TypeError):
            continue
            
        if end_time > start_time:
            parsed_scenes.append((start_time, end_time))

    if not parsed_scenes:
        segments = analysis_results.get("segments") or []
        for seg in segments:
            start_time = 0.0
            end_time = 0.0
            if isinstance(seg, dict):
                start_time = seg.get("start", 0.0)
                end_time = seg.get("end", 0.0)
            else:
                try:
                    start_time = getattr(seg, "start", 0.0)
                    end_time = getattr(seg, "end", 0.0)
                except Exception:
                    pass
            try:
                start_time = float(start_time)
                end_time = float(end_time)
            except (ValueError, TypeError):
                continue
            if end_time > start_time:
                parsed_scenes.append((start_time, end_time))

    if not parsed_scenes:
        if duration <= 0:
            duration = 15.0
        step = 5.0
        if duration > 30.0:
            step = 10.0
        curr = 0.0
        while curr < duration:
            next_t = min(curr + step, duration)
            if next_t - curr >= 1.0:
                parsed_scenes.append((curr, next_t))
            curr = next_t

    parsed_scenes.sort(key=lambda x: x[0])

    for i, (start, end) in enumerate(parsed_scenes):
        slot_id = i + 1
        dur = end - start
        role = infer_slot_role(i, len(parsed_scenes))
        slots.append({
            "slot_id": slot_id,
            "start_time": round(start, 2),
            "end_time": round(end, 2),
            "duration": round(dur, 2),
            "role": role,
            "description": f"Scene {slot_id} ({round(dur, 1)}s) - {role} visual element."
        })
    return slots

def build_reference_summary(analysis_results: dict, probe_metadata: dict) -> dict:
    meta_ref = analysis_results.get("metadata") or {}
    
    # Check if meta_ref is an object or dict
    if not isinstance(meta_ref, dict):
        try:
            meta_ref = meta_ref.to_dict() if hasattr(meta_ref, "to_dict") else {}
        except Exception:
            meta_ref = {}

    duration = float(probe_metadata.get("duration") or meta_ref.get("duration_seconds") or 0.0)
    fps = float(probe_metadata.get("fps") or meta_ref.get("fps") or 30.0)
    width = int(probe_metadata.get("width") or meta_ref.get("width") or 1920)
    height = int(probe_metadata.get("height") or meta_ref.get("height") or 1080)

    aspect_ratio = "16:9"
    if width > 0 and height > 0:
        ratio = width / height
        if abs(ratio - (9 / 16)) < 0.1:
            aspect_ratio = "9:16"
        elif abs(ratio - 1.0) < 0.1:
            aspect_ratio = "1:1"
        elif ratio < 1.0:
            aspect_ratio = "9:16"

    scenes = analysis_results.get("scenes") or []
    scene_count = len(scenes)

    style_profile = analysis_results.get("style_profile") or {}
    if style_profile:
        rhythm = style_profile.get("editing_rhythm", "")
        captions = style_profile.get("captions_style", "")
        transitions = style_profile.get("transitions_rhythm", "")
        style_summary = f"Editing Pacing: {rhythm or 'Dynamic'}. Captions: {captions or 'Sleek'}. Transitions: {transitions or 'Fast cuts'}."
    else:
        pacing = analysis_results.get("pacing") or {}
        pacing_cat = pacing.get("pacing_category", "medium-paced")
        style_summary = f"Dynamic style transfer with {pacing_cat} editing cadence, sharp cuts, and synchronized pacing."

    return {
        "duration_seconds": round(duration, 2),
        "fps": round(fps, 2),
        "width": width,
        "height": height,
        "aspect_ratio": aspect_ratio,
        "scene_count": scene_count,
        "style_summary": style_summary
    }

def summarize_reference_for_chat(
    summary: dict,
    slots: list,
    text_overlays: list | None = None,
) -> str:
    parts = []
    parts.append("Reference analysis is complete.")
    parts.append(
        f"Duration: {summary['duration_seconds']} seconds. "
        f"Format: {summary['aspect_ratio']} ({summary['width']}x{summary['height']} at {summary['fps']} FPS)."
    )
    parts.append(f"Style notes: {summary['style_summary']}")
    parts.append(f"Detected slots: {len(slots)}")
    if text_overlays:
        from ai_editor.chat_intake.text_overlays import summarize_text_overlays_for_chat

        overlay_msg = summarize_text_overlays_for_chat(text_overlays)
        if overlay_msg:
            parts.append(overlay_msg)
    parts.append("Use the forms below to enter replacement URLs and text changes.")
    return "\n".join(parts)
