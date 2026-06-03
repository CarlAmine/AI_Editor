"""Top-level orchestrator for the two-track neural style transfer pipeline.

Track 1 — StyleRenderer: trains a compact U-Net on the donor video and rerenders
           each content clip in the donor's visual style, trimmed to its scene duration.
Track 2 — OverlayReplicator: detects graphic overlays in the donor and composites
           them onto the concatenated Track-1 output at matching temporal positions.

The final video is written entirely by OpenCV VideoWriter.
No FFmpeg. No Shotstack. No diffusion models.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional


def run_neural_style_transfer(
    donor_video_path: str,
    content_video_paths: List[str],
    scene_durations: List[float],
    out_dir: str,
    epochs: int = 80,
    fps_train: float = 8.0,
    processing_size: int = 360,
    device: str = "cpu",
    max_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    """Run the full two-track neural style transfer pipeline over multiple content clips.

    Each content clip is trimmed to its corresponding scene_duration via max_frames.
    All styled clips are concatenated into one file before overlay compositing.

    Returns dict with keys:
      styled_video_path      — concatenated Track 1 output (style only)
      composited_video_path  — Track 2 output (style + overlays)
      model_path             — saved U-Net weights
      training               — training metadata dict
      overlays               — overlay replication metadata dict
      final_output_path      — same as composited_video_path
      clip_count             — number of content clips processed
    """
    from .style_renderer import train_style_renderer, render_video_with_style
    from .overlay_replicator import replicate_overlays

    # ── 1. Validate inputs ─────────────────────────────────────────────────
    if len(content_video_paths) != len(scene_durations):
        raise ValueError(
            f"content_video_paths and scene_durations must have the same length; "
            f"got {len(content_video_paths)} paths and {len(scene_durations)} durations."
        )
    for path in content_video_paths:
        if not os.path.exists(path):
            raise RuntimeError(f"Content video not found: {path}")

    # ── 2. Prepare output directory ────────────────────────────────────────
    os.makedirs(out_dir, exist_ok=True)

    # ── 3. Train style renderer on donor ───────────────────────────────────
    print("[NeuralStylePipeline] Step 1/3: Training style renderer on donor video...")
    training_result = train_style_renderer(
        donor_video_path=donor_video_path,
        out_dir=out_dir,
        epochs=epochs,
        fps=fps_train,
        size=processing_size,
        device=device,
        max_seconds=max_seconds,
    )

    # ── 4-5. Render each content clip with learned style ───────────────────
    print(
        f"[NeuralStylePipeline] Step 2/3: Rendering {len(content_video_paths)} "
        "content clip(s) with learned style..."
    )
    styled_clip_paths: List[str] = []

    for index, (content_path, scene_duration) in enumerate(
        zip(content_video_paths, scene_durations), start=1
    ):
        # Compute max_frames for this clip
        try:
            import cv2 as _cv2
            _cap = _cv2.VideoCapture(content_path)
            clip_fps = float(_cap.get(_cv2.CAP_PROP_FPS))
            _cap.release()
        except Exception:
            clip_fps = 0.0

        if clip_fps > 0 and scene_duration > 0:
            max_frames = int(round(scene_duration * clip_fps))
        else:
            max_frames = None

        styled_clip_path = os.path.join(out_dir, f"styled_clip_{index:03d}.mp4")
        render_video_with_style(
            content_video_path=content_path,
            style_renderer_path=training_result["model_path"],
            out_path=styled_clip_path,
            processing_size=processing_size,
            device=device,
            max_frames=max_frames,
        )
        styled_clip_paths.append(styled_clip_path)

    # ── 6. Concatenate styled clips with OpenCV ────────────────────────────
    print(
        f"[NeuralStylePipeline] Step 2b/3: Concatenating {len(styled_clip_paths)} styled clips..."
    )
    styled_frames_path = os.path.join(out_dir, "styled_frames.mp4")

    import cv2

    # Read properties from the first clip
    _first_cap = cv2.VideoCapture(styled_clip_paths[0])
    concat_w = int(_first_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    concat_h = int(_first_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    concat_fps = float(_first_cap.get(cv2.CAP_PROP_FPS)) or 30.0
    _first_cap.release()

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    concat_writer = cv2.VideoWriter(styled_frames_path, fourcc, concat_fps, (concat_w, concat_h))
    total_concat_frames = 0

    for clip_path in styled_clip_paths:
        clip_cap = cv2.VideoCapture(clip_path)
        while True:
            ok, frame = clip_cap.read()
            if not ok:
                break
            concat_writer.write(frame)
            total_concat_frames += 1
        clip_cap.release()

    concat_writer.release()

    # ── 7-8. Composite donor overlays onto concatenated output ─────────────
    styled_path = styled_frames_path
    composited_path = os.path.join(out_dir, "final_stylized.mp4")

    print("[NeuralStylePipeline] Step 3/3: Replicating overlays from donor...")
    overlay_result = replicate_overlays(
        content_video_path=styled_path,
        donor_video_path=donor_video_path,
        out_path=composited_path,
    )

    # ── 9. Done ────────────────────────────────────────────────────────────
    print(f"[NeuralStylePipeline] Done. Final output -> {composited_path}")

    return {
        "styled_video_path": styled_path,
        "composited_video_path": composited_path,
        "model_path": training_result["model_path"],
        "training": training_result,
        "overlays": {
            "overlay_count": overlay_result["overlay_count"],
            "frame_count": overlay_result["frame_count"],
        },
        "final_output_path": composited_path,
        "clip_count": len(content_video_paths),
    }
