from __future__ import annotations

from typing import Dict, Optional

import torch
import torch.nn.functional as F

from ai_editor.vision_template.model import VisionEditOutput


def _finite(value: torch.Tensor) -> torch.Tensor:
    value = torch.nan_to_num(value, nan=0.0, posinf=1e4, neginf=-1e4)
    if value.ndim == 0:
        return value
    return value.mean()


def _boundary_focal_bce(logits: torch.Tensor, labels: torch.Tensor, gamma: float = 2.0) -> torch.Tensor:
    logits = logits.float()
    labels = labels.float()
    pos_count = float(labels.sum().detach().cpu().item())
    neg_count = float(labels.numel() - labels.sum().detach().cpu().item())
    pos_weight_value = max(1.0, neg_count / max(pos_count, 1.0))
    pos_weight = torch.tensor(pos_weight_value, device=logits.device, dtype=logits.dtype)
    bce = F.binary_cross_entropy_with_logits(logits, labels, reduction="none", pos_weight=pos_weight)
    probs = torch.sigmoid(logits)
    pt = torch.where(labels > 0.5, probs, 1.0 - probs)
    focal = (1.0 - pt).pow(gamma)
    return (bce * focal).mean()


def compute_supervised_synthetic_loss(
    output: VisionEditOutput,
    labels: Dict[str, torch.Tensor],
    *,
    sparsity_weight: float = 0.01,
    smoothness_weight: float = 0.02,
    peak_weight: float = 0.08,
) -> torch.Tensor:
    boundary_target = labels["boundary"].float()
    boundary_logits = output.boundary_logits.float()
    boundary = _boundary_focal_bce(boundary_logits, boundary_target)

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

    boundary_prob = torch.sigmoid(boundary_logits)
    sparsity = boundary_prob.mean()
    smoothness = torch.abs(boundary_prob[..., 1:] - boundary_prob[..., :-1]).mean() if boundary_prob.shape[-1] > 1 else boundary_prob.mean() * 0.0
    peak_sharpness = ((boundary_prob - boundary_target) ** 2 * (1.0 + 3.0 * boundary_target)).mean()
    loss = boundary + motion + 0.7 * transition + 0.7 * overlay + 0.5 * crop + sparsity_weight * sparsity + smoothness_weight * smoothness + peak_weight * peak_sharpness
    return _finite(loss)


def compute_reference_adaptation_loss(
    output: VisionEditOutput,
    frames: torch.Tensor,
    *,
    expected_slots: Optional[int] = None,
    boundary_sparsity_weight: float = 0.015,
    entropy_weight: float = 0.01,
    discontinuity_weight: float = 0.25,
    slot_regularization_weight: float = 0.08,
    smoothness_weight: float = 0.03,
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

    if frames.shape[0] > 1:
        frame_delta = torch.abs(frames[1:] - frames[:-1]).mean(dim=(1, 2, 3))
        emb_delta = torch.norm(embeddings[1:] - embeddings[:-1], dim=-1)
        signal = frame_delta + emb_delta / (emb_delta.max() + 1e-6)
        target = signal / (signal.max() + 1e-6)
        predicted = boundary_prob[1:]
        discontinuity = F.mse_loss(predicted, target)
    else:
        discontinuity = boundary_prob.mean() * 0.0

    smoothness = torch.abs(boundary_prob[1:] - boundary_prob[:-1]).mean() if boundary_prob.shape[0] > 1 else boundary_prob.mean() * 0.0
    slot_regularization = boundary_prob.mean() * 0.0
    if expected_slots is not None:
        predicted_slots = boundary_prob.sum() + 1.0
        slot_regularization = (predicted_slots - float(expected_slots)) ** 2

    loss = (
        temporal_consistency
        + 0.35 * masked_reconstruction
        + boundary_sparsity_weight * sparsity
        + entropy_weight * entropy
        + discontinuity_weight * discontinuity
        + slot_regularization_weight * slot_regularization
        + smoothness_weight * smoothness
    )
    return _finite(loss)
