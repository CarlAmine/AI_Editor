from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Tuple

from .object_detector import Detection
from .schemas import ObjectFrameState, TrackedObject


def _iou(box_a: List[float], box_b: List[float]) -> float:
    ax1, ay1, aw, ah = box_a
    bx1, by1, bw, bh = box_b
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def track_objects(
    detections,
    timestamps,
    iou_threshold: float = 0.3,
    max_missing_frames: int = 8,
) -> list[TrackedObject]:
    by_frame: Dict[int, List[Detection]] = defaultdict(list)
    for detection in detections:
        by_frame[int(detection.frame_index)].append(detection)

    active: Dict[str, Dict] = {}
    finished: List[Dict] = []
    counters: Dict[str, int] = defaultdict(int)
    all_frames = range(len(timestamps))

    for frame_index in all_frames:
        frame_detections = by_frame.get(frame_index, [])
        used_tracks = set()
        used_detections = set()
        pairs: List[Tuple[float, str, int]] = []

        for track_id, payload in active.items():
            if frame_index - payload["last_frame"] > max_missing_frames:
                finished.append(payload)
                continue
            for det_index, detection in enumerate(frame_detections):
                if detection.label != payload["label"]:
                    continue
                score = _iou(payload["last_bbox"], detection.bbox)
                if score >= iou_threshold:
                    pairs.append((score, track_id, det_index))

        for score, track_id, det_index in sorted(pairs, key=lambda item: item[0], reverse=True):
            if track_id in used_tracks or det_index in used_detections or track_id not in active:
                continue
            detection = frame_detections[det_index]
            payload = active[track_id]
            payload["track"].append(
                ObjectFrameState(
                    timestamp=float(detection.timestamp),
                    bbox=list(detection.bbox),
                    confidence=float(detection.confidence),
                    visible=True,
                    occlusion_score=0.0,
                    mask_path=None,
                )
            )
            payload["last_frame"] = frame_index
            payload["last_bbox"] = list(detection.bbox)
            payload["scores"].append(score)
            payload["confidences"].append(float(detection.confidence))
            payload["attributes"].update(detection.attributes or {})
            payload["color_history"].append(list((detection.attributes or {}).get("mean_color", [])))
            used_tracks.add(track_id)
            used_detections.add(det_index)

        for det_index, detection in enumerate(frame_detections):
            if det_index in used_detections:
                continue
            counters[detection.label] += 1
            object_id = f"{detection.label}_{counters[detection.label]}"
            active[object_id] = {
                "object_id": object_id,
                "label": detection.label,
                "track": [
                    ObjectFrameState(
                        timestamp=float(detection.timestamp),
                        bbox=list(detection.bbox),
                        confidence=float(detection.confidence),
                        visible=True,
                        occlusion_score=0.0,
                        mask_path=None,
                    )
                ],
                "first_seen": float(detection.timestamp),
                "last_seen": float(detection.timestamp),
                "last_frame": frame_index,
                "last_bbox": list(detection.bbox),
                "scores": [1.0],
                "confidences": [float(detection.confidence)],
                "attributes": dict(detection.attributes or {}),
                "color_history": [list((detection.attributes or {}).get("mean_color", []))],
            }

        stale_ids = []
        for track_id, payload in active.items():
            if frame_index == payload["last_frame"]:
                payload["last_seen"] = float(timestamps[frame_index])
                continue
            if frame_index - payload["last_frame"] <= max_missing_frames:
                payload["track"].append(
                    ObjectFrameState(
                        timestamp=float(timestamps[frame_index]),
                        bbox=list(payload["last_bbox"]),
                        confidence=0.0,
                        visible=False,
                        occlusion_score=1.0,
                        mask_path=None,
                    )
                )
            else:
                stale_ids.append(track_id)
        for track_id in stale_ids:
            finished.append(active.pop(track_id))

    finished.extend(active.values())
    tracked: List[TrackedObject] = []
    for payload in finished:
        track = payload["track"]
        first_visible = next((state.timestamp for state in track if state.visible), payload["first_seen"])
        last_visible = next((state.timestamp for state in reversed(track) if state.visible), payload["last_seen"])
        tracked.append(
            TrackedObject(
                object_id=payload["object_id"],
                label=payload["label"],
                confidence=sum(payload["confidences"]) / max(len(payload["confidences"]), 1),
                first_seen=float(first_visible),
                last_seen=float(last_visible),
                track=track,
                mask_available=False,
                stable_identity_score=sum(payload["scores"]) / max(len(payload["scores"]), 1),
                attributes={**payload["attributes"], "color_history": payload.get("color_history", [])},
            )
        )
    tracked.sort(key=lambda item: (item.first_seen, item.object_id))
    return tracked
