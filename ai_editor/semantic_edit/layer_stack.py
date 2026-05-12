from __future__ import annotations

from typing import List

from .object_detector import Detection
from .schemas import TrackedObject, VideoLayer


def build_layer_stack(
    graph_or_tracks,
    overlay_detections=None,
) -> list[VideoLayer]:
    tracks = graph_or_tracks.objects if hasattr(graph_or_tracks, "objects") else list(graph_or_tracks or [])
    duration = getattr(graph_or_tracks, "duration", None)
    if duration is None:
        duration = max((track.last_seen for track in tracks), default=0.0)
    layers: List[VideoLayer] = [
        VideoLayer(
            layer_id="background_1",
            layer_type="background",
            label="background",
            object_id=None,
            start=0.0,
            end=float(duration),
            region="full",
            editable=False,
            confidence=1.0,
            metadata={},
        )
    ]
    for track in tracks:
        layer_type = "overlay" if track.label == "overlay" else "foreground_subject" if track.label == "person" else "object"
        layers.append(
            VideoLayer(
                layer_id=f"layer_{track.object_id}",
                layer_type=layer_type,
                label=track.label,
                object_id=track.object_id,
                start=track.first_seen,
                end=track.last_seen,
                region="full" if track.label == "overlay" else None,
                editable=track.label != "background",
                confidence=min(1.0, max(track.confidence, track.stable_identity_score)),
                metadata={"stable_identity_score": track.stable_identity_score},
            )
        )
    return layers
