from __future__ import annotations

from typing import Dict, List, Tuple

from .schemas import ActionEvent, SemanticVideoGraph


def _center(box):
    return box[0] + box[2] / 2.0, box[1] + box[3] / 2.0


def _relation(box_a, box_b) -> List[str]:
    ax, ay = _center(box_a)
    bx, by = _center(box_b)
    relations: List[str] = []
    if ax < bx:
        relations.append("left_of")
    if ax > bx:
        relations.append("right_of")
    if ay < by:
        relations.append("above")
    if ay > by:
        relations.append("below")
    overlap_x = min(box_a[0] + box_a[2], box_b[0] + box_b[2]) - max(box_a[0], box_b[0])
    overlap_y = min(box_a[1] + box_a[3], box_b[1] + box_b[3]) - max(box_a[1], box_b[1])
    if overlap_x > 0 and overlap_y > 0:
        relations.append("overlapping")
    if abs(ax - bx) < 0.15 and abs(ay - by) < 0.15:
        relations.append("near")
    return relations


def build_semantic_video_graph(
    video_path: str,
    frames,
    timestamps,
    detections,
    tracks,
    layers,
) -> SemanticVideoGraph:
    actions: List[ActionEvent] = []
    for index, left in enumerate(tracks):
        left_visible = next((state for state in left.track if state.visible), None)
        if left_visible is None:
            continue
        left_relations = []
        for right in tracks[index + 1 :]:
            right_visible = next((state for state in right.track if state.visible), None)
            if right_visible is None:
                continue
            relations = _relation(left_visible.bbox, right_visible.bbox)
            if relations:
                left_relations.append({"other": right.object_id, "relations": relations})
                if left.label == "person" and right.label == "chair" and "overlapping" in relations:
                    actions.append(
                        ActionEvent(
                            subject_id=left.object_id,
                            verb="sitting_or_overlapping",
                            object_id=right.object_id,
                            start=max(left.first_seen, right.first_seen),
                            end=min(left.last_seen, right.last_seen),
                            confidence=0.7,
                        )
                    )
        left.attributes.setdefault("relations", left_relations)

    duration = float(timestamps[-1]) if timestamps else 0.0
    return SemanticVideoGraph(
        video_path=video_path,
        sampled_fps=(len(timestamps) / duration if duration > 0 else 0.0),
        duration=duration,
        objects=list(tracks),
        layers=list(layers),
        actions=actions,
        edit_events=[],
        warnings=[],
    )
