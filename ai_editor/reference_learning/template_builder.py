from __future__ import annotations
import os
from typing import Any, Dict, List, Optional
from ai_editor.edit_contracts.reference_template import ReferenceSlot, ReferenceEditTemplate

def build_reference_edit_template(
    analysis: Dict[str, Any],
    primary_video_path: str,
    job_id: str,
    requirements: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    # Extract metadata
    meta = analysis.get("metadata") or analysis.get("video_metadata") or {}
    duration = float(meta.get("duration_seconds", 0.0) or 0.0)
    fps = meta.get("fps")
    if fps is not None:
        fps = float(fps)
    width = meta.get("width")
    if width is not None:
        width = int(width)
    height = meta.get("height")
    if height is not None:
        height = int(height)

    # Extract scenes
    scenes_data = analysis.get("scenes") or []
    slots: List[ReferenceSlot] = []
    num_scenes = len(scenes_data)

    if not duration and num_scenes > 0:
        duration = float(max((s.get("end_time") or s.get("end", 0.0) for s in scenes_data), default=0.0))

    # Extract motion effects
    motion_effects_manifest = analysis.get("motion_effects") or {}
    effects_list = []
    if isinstance(motion_effects_manifest, dict):
        effects_list = motion_effects_manifest.get("effects") or []

    # Extract transitions
    transitions_list = analysis.get("transitions") or []

    # Extract style profile
    style_profile = analysis.get("style_profile") or {}

    # Gather style tags
    style_tags = []
    avg_shot_length = style_profile.get("avg_shot_length")
    pacing_label = style_profile.get("pacing_label", "")
    if avg_shot_length is not None and float(avg_shot_length) < 3.0:
        style_tags.append("fast_pacing")
    elif "fast" in str(pacing_label).lower():
        style_tags.append("fast_pacing")
    
    ocr_spans = analysis.get("ocr_spans") or []
    keyframes = analysis.get("keyframes") or []
    
    if len(ocr_spans) > 5:
        style_tags.append("dense_text")
        style_tags.append("high_ocr_density")
    if duration and duration < 60.0:
        style_tags.append("short_form")

    for idx, scene in enumerate(scenes_data):
        slot_id = idx + 1
        
        # Timing
        start = float(scene.get("start_time") or scene.get("start", 0.0) or 0.0)
        end = float(scene.get("end_time") or scene.get("end", start) or 0.0)
        slot_duration = float(scene.get("duration", end - start) or 0.0)
        
        # Role
        if slot_id == 1:
            role = "hook"
        elif slot_id == num_scenes:
            role = "outro"
        else:
            role = "main"

        # OCR/Keyframe text attachment
        slot_texts = []
        # Check ocr_spans
        for ocr in ocr_spans:
            t = ocr.get("timestamp")
            if t is not None:
                t = float(t)
                if start <= t <= end:
                    txt = str(ocr.get("text", "")).strip()
                    if txt and txt not in slot_texts:
                        slot_texts.append(txt)

        # Check keyframes
        for kf in keyframes:
            t = kf.get("timestamp")
            if t is not None:
                t = float(t)
                if start <= t <= end:
                    txt = str(kf.get("detected_text", "")).strip()
                    if txt:
                        for part in txt.split(";"):
                            part_clean = part.strip()
                            if part_clean and part_clean not in slot_texts:
                                slot_texts.append(part_clean)

        text_ref = None
        if slot_texts:
            text_ref = {
                "value": " ".join(slot_texts),
                "words": slot_texts,
                "density": len(slot_texts),
            }

        # Transition out
        # Find transition outgoing matching idx (incoming idx is idx + 1)
        transition_out = {"type": "hard_cut", "duration": 0.0}
        for trans in transitions_list:
            out_idx = trans.get("outgoing_shot_index")
            if out_idx is not None and int(out_idx) == idx:
                transition_out = {
                    "type": str(trans.get("transition_type", "hard_cut")),
                    "duration": float(trans.get("duration", 0.0) or 0.0),
                }
                break

        # Motion effect
        motion = None
        for effect in effects_list:
            shot_idx = effect.get("shot_index")
            if shot_idx is not None and int(shot_idx) == idx:
                motion = effect
                break

        slot = ReferenceSlot(
            slot_id=slot_id,
            start=start,
            end=end,
            duration=slot_duration,
            role=role,
            scene_id=scene.get("scene_id") or slot_id,
            text_ref=text_ref,
            transition_out=transition_out,
            motion=motion,
            style_tags=list(style_tags),
        )
        slots.append(slot)

    template = ReferenceEditTemplate(
        template_id=job_id,
        source_video_path=primary_video_path,
        duration=duration,
        fps=fps,
        width=width,
        height=height,
        slots=slots,
        transitions=list(transitions_list),
        overlays=list(analysis.get("overlays") or []),
        texts=list(analysis.get("texts") or []),
        motion_effects=list(effects_list),
        style_profile=dict(style_profile),
        audio_profile=dict(analysis.get("audio_profile") or {}),
        constraints=dict(analysis.get("constraints") or {}),
        warnings=list(analysis.get("warnings") or []),
    )
    return template.to_dict()
