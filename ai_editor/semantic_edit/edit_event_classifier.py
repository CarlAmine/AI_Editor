from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from .schemas import SemanticEditEvent, SemanticVideoGraph


def classify_semantic_edit_events(
    graph: SemanticVideoGraph,
) -> list[SemanticEditEvent]:
    events: List[SemanticEditEvent] = []
    by_label: Dict[str, List] = defaultdict(list)
    for obj in graph.objects:
        by_label[obj.label].append(obj)
        visible_states = [state for state in obj.track if state.visible]
        hidden_states = [state for state in obj.track if not state.visible]
        if visible_states and visible_states[0].timestamp > 0.05:
            events.append(
                SemanticEditEvent(
                    event_type="object_appeared" if obj.label != "overlay" else "overlay_appeared",
                    object_id=obj.object_id,
                    layer_id=f"layer_{obj.object_id}",
                    start=obj.first_seen,
                    end=obj.first_seen,
                    confidence=obj.confidence,
                    evidence={"first_seen": obj.first_seen},
                )
            )
        if hidden_states:
            last_visible = visible_states[-1] if visible_states else None
            if last_visible and last_visible.timestamp < graph.duration - 0.1:
                if any(state.visible for state in obj.track[obj.track.index(last_visible) + 1 :]):
                    continue
                occluded = any(hidden.occlusion_score > 0.5 for hidden in hidden_states)
                events.append(
                    SemanticEditEvent(
                        event_type="object_disappeared" if occluded else "object_removed",
                        object_id=obj.object_id,
                        layer_id=f"layer_{obj.object_id}",
                        start=last_visible.timestamp,
                        end=obj.last_seen,
                        confidence=0.75,
                        evidence={"last_visible": last_visible.timestamp, "occluded": occluded},
                    )
                )
        visible_boxes = [state.bbox for state in visible_states]
        if len(visible_boxes) >= 2:
            first_box = visible_boxes[0]
            last_box = visible_boxes[-1]
            if abs(first_box[0] - last_box[0]) > 0.12 or abs(first_box[1] - last_box[1]) > 0.12:
                events.append(
                    SemanticEditEvent(
                        event_type="object_position_changed",
                        object_id=obj.object_id,
                        layer_id=f"layer_{obj.object_id}",
                        start=obj.first_seen,
                        end=obj.last_seen,
                        confidence=0.7,
                        evidence={"from": first_box, "to": last_box},
                    )
                )
            first_area = first_box[2] * first_box[3]
            last_area = last_box[2] * last_box[3]
            if abs(first_area - last_area) > 0.06:
                events.append(
                    SemanticEditEvent(
                        event_type="object_scale_changed",
                        object_id=obj.object_id,
                        layer_id=f"layer_{obj.object_id}",
                        start=obj.first_seen,
                        end=obj.last_seen,
                        confidence=0.7,
                        evidence={"from_area": first_area, "to_area": last_area},
                    )
                )

    for label, objects in by_label.items():
        if len(objects) >= 2 and label != "overlay":
            sorted_objects = sorted(objects, key=lambda item: item.first_seen)
            first, second = sorted_objects[0], sorted_objects[1]
            if second.first_seen >= first.last_seen - 0.2:
                color_a = tuple(first.attributes.get("mean_color", []))
                color_b = tuple(second.attributes.get("mean_color", []))
                if color_a and color_b and color_a != color_b:
                    events.append(
                        SemanticEditEvent(
                            event_type="object_replaced",
                            object_id=second.object_id,
                            layer_id=f"layer_{second.object_id}",
                            start=second.first_seen,
                            end=second.first_seen,
                            confidence=0.8,
                            evidence={"replaces": first.object_id, "label": label},
                        )
                    )

    for obj in graph.objects:
        color_history = [tuple(color) for color in obj.attributes.get("color_history", []) if color]
        if len(set(color_history)) >= 2:
            events.append(
                SemanticEditEvent(
                    event_type="object_replaced",
                    object_id=obj.object_id,
                    layer_id=f"layer_{obj.object_id}",
                    start=obj.first_seen,
                    end=obj.last_seen,
                    confidence=0.82,
                    evidence={"color_history": [list(color) for color in list(dict.fromkeys(color_history))]},
                )
            )
            events.append(
                SemanticEditEvent(
                    event_type="object_color_changed",
                    object_id=obj.object_id,
                    layer_id=f"layer_{obj.object_id}",
                    start=obj.first_seen,
                    end=obj.last_seen,
                    confidence=0.78,
                    evidence={"color_history": [list(color) for color in list(dict.fromkeys(color_history))]},
                )
            )

    for layer in graph.layers:
        if layer.layer_type == "overlay" and layer.start > 0.05:
            events.append(
                SemanticEditEvent(
                    event_type="overlay_appeared",
                    object_id=layer.object_id,
                    layer_id=layer.layer_id,
                    start=layer.start,
                    end=layer.start,
                    confidence=layer.confidence,
                    evidence={"layer": layer.layer_id},
                )
            )
    graph.edit_events = events
    return events
