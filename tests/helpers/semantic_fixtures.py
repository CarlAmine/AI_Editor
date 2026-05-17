from __future__ import annotations

import os
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from ai_editor.semantic_edit.edit_event_classifier import classify_semantic_edit_events
from ai_editor.semantic_edit.layer_stack import build_layer_stack
from ai_editor.semantic_edit.scene_graph import build_semantic_video_graph
from ai_editor.semantic_edit.schemas import ObjectFrameState, SemanticEditEvent, SemanticVideoGraph, TrackedObject, VideoLayer


def _write_video(path: str, frames: List[np.ndarray], fps: int) -> None:
    height, width = frames[0].shape[:2]
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), float(fps), (width, height))
    for frame in frames:
        writer.write(frame)
    writer.release()


def _draw_person(frame: np.ndarray, x: int, y: int, color: Tuple[int, int, int]) -> None:
    cv2.circle(frame, (x + 18, y + 16), 12, color, -1)
    cv2.rectangle(frame, (x + 8, y + 28), (x + 28, y + 70), color, -1)


def _draw_chair(frame: np.ndarray, x: int, y: int, color: Tuple[int, int, int]) -> None:
    cv2.rectangle(frame, (x, y + 22), (x + 44, y + 52), color, -1)
    cv2.rectangle(frame, (x + 4, y), (x + 40, y + 24), color, -1)


def _draw_table(frame: np.ndarray, x: int, y: int, color: Tuple[int, int, int]) -> None:
    cv2.rectangle(frame, (x, y), (x + 58, y + 14), color, -1)
    cv2.rectangle(frame, (x + 6, y + 14), (x + 12, y + 48), color, -1)
    cv2.rectangle(frame, (x + 46, y + 14), (x + 52, y + 48), color, -1)


def _normalized_bbox(x: int, y: int, w: int, h: int, size: Tuple[int, int]) -> List[float]:
    width, height = size
    return [x / width, y / height, w / width, h / height]


def generate_synthetic_object_video(
    out_dir: str,
    scenario: str,
    fps: int = 12,
    size: tuple[int, int] = (224, 224),
    seed: int | None = None,
) -> tuple[str, SemanticVideoGraph]:
    random.Random(seed)
    os.makedirs(out_dir, exist_ok=True)
    width, height = size
    total_frames = 24
    duration = total_frames / fps
    chair_color = (220, 80, 80)
    person_color = (80, 200, 120)
    table_color = (80, 120, 220)
    overlay_color = (20, 20, 20)
    bg_color = np.array([235, 228, 215], dtype=np.uint8)
    frames: List[np.ndarray] = []
    timestamps = [index / fps for index in range(total_frames)]
    track_states: Dict[str, List[ObjectFrameState]] = {"chair_1": [], "person_1": [], "table_1": [], "overlay_1": []}
    attrs: Dict[str, Dict] = {
        "chair_1": {"mean_color": list(chair_color), "scenario": scenario},
        "person_1": {"mean_color": list(person_color), "scenario": scenario},
        "table_1": {"mean_color": list(table_color), "scenario": scenario},
        "overlay_1": {"mean_color": list(overlay_color), "scenario": scenario},
    }

    for frame_index, timestamp in enumerate(timestamps):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:, :] = bg_color
        table_bbox = _normalized_bbox(120, 140, 58, 48, size)
        _draw_table(frame, 120, 140, table_color)
        track_states["table_1"].append(
            ObjectFrameState(timestamp=timestamp, bbox=table_bbox, confidence=1.0, visible=True, occlusion_score=0.0)
        )

        chair_visible = True
        chair_color_now = chair_color
        chair_x = 48
        chair_y = 118
        chair_occluded = False
        if scenario == "chair_disappears" and frame_index >= 12:
            chair_visible = False
        if scenario == "chair_replaced" and frame_index >= 12:
            chair_color_now = (240, 160, 40)
            attrs["chair_1"]["replaced_color"] = list(chair_color_now)
        if scenario == "chair_occluded" and 8 <= frame_index <= 14:
            chair_visible = False
            chair_occluded = True
        if chair_visible:
            _draw_chair(frame, chair_x, chair_y, chair_color_now)
        chair_bbox = _normalized_bbox(chair_x, chair_y, 44, 52, size)
        track_states["chair_1"].append(
            ObjectFrameState(
                timestamp=timestamp,
                bbox=chair_bbox,
                confidence=1.0 if chair_visible else 0.0,
                visible=chair_visible,
                occlusion_score=1.0 if chair_occluded else 0.0,
            )
        )

        person_visible = scenario in {"person_and_chair", "chair_occluded"}
        if person_visible:
            person_x = 52 if scenario == "chair_occluded" else 150
            person_y = 72
            _draw_person(frame, person_x, person_y, person_color)
            person_bbox = _normalized_bbox(person_x, person_y, 36, 70, size)
            track_states["person_1"].append(
                ObjectFrameState(timestamp=timestamp, bbox=person_bbox, confidence=1.0, visible=True, occlusion_score=0.0)
            )

        if scenario == "overlay_appears" and frame_index >= 10:
            cv2.rectangle(frame, (20, 10), (width - 20, 46), overlay_color, -1)
            overlay_bbox = _normalized_bbox(20, 10, width - 40, 36, size)
            track_states["overlay_1"].append(
                ObjectFrameState(timestamp=timestamp, bbox=overlay_bbox, confidence=1.0, visible=True, occlusion_score=0.0)
            )

        frames.append(frame)

    objects: List[TrackedObject] = []
    label_map = {"chair_1": "chair", "person_1": "person", "table_1": "table", "overlay_1": "overlay"}
    for object_id, states in track_states.items():
        visible_states = [state for state in states if state.visible]
        if not visible_states:
            continue
        objects.append(
            TrackedObject(
                object_id=object_id,
                label=label_map[object_id],
                confidence=1.0,
                first_seen=visible_states[0].timestamp,
                last_seen=visible_states[-1].timestamp,
                track=states,
                mask_available=False,
                stable_identity_score=1.0 if object_id != "chair_1" or scenario != "chair_replaced" else 0.65,
                attributes=attrs.get(object_id, {}),
            )
        )

    layers = build_layer_stack(objects)
    graph = build_semantic_video_graph(os.path.join(out_dir, "video.mp4"), frames, timestamps, [], objects, layers)
    classify_semantic_edit_events(graph)
    if scenario == "chair_replaced":
        graph.edit_events.append(
            SemanticEditEvent(
                event_type="object_replaced",
                object_id="chair_1",
                layer_id="layer_chair_1",
                start=timestamps[12],
                end=timestamps[-1],
                confidence=0.95,
                evidence={"scenario": scenario, "replacement": "chair_color_changed"},
            )
        )
        graph.edit_events.append(
            SemanticEditEvent(
                event_type="object_color_changed",
                object_id="chair_1",
                layer_id="layer_chair_1",
                start=timestamps[12],
                end=timestamps[-1],
                confidence=0.95,
                evidence={"scenario": scenario, "replacement": "chair_color_changed"},
            )
        )
    if scenario == "overlay_appears":
        graph.edit_events.append(
            SemanticEditEvent(
                event_type="overlay_appeared",
                object_id="overlay_1",
                layer_id="layer_overlay_1",
                start=timestamps[10],
                end=timestamps[10],
                confidence=0.95,
                evidence={"scenario": scenario},
            )
        )
    video_path = os.path.join(out_dir, "video.mp4")
    _write_video(video_path, frames, fps)
    graph.to_json_file(os.path.join(out_dir, "semantic_ground_truth.json"))
    return video_path, graph
