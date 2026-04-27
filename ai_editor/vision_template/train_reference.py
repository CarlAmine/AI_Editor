from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional

import torch

from . import VisionTemplateError
from .decode_template import decode_edit_template
from .frame_sampler import sample_video_frames
from .losses import compute_reference_adaptation_loss
from .model import build_vision_edit_model, save_model_or_adapter
from .schemas import EditTemplate, TrainingSummary


@dataclass
class TrainingResult:
    model_path: str
    template_path: str
    raw_output_path: str
    training_summary_path: str
    template: EditTemplate


def _resolve_device(raw: str) -> str:
    if raw == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    return raw


def train_reference_adapter(
    reference_video_path: str,
    out_dir: str,
    base_model_path: str | None = None,
    epochs: int = 5,
    fps: float = 8.0,
    size: int = 224,
    device: str = "auto",
    max_seconds: float | None = None,
    expected_slots: int | None = None,
    use_pretrained_backbone: bool = False,
) -> TrainingResult:
    os.makedirs(out_dir, exist_ok=True)
    sampled = sample_video_frames(reference_video_path, fps=fps, size=size, max_seconds=max_seconds)
    resolved_device = _resolve_device(device)
    warnings = []

    model = build_vision_edit_model(
        {
            "use_pretrained_backbone": use_pretrained_backbone,
            "size": size,
            "num_frames": sampled.frames.shape[0],
        }
    )
    model.to(resolved_device)
    optimizer = torch.optim.Adam([param for param in model.parameters() if param.requires_grad], lr=1e-3)
    frames = sampled.frames.to(resolved_device)
    final_loss = None
    boundary_loss = None

    try:
        for _epoch in range(max(int(epochs), 1)):
            model.train()
            optimizer.zero_grad()
            output = model(frames)
            loss = compute_reference_adaptation_loss(output, frames, expected_slots=expected_slots)
            if not torch.isfinite(loss):
                raise VisionTemplateError("Reference adaptation loss became non-finite.")
            loss.backward()
            optimizer.step()
            final_loss = float(loss.detach().cpu().item())
            boundary_loss = float(torch.sigmoid(output.boundary_logits).mean().detach().cpu().item())
    except Exception as exc:
        raise VisionTemplateError(f"Vision template training failed: {exc}") from exc

    model.eval()
    with torch.no_grad():
        output = model(frames)

    template = decode_edit_template(output, sampled, expected_slots=expected_slots)
    template.source_reference = reference_video_path
    if len(template.slots) <= 1:
        template.warnings.append("Low-confidence decode fallback produced a single-slot template.")
    if any(slot.boundary_confidence < 0.35 for slot in template.slots):
        template.warnings.append("Some slot boundaries were low confidence.")

    summary = TrainingSummary(
        epochs=max(int(epochs), 1),
        final_loss=final_loss,
        boundary_loss=boundary_loss,
        self_supervised_loss=final_loss,
        device=resolved_device,
        model_type=model.__class__.__name__,
        used_pretrained_backbone=bool(use_pretrained_backbone and model.__class__.__name__ == "PretrainedVideoEditModel"),
        warning_count=len(template.warnings),
    )
    template.training_summary = summary

    model_path = os.path.join(out_dir, "vision_model.pt")
    raw_output_path = os.path.join(out_dir, "vision_template_raw_output.pt")
    template_path = os.path.join(out_dir, "edit_template.json")
    summary_path = os.path.join(out_dir, "training_summary.json")

    save_model_or_adapter(model, model_path)
    torch.save(
        {
            "boundary_logits": output.boundary_logits.detach().cpu(),
            "motion_logits": output.motion_logits.detach().cpu(),
            "transition_logits": output.transition_logits.detach().cpu(),
            "overlay_logits": output.overlay_logits.detach().cpu(),
            "crop_params": output.crop_params.detach().cpu(),
            "style_embedding": output.style_embedding.detach().cpu(),
        },
        raw_output_path,
    )
    template.to_json_file(template_path)
    with open(summary_path, "w", encoding="utf-8") as handle:
        json.dump(summary.model_dump() if hasattr(summary, "model_dump") else summary.dict(), handle, ensure_ascii=False, indent=2)

    return TrainingResult(
        model_path=model_path,
        template_path=template_path,
        raw_output_path=raw_output_path,
        training_summary_path=summary_path,
        template=template,
    )
