from __future__ import annotations

from typing import Any, Dict, List

from ai_editor.edit_contracts.reference_template import ReferenceEditTemplate
from ai_editor.edit_contracts.source_inventory import SourceInventory

_ALLOWED_TOP_LEVEL_FIELDS = {
    "version",
    "timeline",
    "global_style_ops",
    "audio",
    "warnings",
    "model_metadata",
}
_ALLOWED_CLIP_FIELDS = {
    "slot_id",
    "clip_id",
    "source_index",
    "video_src",
    "source_start",
    "duration",
    "crop",
    "motion_effects",
    "transition_out",
    "text",
    "style_ops",
    "metadata",
}
_ALLOWED_TRANSITIONS = {"hard_cut", "flash_cut", "zoom_cut", "crossfade", "none"}
_ALLOWED_STYLE_OPS = {"match_reference_style", "match_reference_color", "preserve_source_style"}


def validate_edit_graph(
    edit_graph: Dict[str, Any],
    reference_template: Dict[str, Any],
    source_inventory: Dict[str, Any],
) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []
    checks: Dict[str, bool] = {}

    if not isinstance(edit_graph, dict):
        return {
            "valid": False,
            "score": 0.0,
            "errors": ["Edit graph must be a JSON object."],
            "warnings": [],
            "checks": {"is_object": False},
        }

    template = ReferenceEditTemplate.from_dict(reference_template)
    inventory = SourceInventory.from_dict(source_inventory)
    clips_by_id = {clip.clip_id: clip for clip in inventory.clips}
    slot_ids = {slot.slot_id for slot in template.slots}

    checks["known_top_level_fields"] = set(edit_graph.keys()).issubset(_ALLOWED_TOP_LEVEL_FIELDS)
    if not checks["known_top_level_fields"]:
        warnings.append(
            "Edit graph contains unsupported top-level fields: "
            + ", ".join(sorted(set(edit_graph.keys()) - _ALLOWED_TOP_LEVEL_FIELDS))
        )

    checks["valid_version"] = edit_graph.get("version") == "edit_graph_v1"
    if not checks["valid_version"]:
        errors.append("Edit graph version must be 'edit_graph_v1'.")

    timeline = edit_graph.get("timeline")
    checks["timeline_exists"] = "timeline" in edit_graph
    checks["timeline_is_list"] = isinstance(timeline, list)
    if not checks["timeline_exists"]:
        errors.append("Edit graph is missing 'timeline'.")
    elif not checks["timeline_is_list"]:
        errors.append("Edit graph 'timeline' must be a list.")
        timeline = []

    if isinstance(timeline, list) and not timeline and template.slots:
        errors.append("Edit graph timeline must not be empty when the reference template has slots.")
    checks["has_clips"] = bool(timeline)

    total_duration = 0.0
    seen_slot_ids = set()
    for index, clip in enumerate(timeline or []):
        prefix = f"Timeline clip at index {index}: "
        if not isinstance(clip, dict):
            errors.append(prefix + "timeline items must be objects.")
            continue

        unknown_fields = sorted(set(clip.keys()) - _ALLOWED_CLIP_FIELDS)
        if unknown_fields:
            warnings.append(prefix + f"unsupported clip fields present and ignored: {', '.join(unknown_fields)}")

        slot_id = clip.get("slot_id")
        if slot_id is None:
            errors.append(prefix + "missing slot_id.")
        else:
            try:
                slot_id = int(slot_id)
            except (TypeError, ValueError):
                errors.append(prefix + "slot_id must be an integer.")
            else:
                seen_slot_ids.add(slot_id)
                if slot_id not in slot_ids:
                    errors.append(prefix + f"slot_id {slot_id} is not present in the reference template.")

        clip_id = str(clip.get("clip_id") or "").strip()
        source_index = clip.get("source_index")
        video_src = clip.get("video_src")
        if not clip_id and source_index is None and not str(video_src or "").strip():
            errors.append(prefix + "must include clip_id or source_index unless video_src is explicitly set.")

        inventory_clip = None
        if clip_id:
            inventory_clip = clips_by_id.get(clip_id)
            if inventory_clip is None:
                errors.append(prefix + f"clip_id '{clip_id}' is not present in source_inventory.")
        if source_index is not None:
            try:
                source_index = int(source_index)
            except (TypeError, ValueError):
                errors.append(prefix + "source_index must be an integer when provided.")
            else:
                if inventory_clip is not None and inventory_clip.source_index != source_index:
                    warnings.append(
                        prefix + f"source_index {source_index} does not match inventory source_index {inventory_clip.source_index} for clip_id '{clip_id}'."
                    )

        try:
            source_start = float(clip.get("source_start", 0.0))
        except (TypeError, ValueError):
            errors.append(prefix + "source_start must be numeric.")
            source_start = 0.0
        else:
            if source_start < 0.0:
                errors.append(prefix + "source_start must be non-negative.")

        try:
            duration = float(clip.get("duration", 0.0))
        except (TypeError, ValueError):
            errors.append(prefix + "duration must be numeric.")
            duration = 0.0
        else:
            if duration <= 0.0:
                errors.append(prefix + "duration must be greater than 0.")
            else:
                total_duration += duration

        if inventory_clip is not None and inventory_clip.duration > 0:
            if source_start + duration > inventory_clip.duration + 0.05:
                errors.append(
                    prefix
                    + f"source segment overruns clip duration ({source_start + duration:.3f}s > {inventory_clip.duration:.3f}s)."
                )

        text = clip.get("text")
        if text is not None and not isinstance(text, (dict, str)):
            errors.append(prefix + "text must be null, a string, or an object.")
        elif isinstance(text, dict) and "value" not in text:
            errors.append(prefix + "text objects must contain a 'value' field.")

        transition_out = clip.get("transition_out")
        if transition_out is not None:
            if not isinstance(transition_out, dict):
                errors.append(prefix + "transition_out must be null or an object.")
            else:
                transition_type = str(transition_out.get("type") or "").strip()
                if transition_type and transition_type not in _ALLOWED_TRANSITIONS:
                    warnings.append(prefix + f"unsupported transition type '{transition_type}'.")

        motion_effects = clip.get("motion_effects")
        if motion_effects is not None and not isinstance(motion_effects, list):
            errors.append(prefix + "motion_effects must be a list.")
        elif isinstance(motion_effects, list):
            for effect in motion_effects:
                if not isinstance(effect, dict):
                    warnings.append(prefix + "unsupported non-object motion_effect entry.")
                    break

        style_ops = clip.get("style_ops")
        if style_ops is not None and not isinstance(style_ops, list):
            errors.append(prefix + "style_ops must be a list.")
        elif isinstance(style_ops, list):
            for style_op in style_ops:
                if not isinstance(style_op, dict):
                    warnings.append(prefix + "unsupported non-object style_op entry.")
                    continue
                style_type = str(style_op.get("type") or "").strip()
                if style_type and style_type not in _ALLOWED_STYLE_OPS:
                    warnings.append(prefix + f"unsupported style op '{style_type}'.")

        if slot_id in slot_ids:
            slot = next(slot for slot in template.slots if slot.slot_id == slot_id)
            if abs(duration - float(slot.duration or 0.0)) > 0.35:
                warnings.append(
                    prefix
                    + f"duration deviates from reference slot duration ({duration:.3f}s vs {float(slot.duration or 0.0):.3f}s)."
                )

    checks["all_slots_mapped"] = len(seen_slot_ids) == len(template.slots)
    checks["known_slot_ids"] = seen_slot_ids.issubset(slot_ids)
    checks["duration_matches_reference"] = True

    reference_duration = float(template.duration or 0.0)
    if reference_duration > 0.0 and total_duration > 0.0:
        if abs(reference_duration - total_duration) > 1.5:
            checks["duration_matches_reference"] = False
            warnings.append(
                f"Compiled graph duration ({total_duration:.2f}s) differs from reference duration ({reference_duration:.2f}s)."
            )

    score = 1.0
    if errors:
        score = 0.0
    else:
        score = max(0.0, 1.0 - min(0.5, 0.05 * len(warnings)))

    return {
        "valid": not errors,
        "score": score,
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
    }
