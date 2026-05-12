from __future__ import annotations

from typing import List, Optional

from .schemas import SemanticEditVerification, SemanticVideoGraph


def _parse_target_label(user_instruction: str) -> Optional[str]:
    lowered = str(user_instruction or "").lower()
    for label in ("chair", "person", "table", "product", "phone", "car", "overlay"):
        if label in lowered:
            return label
    return None


def verify_object_edit(
    before_graph: SemanticVideoGraph,
    after_graph: SemanticVideoGraph,
    user_instruction: str,
    target_object_label: str | None = None,
) -> SemanticEditVerification:
    target_label = target_object_label or _parse_target_label(user_instruction)
    warnings: List[str] = []
    changed_objects: List[str] = []
    preserved_objects: List[str] = []
    unintended_changes: List[str] = []

    before_by_label = {}
    for obj in before_graph.objects:
        before_by_label.setdefault(obj.label, []).append(obj)
    after_by_label = {}
    for obj in after_graph.objects:
        after_by_label.setdefault(obj.label, []).append(obj)

    target_ids = [obj.object_id for obj in before_by_label.get(target_label, [])] if target_label else []
    target_changed = False
    for event in after_graph.edit_events:
        if target_label and event.object_id and any(obj.object_id == event.object_id for obj in after_by_label.get(target_label, [])):
            if event.event_type in {"object_replaced", "object_removed", "object_disappeared", "object_color_changed"}:
                changed_objects.append(event.object_id)
                target_changed = True

    for label, before_objs in before_by_label.items():
        if label == target_label:
            continue
        after_objs = after_by_label.get(label, [])
        if not after_objs:
            unintended_changes.extend([obj.object_id for obj in before_objs])
            continue
        before_box = next((state.bbox for state in before_objs[0].track if state.visible), None)
        after_box = next((state.bbox for state in after_objs[0].track if state.visible), None)
        if before_box == after_box:
            preserved_objects.append(before_objs[0].object_id)
        else:
            unintended_changes.append(before_objs[0].object_id)

    score = 0.5
    if target_label:
        if target_changed:
            score += 0.3
        else:
            score -= 0.2
            warnings.append(f"Target label '{target_label}' did not show a clear semantic change.")
    if preserved_objects:
        score += 0.2
    if unintended_changes:
        score -= 0.35
    score = max(0.0, min(1.0, score))
    return SemanticEditVerification(
        passed=score >= 0.6 and (not target_label or target_changed),
        score=score,
        target_object_label=target_label,
        target_object_ids=target_ids,
        changed_objects=sorted(set(changed_objects)),
        preserved_objects=sorted(set(preserved_objects)),
        unintended_changes=sorted(set(unintended_changes)),
        evidence={
            "before_object_labels": sorted(before_by_label.keys()),
            "after_object_labels": sorted(after_by_label.keys()),
            "event_types": [event.event_type for event in after_graph.edit_events],
        },
        warnings=warnings,
    )
