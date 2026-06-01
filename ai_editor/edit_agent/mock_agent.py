from __future__ import annotations

from typing import Any, Dict, List, Optional

from ai_editor.edit_contracts.reference_template import ReferenceEditTemplate
from ai_editor.edit_contracts.user_plan import UserPatchedPlan
from ai_editor.edit_contracts.source_inventory import SourceInventory
from ai_editor.edit_contracts.edit_graph import EditGraphClip, ExecutableEditGraph

def compile_with_mock_agent(
    reference_template: Dict[str, Any],
    user_patched_plan: Dict[str, Any],
    source_inventory: Dict[str, Any],
    requirements: Dict[str, Any],
) -> Dict[str, Any]:
    # Restore contracts
    template = ReferenceEditTemplate.from_dict(reference_template)
    patched_plan = UserPatchedPlan.from_dict(user_patched_plan)
    inventory = SourceInventory.from_dict(source_inventory)

    timeline: List[EditGraphClip] = []
    
    # Pre-map slot replacements by slot_id
    slot_reps = {r.slot_id: r for r in patched_plan.slot_replacements}
    # Pre-map text replacements by slot_id
    text_reps = {t.slot_id: t for t in patched_plan.text_replacements if t.slot_id is not None}
    
    warnings: List[str] = []

    # Generic or untargeted text replacement if any (we can use as fallback)
    fallback_new_text = next((t.new_text for t in patched_plan.text_replacements if t.slot_id is None), None)

    clips_list = inventory.clips
    num_clips = len(clips_list)

    for slot in template.slots:
        slot_id = slot.slot_id
        
        # 1. Determine clip
        replacement = slot_reps.get(slot_id)
        
        target_clip = None
        if replacement and replacement.clip_id:
            # Match by clip_id or label
            for c in clips_list:
                if c.clip_id == replacement.clip_id:
                    target_clip = c
                    break
        
        if target_clip is None and replacement and replacement.source_index is not None:
            # Match by source_index (1-indexed or 0-indexed?)
            idx = replacement.source_index
            if 0 <= idx < num_clips:
                target_clip = clips_list[idx]
            elif 0 <= (idx - 1) < num_clips:
                target_clip = clips_list[idx - 1]

        if target_clip is None:
            # Default fallback: clip matching slot index
            idx = slot_id - 1
            if 0 <= idx < num_clips:
                target_clip = clips_list[idx]
            elif num_clips > 0:
                # Cycle through clips
                target_clip = clips_list[idx % num_clips]

        # If no clips are available at all, raise warning/error or use dummy
        if target_clip is None:
            clip_id = f"missing_clip_slot_{slot_id}"
            video_src = None
            source_index = None
            source_start = 0.0
            candidate_segments = []
            warnings.append(f"No source clip available for slot {slot_id}; emitted placeholder clip id.")
        else:
            clip_id = target_clip.clip_id
            video_src = target_clip.path
            source_index = target_clip.source_index
            source_start = 0.0
            candidate_segments = target_clip.candidate_segments

        # 2. Timing
        duration = max(0.0, float(slot.duration or 0.0))
        if replacement and replacement.source_start is not None:
            source_start = float(replacement.source_start)
            if replacement.source_end is not None:
                duration = max(0.0, float(replacement.source_end) - source_start)
        elif candidate_segments:
            # Try to pick the best candidate segment (e.g. middle segment is best, or beginning if duration fits)
            # Find candidate whose duration is at least equal to slot.duration, or pick the first candidate
            best_cand = None
            for cand in candidate_segments:
                if cand.get("duration", 0.0) >= duration:
                    best_cand = cand
                    break
            if best_cand is None:
                best_cand = candidate_segments[0]
            
            source_start = float(best_cand.get("start", 0.0))
            # Keep slot duration unless it exceeds candidate duration
            cand_dur = float(best_cand.get("duration", duration))
            if duration > cand_dur:
                warnings.append(
                    f"Slot {slot_id} duration trimmed from {duration:.3f}s to candidate duration {cand_dur:.3f}s."
                )
                duration = cand_dur

        # 3. Text value
        text_val = ""
        # Replacement text takes priority
        if replacement and replacement.replacement_text is not None:
            text_val = replacement.replacement_text
        elif slot_id in text_reps:
            text_val = text_reps[slot_id].new_text
        elif slot.text_ref and slot.text_ref.get("value"):
            # Fallback to reference template text
            text_val = slot.text_ref["value"]
        elif fallback_new_text is not None:
            text_val = fallback_new_text

        text_obj = None
        if text_val:
            text_obj = {"value": text_val}

        # 4. Transitions & Motion
        transition_out = slot.transition_out
        motion_effects = []
        if slot.motion:
            motion_effects.append(slot.motion)

        # Style ops
        style_ops = [{"type": "match_reference_style", "strength": 0.5}]

        graph_clip = EditGraphClip(
            slot_id=slot_id,
            clip_id=clip_id,
            source_index=source_index,
            video_src=video_src,
            source_start=source_start,
            duration=duration,
            crop={},
            motion_effects=motion_effects,
            transition_out=transition_out,
            text=text_obj,
            style_ops=style_ops,
            metadata={"source_clip_id": clip_id, "slot_role": slot.role},
        )
        timeline.append(graph_clip)

    graph = ExecutableEditGraph(
        version="edit_graph_v1",
        timeline=timeline,
        global_style_ops=[{"type": "global_style_match", "strength": 0.5}],
        audio={"soundtrack_url": requirements.get("custom_music_url"), "mute_source_audio": True},
        warnings=[],
        model_metadata={"backend": "mock", "strategy": "slot_mapping_reference_duration"},
    )
    graph.warnings = warnings
    return graph.to_dict()
