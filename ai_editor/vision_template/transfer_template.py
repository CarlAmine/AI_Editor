from __future__ import annotations

from typing import Dict, Optional

from .schemas import EditTemplate, SlotMapping, validate_slot_mapping


def apply_template_to_clips(
    template: EditTemplate,
    slot_mapping: SlotMapping,
    available_sources: Optional[Dict[str, str]] = None,
) -> dict:
    validate_slot_mapping(template, slot_mapping)
    available_sources = dict(available_sources or {})
    mapping_by_slot = slot_mapping.as_slot_dict()
    timeline = []
    warnings = []

    for slot in template.slots:
        item = mapping_by_slot[slot.slot_id]
        resolved = item.clip_path or item.clip_url
        if not resolved and item.clip_id:
            resolved = available_sources.get(item.clip_id)
        if not resolved:
            raise ValueError(f"Could not resolve media source for slot {slot.slot_id}.")

        trim_start = float(item.source_start or 0.0)
        trim_end = float(item.source_end) if item.source_end is not None else None
        trim = trim_start
        metadata = {
            "source_slot_id": slot.slot_id,
            "clip_id": item.clip_id,
            "learned_start": slot.start,
            "learned_end": slot.end,
            "learned_duration": slot.duration,
            "transition_in": slot.transition_in,
            "transition_out": slot.transition_out,
            "motion": slot.motion.model_dump() if hasattr(slot.motion, "model_dump") else slot.motion.dict(),
            "crop": slot.crop.model_dump() if hasattr(slot.crop, "model_dump") else slot.crop.dict(),
            "overlay": (slot.overlay.model_dump() if slot.overlay and hasattr(slot.overlay, "model_dump") else slot.overlay.dict()) if slot.overlay else None,
            "vision_template_confidence": slot.boundary_confidence,
            "source_start": item.source_start,
            "source_end": item.source_end,
        }
        if trim_end is not None and trim_end <= trim_start:
            warnings.append(f"Slot {slot.slot_id} trim range was invalid; falling back to trim_start only.")
            trim_end = None

        timeline.append(
            {
                "index": len(timeline) + 1,
                "scene_id": slot.slot_id,
                "label": f"vision_{slot.slot_id:03d}",
                "start": slot.start,
                "end": slot.end,
                "duration": slot.duration,
                "length": slot.duration,
                "video_src": resolved,
                "videoSrc": resolved,
                "trim": trim,
                "trim_end": trim_end,
                "transitionIn": slot.transition_in,
                "transitionOut": slot.transition_out,
                "transition": {"in": slot.transition_in, "out": slot.transition_out},
                "crop": (slot.crop.model_dump() if hasattr(slot.crop, "model_dump") else slot.crop.dict()),
                "motion": (slot.motion.model_dump() if hasattr(slot.motion, "model_dump") else slot.motion.dict()),
                "overlay": (
                    slot.overlay.model_dump() if slot.overlay and hasattr(slot.overlay, "model_dump") else slot.overlay.dict()
                )
                if slot.overlay
                else None,
                "metadata": metadata,
                "text": "",
                "text_start": slot.start,
                "text_end": slot.end,
            }
        )

    return {
        "timeline": timeline,
        "warnings": warnings,
        "summary": {
            "slot_count": len(template.slots),
            "preserved_duration": template.total_duration,
            "mapping_count": len(slot_mapping.items),
        },
    }
