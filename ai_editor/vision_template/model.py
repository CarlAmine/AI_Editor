from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import torch
from torch import nn

MOTION_LABELS = [
    "static",
    "zoom_in",
    "zoom_out",
    "pan_left",
    "pan_right",
    "pan_up",
    "pan_down",
    "unknown",
]
TRANSITION_LABELS = ["cut", "fade", "wipe", "none"]
OVERLAY_LABELS = ["none", "top", "center", "lower_third", "full", "unknown"]


@dataclass
class VisionEditOutput:
    boundary_logits: torch.Tensor
    motion_logits: torch.Tensor
    transition_logits: torch.Tensor
    overlay_logits: torch.Tensor
    crop_params: torch.Tensor
    style_embedding: torch.Tensor
    frame_embeddings: torch.Tensor
    temporal_features: torch.Tensor


class TinyVisionEditModel(nn.Module):
    def __init__(self, hidden_size: int = 72, style_dim: int = 16) -> None:
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Conv2d(3, 16, kernel_size=5, stride=2, padding=2),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(16, 32, kernel_size=3, stride=1, padding=1),
            nn.ReLU(),
            nn.Conv2d(32, 48, kernel_size=3, stride=1, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d((1, 1)),
        )
        self.delta_projection = nn.Sequential(nn.Linear(1, 8), nn.ReLU(), nn.Linear(8, 8), nn.ReLU())
        self.temporal_prep = nn.Sequential(
            nn.Conv1d(56, 64, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(64, 64, kernel_size=3, padding=1),
            nn.ReLU(),
        )
        self.temporal = nn.GRU(input_size=64, hidden_size=hidden_size, batch_first=True, bidirectional=True)
        temporal_dim = hidden_size * 2
        self.boundary_pair = nn.Sequential(
            nn.Linear(temporal_dim * 2 + 1, temporal_dim),
            nn.ReLU(),
            nn.Linear(temporal_dim, 1),
        )
        self.motion_head = nn.Linear(temporal_dim, len(MOTION_LABELS))
        self.transition_head = nn.Linear(temporal_dim, len(TRANSITION_LABELS))
        self.overlay_head = nn.Linear(temporal_dim, len(OVERLAY_LABELS))
        self.crop_head = nn.Sequential(nn.Linear(temporal_dim, 32), nn.ReLU(), nn.Linear(32, 4), nn.Sigmoid())
        self.style_head = nn.Sequential(nn.Linear(temporal_dim, 32), nn.ReLU(), nn.Linear(32, style_dim))

    def forward(self, frames: torch.Tensor) -> VisionEditOutput:
        squeezed = False
        if frames.dim() == 4:
            frames = frames.unsqueeze(0)
            squeezed = True
        if frames.dim() != 5:
            raise ValueError(f"Expected frames with shape [T,C,H,W] or [B,T,C,H,W], got {tuple(frames.shape)}")

        batch, steps, channels, height, width = frames.shape
        encoded = self.encoder(frames.reshape(batch * steps, channels, height, width)).flatten(1)
        frame_embeddings = encoded.reshape(batch, steps, -1)

        if steps > 1:
            frame_delta = torch.abs(frames[:, 1:] - frames[:, :-1]).mean(dim=(2, 3, 4), keepdim=False).unsqueeze(-1)
            frame_delta = torch.cat([torch.zeros((batch, 1, 1), device=frames.device, dtype=frames.dtype), frame_delta], dim=1)
        else:
            frame_delta = torch.zeros((batch, steps, 1), device=frames.device, dtype=frames.dtype)
        delta_features = self.delta_projection(frame_delta)

        sequence = torch.cat([frame_embeddings, delta_features], dim=-1)
        prepped = self.temporal_prep(sequence.transpose(1, 2)).transpose(1, 2)
        temporal_features, _ = self.temporal(prepped)
        pooled = temporal_features.mean(dim=1)

        if steps > 1:
            prev_features = torch.cat([temporal_features[:, :1], temporal_features[:, :-1]], dim=1)
            pair_delta = torch.norm(frame_embeddings - torch.cat([frame_embeddings[:, :1], frame_embeddings[:, :-1]], dim=1), dim=-1, keepdim=True)
        else:
            prev_features = temporal_features
            pair_delta = torch.zeros((batch, steps, 1), device=frames.device, dtype=temporal_features.dtype)
        boundary_features = torch.cat([prev_features, temporal_features, pair_delta], dim=-1)
        boundary = self.boundary_pair(boundary_features).squeeze(-1)
        motion = self.motion_head(temporal_features)
        transition = self.transition_head(temporal_features)
        overlay = self.overlay_head(temporal_features)
        crop = self.crop_head(temporal_features)
        style = self.style_head(pooled)

        if squeezed:
            boundary = boundary.squeeze(0)
            motion = motion.squeeze(0)
            transition = transition.squeeze(0)
            overlay = overlay.squeeze(0)
            crop = crop.squeeze(0)
            style = style.squeeze(0)
            frame_embeddings = frame_embeddings.squeeze(0)
            temporal_features = temporal_features.squeeze(0)

        return VisionEditOutput(
            boundary_logits=boundary,
            motion_logits=motion,
            transition_logits=transition,
            overlay_logits=overlay,
            crop_params=crop,
            style_embedding=style,
            frame_embeddings=frame_embeddings,
            temporal_features=temporal_features,
        )


class PretrainedVideoEditModel(nn.Module):
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__()
        self.config = dict(config or {})
        self.warning = ""
        self.fallback = TinyVisionEditModel()
        try:
            from transformers import VideoMAEConfig, VideoMAEModel  # type: ignore

            backbone_config = VideoMAEConfig(
                image_size=int(self.config.get("size", 224)),
                hidden_size=96,
                num_hidden_layers=2,
                num_attention_heads=4,
                intermediate_size=192,
                tubelet_size=2,
                num_frames=int(self.config.get("num_frames", 8)),
            )
            self.backbone = VideoMAEModel(backbone_config)
            hidden = self.backbone.config.hidden_size
            self.boundary_head = nn.Linear(hidden, 1)
            self.motion_head = nn.Linear(hidden, len(MOTION_LABELS))
            self.transition_head = nn.Linear(hidden, len(TRANSITION_LABELS))
            self.overlay_head = nn.Linear(hidden, len(OVERLAY_LABELS))
            self.crop_head = nn.Sequential(nn.Linear(hidden, 32), nn.ReLU(), nn.Linear(32, 4), nn.Sigmoid())
            self.style_head = nn.Sequential(nn.Linear(hidden, 32), nn.ReLU(), nn.Linear(32, 16))
            self.uses_transformers = True
        except Exception as exc:  # pragma: no cover - optional path
            self.warning = f"transformers unavailable; falling back to TinyVisionEditModel: {exc}"
            self.uses_transformers = False

    def forward(self, frames: torch.Tensor) -> VisionEditOutput:
        if not getattr(self, "uses_transformers", False):
            return self.fallback(frames)

        squeezed = False
        if frames.dim() == 4:
            frames = frames.unsqueeze(0)
            squeezed = True
        pixel_values = frames.permute(0, 2, 1, 3, 4)
        outputs = self.backbone(pixel_values=pixel_values)
        tokens = outputs.last_hidden_state.mean(dim=2)
        boundary = self.boundary_head(tokens).squeeze(-1)
        motion = self.motion_head(tokens)
        transition = self.transition_head(tokens)
        overlay = self.overlay_head(tokens)
        crop = self.crop_head(tokens)
        style = self.style_head(tokens.mean(dim=1))
        if squeezed:
            return VisionEditOutput(
                boundary_logits=boundary.squeeze(0),
                motion_logits=motion.squeeze(0),
                transition_logits=transition.squeeze(0),
                overlay_logits=overlay.squeeze(0),
                crop_params=crop.squeeze(0),
                style_embedding=style.squeeze(0),
                frame_embeddings=tokens.squeeze(0),
                temporal_features=tokens.squeeze(0),
            )
        return VisionEditOutput(
            boundary_logits=boundary,
            motion_logits=motion,
            transition_logits=transition,
            overlay_logits=overlay,
            crop_params=crop,
            style_embedding=style,
            frame_embeddings=tokens,
            temporal_features=tokens,
        )


def build_vision_edit_model(config: Optional[Dict[str, Any]] = None) -> nn.Module:
    cfg = dict(config or {})
    if cfg.get("use_pretrained_backbone"):
        return PretrainedVideoEditModel(cfg)
    return TinyVisionEditModel()


def freeze_backbone(model: nn.Module) -> None:
    if hasattr(model, "backbone"):
        for param in model.backbone.parameters():
            param.requires_grad = False


def save_model_or_adapter(model: nn.Module, path: str) -> str:
    payload = {
        "state_dict": model.state_dict(),
        "class_name": model.__class__.__name__,
    }
    torch.save(payload, path)
    return path


def load_model_or_adapter(path: str) -> nn.Module:
    payload = torch.load(path, map_location="cpu")
    class_name = payload.get("class_name", "TinyVisionEditModel")
    if class_name == "PretrainedVideoEditModel":
        model = PretrainedVideoEditModel()
    else:
        model = TinyVisionEditModel()
    model.load_state_dict(payload["state_dict"], strict=False)
    return model
