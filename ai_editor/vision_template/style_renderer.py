"""StyleRenderer: a compact U-Net that overfits on donor video frames and repaints
content video frames in the donor's visual style (color grade, tonal curves, grain,
vignette).  Training combines L1, Gram-matrix perceptual, and soft color-histogram
losses.  Inference uses temporal blending to suppress flicker.

No FFmpeg. No Shotstack. No diffusion models. Pure PyTorch + OpenCV.
"""

from __future__ import annotations

import math
import os
import random
from typing import Any, Dict, Optional

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "torch is required for StyleRenderer. Install with: pip install torch"
    ) from exc

try:
    import cv2
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "opencv-python is required for StyleRenderer. Install with: pip install opencv-python"
    ) from exc

try:
    import numpy as np
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "numpy is required for StyleRenderer. Install with: pip install numpy"
    ) from exc


# ---------------------------------------------------------------------------
# U-Net building block
# ---------------------------------------------------------------------------

def _conv_block(in_ch: int, out_ch: int) -> nn.Sequential:
    return nn.Sequential(
        nn.Conv2d(in_ch, out_ch, 3, padding=1),
        nn.BatchNorm2d(out_ch),
        nn.ReLU(inplace=True),
        nn.Conv2d(out_ch, out_ch, 3, padding=1),
        nn.BatchNorm2d(out_ch),
        nn.ReLU(inplace=True),
    )


class StyleRenderer(nn.Module):
    """3-level encoder-decoder U-Net.  Fully convolutional — works at any spatial size."""

    def __init__(self) -> None:
        super().__init__()
        # Encoder
        self.enc1 = _conv_block(3, 32)
        self.pool1 = nn.MaxPool2d(2)
        self.enc2 = _conv_block(32, 64)
        self.pool2 = nn.MaxPool2d(2)
        self.enc3 = _conv_block(64, 128)
        self.pool3 = nn.MaxPool2d(2)
        # Bottleneck
        self.bottleneck = _conv_block(128, 256)
        # Decoder
        self.up3 = nn.ConvTranspose2d(256, 128, 2, stride=2)
        self.dec3 = _conv_block(256, 128)  # 128 skip + 128 up
        self.up2 = nn.ConvTranspose2d(128, 64, 2, stride=2)
        self.dec2 = _conv_block(128, 64)   # 64 skip + 64 up
        self.up1 = nn.ConvTranspose2d(64, 32, 2, stride=2)
        self.dec1 = _conv_block(64, 32)    # 32 skip + 32 up
        # Output
        self.out_conv = nn.Sequential(
            nn.Conv2d(32, 3, 1),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        e1 = self.enc1(x)
        e2 = self.enc2(self.pool1(e1))
        e3 = self.enc3(self.pool2(e2))
        bn = self.bottleneck(self.pool3(e3))

        d3 = self.dec3(torch.cat([self.up3(bn), e3], dim=1))
        d2 = self.dec2(torch.cat([self.up2(d3), e2], dim=1))
        d1 = self.dec1(torch.cat([self.up1(d2), e1], dim=1))
        return self.out_conv(d1)


# ---------------------------------------------------------------------------
# Frozen VGG feature extractor for Gram loss
# ---------------------------------------------------------------------------

class _VGGFeatures(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        try:
            from torchvision.models import vgg11
        except ImportError as exc:
            raise RuntimeError(
                "torchvision is required for the perceptual loss. "
                "Install with: pip install torchvision"
            ) from exc
        vgg = vgg11(weights=None)
        # VGG11 features[:6]  → 128-channel output (after 2nd MaxPool)
        # VGG11 features[:11] → 256-channel output (after 3rd MaxPool)
        self.level1 = nn.Sequential(*list(vgg.features.children())[:6])
        self.level2 = nn.Sequential(*list(vgg.features.children())[:11])
        for p in self.parameters():
            p.requires_grad_(False)

    def forward(self, x: torch.Tensor):
        f1 = self.level1(x)
        f2 = self.level2(x)
        return f1, f2


def _gram_matrix(feat: torch.Tensor) -> torch.Tensor:
    """Compute normalised Gram matrix for a [B, C, H, W] feature map."""
    b, c, h, w = feat.shape
    f = feat.view(b, c, h * w)
    gram = torch.bmm(f, f.transpose(1, 2)) / (c * h * w)
    return gram  # [B, C, C]


def _soft_histogram(x: torch.Tensor, n_bins: int = 64, sigma: float = 0.02) -> torch.Tensor:
    """Differentiable soft histogram over a [1, 1, H, W] single-channel tensor."""
    pixels = x.view(-1)
    bin_centers = torch.linspace(0.0, 1.0, n_bins, device=x.device)
    diff = pixels.unsqueeze(0) - bin_centers.unsqueeze(1)  # [n_bins, N_px]
    hist = torch.exp(-diff ** 2 / (2 * sigma ** 2)).sum(dim=1)  # [n_bins]
    return hist


# ---------------------------------------------------------------------------
# Loss function
# ---------------------------------------------------------------------------

def compute_style_loss(
    output: torch.Tensor,
    target: torch.Tensor,
    vgg: "_VGGFeatures",
) -> torch.Tensor:
    """Combined L1 + Gram perceptual + soft colour-histogram loss.

    output / target: [1, 3, H, W] in [0, 1].
    """
    # 1. L1 pixel loss (weight 1.0)
    l1 = F.l1_loss(output, target)

    # 2. Gram matrix perceptual loss (weight 0.5)
    out_f1, out_f2 = vgg(output)
    tgt_f1, tgt_f2 = vgg(target)
    gram_loss = (
        F.l1_loss(_gram_matrix(out_f1), _gram_matrix(tgt_f1))
        + F.l1_loss(_gram_matrix(out_f2), _gram_matrix(tgt_f2))
    ) / 2.0

    # 3. Soft colour histogram loss (weight 0.3) — one per RGB channel
    hist_loss = torch.zeros(1, device=output.device)
    for c in range(3):
        out_hist = _soft_histogram(output[:, c : c + 1, :, :])
        tgt_hist = _soft_histogram(target[:, c : c + 1, :, :])
        hist_loss = hist_loss + F.l1_loss(out_hist, tgt_hist)
    hist_loss = hist_loss / 3.0

    return l1 * 1.0 + gram_loss * 0.5 + hist_loss * 0.3


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def _augment(frame: torch.Tensor) -> torch.Tensor:
    """Random flip + colour jitter + Gaussian noise on a [3, H, W] tensor."""
    try:
        from torchvision import transforms
    except ImportError as exc:
        raise RuntimeError(
            "torchvision is required for augmentation. "
            "Install with: pip install torchvision"
        ) from exc

    if random.random() > 0.5:
        frame = frame.flip(-1)  # horizontal flip

    jitter = transforms.ColorJitter(brightness=0.15, contrast=0.15, saturation=0.1)
    frame = jitter(frame)

    noise = torch.randn_like(frame) * 0.02
    frame = (frame + noise).clamp(0.0, 1.0)
    return frame


def train_style_renderer(
    donor_video_path: str,
    out_dir: str,
    epochs: int = 80,
    fps: float = 8.0,
    size: int = 360,
    device: str = "cpu",
    max_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    """Overfit a StyleRenderer U-Net on donor video frames.

    Returns dict: model_path, final_loss, epochs, frame_count.
    """
    from .frame_sampler import sample_video_frames

    os.makedirs(out_dir, exist_ok=True)
    dev = torch.device(device)

    print(f"[StyleRenderer] Sampling donor frames at {fps} fps, size={size}…")
    sampled = sample_video_frames(donor_video_path, fps=fps, size=size, max_seconds=max_seconds)
    frames = sampled.frames.to(dev)  # [N, 3, H, W] in [0, 1]
    n_frames = frames.shape[0]
    print(f"[StyleRenderer] {n_frames} frames sampled. Starting {epochs}-epoch training…")

    model = StyleRenderer().to(dev)
    vgg = _VGGFeatures().to(dev).eval()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

    final_loss = 0.0
    for epoch in range(1, epochs + 1):
        epoch_loss = 0.0
        model.train()
        for i in range(n_frames):
            target = frames[i].unsqueeze(0)          # [1, 3, H, W]
            augmented = _augment(frames[i]).unsqueeze(0)

            output = model(augmented)
            loss = compute_style_loss(output, target, vgg)
            loss.backward()                          # accumulate; DO NOT step here
            epoch_loss += loss.item()

        # Step once per epoch after all frames
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        optimizer.zero_grad()

        final_loss = epoch_loss / max(1, n_frames)
        if epoch % 10 == 0 or epoch == epochs:
            print(f"[StyleRenderer] Epoch {epoch}/{epochs} loss={final_loss:.4f}")

    model_path = os.path.join(out_dir, "style_renderer.pt")
    torch.save({"state_dict": model.state_dict()}, model_path)
    print(f"[StyleRenderer] Model saved → {model_path}")

    return {
        "model_path": model_path,
        "final_loss": final_loss,
        "epochs": epochs,
        "frame_count": n_frames,
    }


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------

def render_video_with_style(
    content_video_path: str,
    style_renderer_path: str,
    out_path: str,
    processing_size: int = 360,
    device: str = "cpu",
) -> Dict[str, Any]:
    """Apply learned style to every frame of the content video.

    Processes at processing_size for speed; outputs at original resolution.
    Applies temporal blending (alpha=0.75 current / 0.25 previous) to suppress flicker.
    Uses OpenCV VideoWriter — no FFmpeg.

    Returns dict: out_path, frame_count, width, height.
    """
    dev = torch.device(device)

    checkpoint = torch.load(style_renderer_path, map_location=dev)
    model = StyleRenderer().to(dev)
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()

    cap = cv2.VideoCapture(content_video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open content video: {content_video_path}")

    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    orig_fps = float(cap.get(cv2.CAP_PROP_FPS)) or 30.0

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(out_path, fourcc, orig_fps, (orig_w, orig_h))

    prev_frame: Optional[np.ndarray] = None
    frame_count = 0

    with torch.no_grad():
        while True:
            ok, bgr = cap.read()
            if not ok:
                break

            # Resize to processing size for inference
            rgb_small = cv2.cvtColor(
                cv2.resize(bgr, (processing_size, processing_size), interpolation=cv2.INTER_AREA),
                cv2.COLOR_BGR2RGB,
            )
            tensor = torch.from_numpy(rgb_small).permute(2, 0, 1).float().div(255.0).unsqueeze(0).to(dev)

            output = model(tensor)  # [1, 3, H, W]
            out_np = output[0].permute(1, 2, 0).cpu().numpy()
            out_uint8 = (out_np * 255.0).clip(0, 255).astype(np.uint8)  # [H, W, 3] RGB

            # Resize output back to original resolution
            out_orig = cv2.resize(out_uint8, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)

            # Temporal blending — anti-flicker
            if prev_frame is not None:
                blended = (
                    0.75 * out_orig.astype(np.float32)
                    + 0.25 * prev_frame.astype(np.float32)
                ).clip(0, 255).astype(np.uint8)
            else:
                blended = out_orig

            prev_frame = blended

            # Write in BGR (OpenCV convention)
            bgr_out = cv2.cvtColor(blended, cv2.COLOR_RGB2BGR)
            writer.write(bgr_out)
            frame_count += 1

    cap.release()
    writer.release()
    print(f"[StyleRenderer] Rendered {frame_count} frames → {out_path}")

    return {
        "out_path": out_path,
        "frame_count": frame_count,
        "width": orig_w,
        "height": orig_h,
    }
