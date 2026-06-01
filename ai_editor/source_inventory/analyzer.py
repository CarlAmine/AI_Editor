from __future__ import annotations
import os
from typing import Any, Dict, List, Optional
from ai_editor.edit_contracts.source_inventory import SourceClipInventory, SourceInventory

def build_source_inventory(
    source_artifacts: List[Dict[str, Any]],
    job_id: str,
    out_dir: str,
    lightweight: bool = True,
) -> Dict[str, Any]:
    clips: List[SourceClipInventory] = []
    warnings: List[str] = []

    for art in source_artifacts:
        clip_id = str(art.get("clip_id", ""))
        source_index = int(art.get("source_index", 0))
        path = str(art.get("path", ""))

        if not path or not os.path.exists(path):
            warnings.append(f"Source clip path for {clip_id} does not exist: {path}")
            continue

        # Probe video using OpenCV
        fps = None
        width = None
        height = None
        duration = 0.0

        try:
            import cv2
            cap = cv2.VideoCapture(path)
            if cap.isOpened():
                fps_val = cap.get(cv2.CAP_PROP_FPS)
                if fps_val > 0:
                    fps = float(fps_val)
                frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                w_val = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                h_val = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                if w_val > 0:
                    width = int(w_val)
                if h_val > 0:
                    height = int(h_val)
                if fps and frame_count > 0:
                    duration = float(frame_count / fps)
                cap.release()
        except Exception as exc:
            warnings.append(f"Failed to probe metadata for {clip_id}: {exc}")

        # Fallback duration if cv2 failed
        if duration <= 0.0:
            try:
                # If there's an existing probe method or we can fallback
                from ai_editor.downloader import _probe_duration_any
                duration = float(_probe_duration_any(path) or 0.0)
            except Exception:
                pass

        candidate_segments: List[Dict[str, Any]] = []
        if duration <= 0.0:
            warnings.append(f"Clip {clip_id} has zero or unknown duration. Skipping candidates.")
        elif duration <= 3.0:
            candidate_segments.append({
                "start": 0.0,
                "end": duration,
                "duration": duration,
                "quality_score": 0.8,
                "motion_score": 0.5,
                "subject_position": "unknown",
                "selection_reason": "entire_short_clip",
            })
        else:
            # Create 3 segments: beginning, middle, ending
            seg_len = duration / 3.0
            candidate_segments.append({
                "start": 0.0,
                "end": seg_len,
                "duration": seg_len,
                "quality_score": 0.85,
                "motion_score": 0.6,
                "subject_position": "unknown",
                "selection_reason": "beginning_segment",
            })
            candidate_segments.append({
                "start": seg_len,
                "end": seg_len * 2.0,
                "duration": seg_len,
                "quality_score": 0.9,
                "motion_score": 0.7,
                "subject_position": "unknown",
                "selection_reason": "middle_segment",
            })
            candidate_segments.append({
                "start": seg_len * 2.0,
                "end": duration,
                "duration": duration - (seg_len * 2.0),
                "quality_score": 0.8,
                "motion_score": 0.5,
                "subject_position": "unknown",
                "selection_reason": "ending_segment",
            })

        clip_inv = SourceClipInventory(
            clip_id=clip_id,
            source_index=source_index,
            path=path,
            duration=duration,
            fps=fps,
            width=width,
            height=height,
            candidate_segments=candidate_segments,
            metadata={"probed": True, "job_id": job_id},
        )
        clips.append(clip_inv)

    inventory = SourceInventory(clips=clips, warnings=warnings)
    return inventory.to_dict()
