from __future__ import annotations

from typing import Any, Dict, List, Optional

from ai_editor.edit_contracts.edit_graph import ExecutableEditGraph
from ai_editor.edit_contracts.source_inventory import SourceInventory
from ai_editor.edit_contracts.reference_template import ReferenceEditTemplate
from ai_editor.edit_contracts.render_contract import RenderCompileResult

def compile_edit_graph_to_render_spec(
    edit_graph: Dict[str, Any],
    source_inventory: Dict[str, Any],
    reference_template: Dict[str, Any],
    requirements: Dict[str, Any],
    existing_audio_plan: Optional[Dict[str, Any]] = None,
    existing_overlay_plan: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    # Restore contracts
    graph = ExecutableEditGraph.from_dict(edit_graph)
    inventory = SourceInventory.from_dict(source_inventory)
    template = ReferenceEditTemplate.from_dict(reference_template)

    canonical_timeline: List[Dict[str, Any]] = []
    warnings: List[str] = list(graph.warnings or [])
    cumulative_time = 0.0
    overlays_list: List[Dict[str, Any]] = []

    # Map slot_id to role for reference metadata
    slot_roles = {s.slot_id: s.role for s in template.slots}
    clips_by_id = {clip.clip_id: clip for clip in inventory.clips}

    for idx, c in enumerate(graph.timeline):
        index = idx + 1
        slot_id = c.slot_id
        duration = c.duration
        
        # Build cumulative start/end
        start = cumulative_time
        end = start + duration
        cumulative_time = end

        # Text mapping
        text_val = ""
        if isinstance(c.text, dict) and c.text.get("value"):
            text_val = str(c.text["value"])
        elif isinstance(c.text, str):
            text_val = c.text

        # If text is present, register it as overlay
        if text_val:
            overlays_list.append({
                "start": start,
                "end": end,
                "duration": duration,
                "text": text_val,
                "position": "bottom", # default placement
                "slot_id": slot_id,
            })

        inventory_clip = clips_by_id.get(c.clip_id)
        video_src = c.video_src or (inventory_clip.path if inventory_clip is not None else None)
        if not video_src:
            warnings.append(f"Slot {slot_id} has no resolved video source path.")

        row = {
            "index": index,
            "scene_id": slot_id,
            "label": f"slot_{slot_id:03d}",
            "start": start,
            "end": end,
            "duration": duration,
            "length": duration,
            "video_src": video_src,
            "videoSrc": video_src,
            "trim": c.source_start,
            "text": text_val,
            "text_start": start if text_val else 0.0,
            "text_end": end if text_val else 0.0,
            "metadata": {
                "slot_id": slot_id,
                "slot_role": slot_roles.get(slot_id, "main"),
                "clip_id": c.clip_id,
                "source_index": c.source_index,
                "motion_effects": c.motion_effects,
                "style_ops": c.style_ops,
                "transition_out": c.transition_out,
                **c.metadata,
            }
        }
        canonical_timeline.append(row)

    # Resolution mapping
    resolution = str(requirements.get("resolution", "1080x1920")).strip()
    
    # Audio fields mapping
    audio_plan = existing_audio_plan or {}
    soundtrack_url = audio_plan.get("soundtrack_url")
    use_reference_audio_bed = bool(audio_plan.get("use_reference_audio_bed"))
    mute_source_audio = bool(audio_plan.get("mute_source_audio", True))
    overlay_plan = existing_overlay_plan or {}

    # Refit / output modes
    output_mode = str(requirements.get("output_mode", "crop_to_9x16")).strip()
    refit_mode = str(requirements.get("refit_mode", "crop_center")).strip()

    render_spec = {
        "generation_mode": "reference_edit_agent",
        "resolution": resolution,
        "output_mode": output_mode,
        "refit_mode": refit_mode,
        "disable_auto_transitions": True,
        "soundtrack_url": soundtrack_url,
        "use_reference_audio_bed": use_reference_audio_bed,
        "mute_source_audio": mute_source_audio,
        "canonical_timeline": canonical_timeline,
        "overlay_timing": overlays_list,
        "overlay_plan": overlay_plan,
        "edit_graph": edit_graph,
        "edit_summary": {
            "strategy": "reference_edit_agent",
            "total_slots": len(graph.timeline),
            "final_duration": cumulative_time,
            "backend": graph.model_metadata.get("backend", "mock"),
        }
    }

    res = RenderCompileResult(
        render_spec=render_spec,
        canonical_timeline=canonical_timeline,
        warnings=warnings,
    )
    return res.to_dict()
