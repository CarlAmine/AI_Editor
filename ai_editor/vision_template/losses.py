from __future__ import annotations

from typing import Dict, Optional

import torch
import torch.nn.functional as F

from .model import VisionEditOutput


def _finite(value: torch.Tensor) -> torch.Tensor:
    return torch.nan_to_num(value, nan=0.0, posinf=1e4, neginf=-1e4)


def compute_supervised_synthetic_loss(
    output: VisionEditOutput,
    labels: Dict[str, torch.Tensor],
    *,
    sparsity_weight: float = 0.02,
    smoothness_weight: float = 0.02,
) -> torch.Tensor:
    boundary = F.binary_cross_entropy_with_logits(
        output.boundary_logits.float(),
        labels["boundary"].float(),
    )
    motion = F.cross_entropy(
        output.motion_logits.reshape(-1, output.motion_logits.shape[-1]),
        labels["motion"].reshape(-1).long(),
    )
    transition = F.cross_entropy(
        output.transition_logits.reshape(-1, output.transition_logits.shape[-1]),
        labels["transition"].reshape(-1).long(),
    )
    overlay = F.cross_entropy(
        output.overlay_logits.reshape(-1, output.overlay_logits.shape[-1]),
        labels["overlay"].reshape(-1).long(),
    )
    crop = F.smooth_l1_loss(output.crop_params.float(), labels["crop"].float())
    boundary_prob = torch.sigmoid(output.boundary_logits.float())
    sparsity = boundary_prob.mean()
    smoothness = torch.abs(boundary_prob[..., 1:] - boundary_prob[..., :-1]).mean()
    loss = boundary + motion + transition + overlay + crop + sparsity_weight * sparsity + smoothness_weight * smoothness
    return _finite(loss)


def compute_reference_adaptation_loss(
    output: VisionEditOutput,
    frames: torch.Tensor,
    *,
    expected_slots: Optional[int] = None,
    boundary_sparsity_weight: float = 0.02,
    entropy_weight: float = 0.01,
    discontinuity_weight: float = 0.15,
    slot_regularization_weight: float = 0.05,
) -> torch.Tensor:
    if frames.dim() == 5:
        frames = frames.squeeze(0)
    embeddings = output.frame_embeddings
    if embeddings.dim() == 3:
        embeddings = embeddings.squeeze(0)
    boundary_logits = output.boundary_logits
    if boundary_logits.dim() == 2:
        boundary_logits = boundary_logits.squeeze(0)
    boundary_prob = torch.sigmoid(boundary_logits)

    temporal_consistency = F.mse_loss(embeddings[1:], embeddings[:-1]) if embeddings.shape[0] > 1 else embeddings.mean() * 0
    reconstructed = embeddings.mean(dim=0, keepdim=True).expand_as(embeddings)
    masked_reconstruction = F.mse_loss(embeddings, reconstructed)
    sparsity = boundary_prob.mean()
    entropy = -(boundary_prob * torch.log(boundary_prob + 1e-6) + (1.0 - boundary_prob) * torch.log(1.0 - boundary_prob + 1e-6)).mean()

    frame_delta = torch.abs(frames[1:] - frames[:-1]).mean(dim=(1, 2, 3))
    emb_delta = torch.norm(embeddings[1:] - embeddings[:-1], dim=-1)
    signal = frame_delta + emb_delta / max(float(emb_delta.max().item() or 1.0), 1.0)
    target = signal / (signal.max() + 1e-6)
    predicted = boundary_prob[1:]
    discontinuity = F.mse_loss(predicted, target)

    slot_regularization = boundary_prob.mean() * 0.0
    if expected_slots is not None:
        predicted_slots = boundary_prob.sum() + 1.0
        slot_regularization = (predicted_slots - float(expected_slots)) ** 2

    loss = (
        temporal_consistency
        + 0.5 * masked_reconstruction
        + boundary_sparsity_weight * sparsity
        + entropy_weight * entropy
        + discontinuity_weight * discontinuity
        + slot_regularization_weight * slot_regularization
    )
    return _finite(loss)
