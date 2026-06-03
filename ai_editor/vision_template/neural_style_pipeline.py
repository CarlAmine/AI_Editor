"""Top-level orchestrator for the two-track neural style transfer pipeline.

Track 1 — StyleRenderer: trains a compact U-Net on the donor video and rerenders
           the content video in the donor's visual style.
Track 2 — OverlayReplicator: detects graphic overlays in the donor and composites
           them onto the Track-1 output at matching temporal positions.

The final video is written entirely by OpenCV VideoWriter.
No FFmpeg. No Shotstack. No diffusion models.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional


def run_neural_style_transfer(
    donor_video_path: str,
    content_video_path: str,
    out_dir: str,
    epochs: int = 80,
    fps_train: float = 8.0,
    processing_size: int = 360,
    device: str = "cpu",
    max_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    """Run the full two-track neural style transfer pipeline.

    Track 1: trains StyleRenderer on donor frames, then rerenders content video.
    Track 2: detects donor overlays, composites them onto Track-1 output.

    Returns dict with keys:
      styled_video_path      — Track 1 output (style only)
      composited_video_path  — Track 2 output (style + overlays)
      model_path             — saved U-Net weights
      training               — training metadata dict
      overlays               — overlay replication metadata dict
      final_output_path      — same as composited_video_path
    """
    from .style_renderer import train_style_renderer, render_video_with_style
    from .overlay_replicator import replicate_overlays

    os.makedirs(out_dir, exist_ok=True)
    styled_path = os.path.join(out_dir, "styled_frames.mp4")
    composited_path = os.path.join(out_dir, "final_stylized.mp4")

    # ── Track 1a: train U-Net on donor ─────────────────────────────────────
    print("[NeuralStylePipeline] Step 1/3: Training style renderer on donor video…")
    training_result = train_style_renderer(
        donor_video_path=donor_video_path,
        out_dir=out_dir,
        epochs=epochs,
        fps=fps_train,
        size=processing_size,
        device=device,
        max_seconds=max_seconds,
    )

    # ── Track 1b: render content video with learned style ──────────────────
    print("[NeuralStylePipeline] Step 2/3: Rendering content video with learned style…")
    render_result = render_video_with_style(
        content_video_path=content_video_path,
        style_renderer_path=training_result["model_path"],
        out_path=styled_path,
        processing_size=processing_size,
        device=device,
    )

    # ── Track 2: replicate overlays from donor onto styled output ──────────
    print("[NeuralStylePipeline] Step 3/3: Replicating overlays from donor…")
    overlay_result = replicate_overlays(
        content_video_path=styled_path,
        donor_video_path=donor_video_path,
        out_path=composited_path,
    )

    print(f"[NeuralStylePipeline] Done. Final output → {composited_path}")

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
    }
