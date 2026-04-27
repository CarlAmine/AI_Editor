from __future__ import annotations

from typing import Dict, Optional, Tuple

from .schemas import EditTemplate, SlotMapping
from .transfer_template import apply_template_to_clips


def build_render_spec_from_vision_template(
    template: EditTemplate,
    slot_mapping: SlotMapping,
    source_artifacts: Dict,
    requirements: Dict,
    existing_overlay_plan: Optional[dict] = None,
    existing_audio_plan: Optional[dict] = None,
) -> Tuple[dict, dict, dict]:
    source_lookup = {}
    for clip_id, artifact in (source_artifacts or {}).items():
        source_lookup[str(clip_id)] = artifact.path_or_url if hasattr(artifact, "path_or_url") else str(artifact)

    transfer = apply_template_to_clips(template, slot_mapping, available_sources=source_lookup)
    canonical_timeline = transfer["timeline"]
    overlay_timing = {
        "overlays": [
            {
                "index": index + 1,
                "start": row["start"],
                "end": row["end"],
                "length": row["duration"],
                "region": ((row.get("overlay") or {}).get("region") if row.get("overlay") else "unknown"),
                "text": "",
            }
            for index, row in enumerate(canonical_timeline)
            if row.get("overlay")
        ]
    }
    edit_summary = {
        "mode": "vision_template_learning",
        "slot_count": len(template.slots),
        "warnings": list(template.warnings) + list(transfer.get("warnings") or []),
        "preserved_total_duration": template.total_duration,
        "dominant_transition": template.global_style.dominant_transition,
    }
    for row in canonical_timeline:
        if row.get("motion", {}).get("kind") not in {"unknown", "static"}:
            row["transform"] = {
                "motion": row["motion"],
                "keyframes": row["motion"].get("keyframes", []),
            }
        row["transition"] = {"in": row.get("transitionIn"), "out": row.get("transitionOut")}

    return canonical_timeline, overlay_timing, edit_summary
