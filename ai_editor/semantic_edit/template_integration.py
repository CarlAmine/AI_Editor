from __future__ import annotations

from collections import Counter

from ai_editor.vision_template.schemas import EditTemplate

from .schemas import SemanticVideoGraph


def attach_semantic_graph_to_template(
    template: EditTemplate,
    graph: SemanticVideoGraph,
) -> EditTemplate:
    for slot in template.slots:
        visible_objects = []
        visible_labels = []
        visible_layers = []
        semantic_events = []
        for obj in graph.objects:
            if obj.last_seen < slot.start or obj.first_seen > slot.end:
                continue
            visible_objects.append(obj.object_id)
            visible_labels.append(obj.label)
        for layer in graph.layers:
            if layer.end < slot.start or layer.start > slot.end:
                continue
            visible_layers.append(layer.layer_id)
        for event in graph.edit_events:
            if event.end < slot.start or event.start > slot.end:
                continue
            semantic_events.append(event.model_dump() if hasattr(event, "model_dump") else event.dict())
        slot.visible_objects = sorted(set(visible_objects))
        slot.visible_layers = sorted(set(visible_layers))
        slot.semantic_events = semantic_events
        slot.semantic_metadata = {
            "dominant_object_labels": [label for label, _count in Counter(visible_labels).most_common(3)],
            "overlay_layers": [layer_id for layer_id in slot.visible_layers if "overlay" in layer_id],
            "object_constraints": {"preserve_non_target": True},
        }
    return template
