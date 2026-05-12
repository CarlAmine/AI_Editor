from __future__ import annotations

import os
from typing import Dict, Optional

from .schemas import EditTemplate, SlotMapping, validate_slot_mapping


def _probe_source_duration(path: str) -> float:
    if not path or str(path).startswith(("http://", "https://")) or not os.path.exists(path):
        return 0.0
    try:
        import cv2

        capture = cv2.VideoCapture(path)
        if not capture.isOpened():
            return 0.0
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        frames = float(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
        capture.release()
        return (frames / fps) if fps > 0 else 0.0
    except Exception:
        return 0.0


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
        slot_warnings = []
        source_duration = _probe_source_duration(resolved)
        effective_available_duration = source_duration - trim_start if source_duration > trim_start else 0.0
        if trim_end is not None and source_duration > 0:
            effective_available_duration = max(0.0, min(effective_available_duration, trim_end - trim_start))
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
            "visible_objects": list(slot.visible_objects or []),
            "visible_layers": list(slot.visible_layers or []),
            "semantic_events": list(slot.semantic_events or []),
            "semantic_metadata": dict(slot.semantic_metadata or {}),
            "object_constraints": dict((slot.semantic_metadata or {}).get("object_constraints", {})),
            "source_duration": source_duration or None,
            "slot_warnings": slot_warnings,
        }
        if trim_end is not None and trim_end <= trim_start:
            message = f"Slot {slot.slot_id} trim range was invalid; falling back to trim_start only."
            warnings.append(message)
            slot_warnings.append(message)
            trim_end = None
        if source_duration > 0 and effective_available_duration + 1e-6 < float(slot.duration):
            message = (
                f"Slot {slot.slot_id} source clip appears shorter than learned slot duration "
                f"({effective_available_duration:.2f}s available vs {float(slot.duration):.2f}s required)."
            )
            warnings.append(message)
            slot_warnings.append(message)
            metadata["short_source_strategy"] = "preserve_template_duration"
            metadata["renderer_fallback_hint"] = "hold_last_frame_or_provider_default"

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
                "visible_objects": list(slot.visible_objects or []),
                "visible_layers": list(slot.visible_layers or []),
                "semantic_events": list(slot.semantic_events or []),
                "semantic_metadata": dict(slot.semantic_metadata or {}),
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
