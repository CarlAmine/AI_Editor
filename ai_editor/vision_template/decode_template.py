from __future__ import annotations

from collections import Counter
from typing import List, Optional

import numpy as np
import torch

from .frame_sampler import SampledVideo
from .model import MOTION_LABELS, OVERLAY_LABELS, TRANSITION_LABELS, VisionEditOutput
from .schemas import CropSpec, EditSlot, EditTemplate, GlobalStyle, MotionSpec, OverlaySpec, validate_monotonic_slots


def _smooth_probabilities(probabilities: np.ndarray) -> np.ndarray:
    if len(probabilities) < 3:
        return probabilities.copy()
    kernel = np.array([0.2, 0.6, 0.2], dtype=np.float32)
    padded = np.pad(probabilities, (1, 1), mode="edge")
    return np.convolve(padded, kernel, mode="valid")


def _find_candidate_peaks(probabilities: np.ndarray) -> List[tuple[float, int]]:
    peaks: List[tuple[float, int]] = []
    if len(probabilities) <= 2:
        return peaks
    for idx in range(1, len(probabilities) - 1):
        center = float(probabilities[idx])
        if center >= float(probabilities[idx - 1]) and center >= float(probabilities[idx + 1]):
            peaks.append((center, idx))
    if not peaks:
        peaks = [(float(probabilities[idx]), idx) for idx in range(1, len(probabilities) - 1)]
    peaks.sort(key=lambda item: item[0], reverse=True)
    return peaks


def _pick_boundary_indices(
    probabilities: np.ndarray,
    timestamps: List[float],
    *,
    expected_slots: Optional[int],
    min_distance_frames: int,
    min_slot_duration: float,
    boundary_threshold: float,
) -> tuple[List[int], bool, List[str]]:
    peaks = _find_candidate_peaks(probabilities)
    warnings: List[str] = []
    fallback_used = False
    target_count = max(0, (expected_slots - 1) if expected_slots else 0)
    chosen: List[int] = []

    def far_enough(candidate: int) -> bool:
        return all(abs(candidate - existing) >= min_distance_frames for existing in chosen)

    chosen_scores: List[float] = []
    if expected_slots is not None:
        for score, idx in peaks:
            if far_enough(idx):
                chosen.append(idx)
                chosen_scores.append(float(score))
            if len(chosen) >= target_count:
                break
        if len(chosen) < target_count:
            fallback_used = True
            warnings.append("Boundary peak confidence was low; decoder used expected-slot fallback.")
            duration = max(float(timestamps[-1]) if timestamps else 0.0, min_slot_duration * max(expected_slots, 1))
            for split in range(1, expected_slots):
                target_time = duration * split / expected_slots
                nearest = min(range(1, max(len(timestamps) - 1, 2)), key=lambda i: abs(float(timestamps[i]) - target_time))
                if far_enough(nearest):
                    chosen.append(nearest)
                    chosen_scores.append(float(probabilities[nearest]))
            chosen = chosen[:target_count]
            chosen_scores = chosen_scores[:target_count]
        elif chosen_scores and float(np.mean(chosen_scores)) < max(0.35, boundary_threshold):
            warnings.append("Low-confidence boundary fallback used expected slot count prior.")
    else:
        adaptive_threshold = max(boundary_threshold, float(probabilities.mean() + 0.5 * probabilities.std()))
        for score, idx in peaks:
            if score < adaptive_threshold:
                continue
            if far_enough(idx):
                chosen.append(idx)
        if not chosen and peaks:
            fallback_used = True
            score, idx = peaks[0]
            chosen.append(idx)
            warnings.append("No confident internal boundary peaks were found; decoder used strongest available candidate.")

    return sorted(chosen), fallback_used, warnings


def _pacing_label(durations: List[float]) -> str:
    if not durations:
        return "medium"
    avg = float(np.mean(durations))
    variation = float(np.std(durations) / max(avg, 1e-6))
    if variation > 0.45:
        return "variable"
    if avg >= 2.8:
        return "slow"
    if avg <= 1.2:
        return "fast"
    return "medium"


def decode_edit_template(
    model_output: VisionEditOutput,
    sampled_video: SampledVideo,
    expected_slots: Optional[int] = None,
    min_slot_duration: float = 0.3,
    boundary_threshold: float = 0.5,
) -> EditTemplate:
    boundary_logits = model_output.boundary_logits
    if boundary_logits.dim() > 1:
        boundary_logits = boundary_logits.squeeze(0)
    probabilities = torch.sigmoid(boundary_logits).detach().cpu().numpy()
    smoothed = _smooth_probabilities(probabilities)
    embeddings = model_output.frame_embeddings
    if embeddings.dim() > 2:
        embeddings = embeddings.squeeze(0)
    if embeddings.shape[0] > 1:
        emb_delta = torch.norm(embeddings[1:] - embeddings[:-1], dim=-1).detach().cpu().numpy()
        emb_delta = np.concatenate([[0.0], emb_delta])
        emb_signal = emb_delta / max(float(np.max(emb_delta)), 1e-6)
    else:
        emb_signal = np.zeros_like(smoothed)
    combined = 0.45 * smoothed + 0.55 * emb_signal
    if len(smoothed) > 0:
        smoothed[0] = 0.0
        smoothed[-1] = 0.0
        combined[0] = 0.0
        combined[-1] = 0.0

    frame_step = sampled_video.timestamps[1] - sampled_video.timestamps[0] if len(sampled_video.timestamps) > 1 else 1.0 / max(sampled_video.fps, 1.0)
    min_distance_frames = max(1, int(round(min_slot_duration / max(frame_step, 1e-6))))
    chosen, fallback_used, decode_warnings = _pick_boundary_indices(
        combined,
        sampled_video.timestamps,
        expected_slots=expected_slots,
        min_distance_frames=min_distance_frames,
        min_slot_duration=min_slot_duration,
        boundary_threshold=boundary_threshold,
    )

    boundaries = [0.0] + [float(sampled_video.timestamps[idx]) for idx in chosen] + [float(sampled_video.duration)]
    boundaries = sorted(boundaries)

    merged = [boundaries[0]]
    for timestamp in boundaries[1:]:
        if timestamp - merged[-1] >= min_slot_duration:
            merged.append(timestamp)
        else:
            merged[-1] = max(merged[-1], timestamp)
    if expected_slots is not None and len(merged) - 1 != expected_slots and len(sampled_video.timestamps) >= expected_slots:
        fallback_used = True
        decode_warnings.append("Decoder adjusted boundaries to match expected slot count.")
        duration = max(float(sampled_video.duration), min_slot_duration * expected_slots)
        merged = [0.0] + [duration * idx / expected_slots for idx in range(1, expected_slots)] + [duration]
    if len(merged) < 2:
        merged = [0.0, float(sampled_video.duration)]
        decode_warnings.append("No useful boundaries were found; decoder fell back to a single-slot template.")
        fallback_used = True

    slots: List[EditSlot] = []
    transition_votes: List[str] = []
    motion_logits = model_output.motion_logits
    transition_logits = model_output.transition_logits
    overlay_logits = model_output.overlay_logits
    crop_params = model_output.crop_params
    style_embedding = model_output.style_embedding.detach().cpu().numpy().tolist() if model_output.style_embedding.ndim == 1 else model_output.style_embedding.detach().cpu().mean(dim=0).numpy().tolist()
    timestamps = sampled_video.timestamps

    for slot_id, (start, end) in enumerate(zip(merged[:-1], merged[1:]), start=1):
        start_index = max(0, next((i for i, ts in enumerate(timestamps) if ts >= start), 0))
        end_index = max(start_index + 1, next((i for i, ts in enumerate(timestamps) if ts >= end), len(timestamps) - 1))
        motion_slice = motion_logits[start_index:end_index]
        transition_slice = transition_logits[start_index:end_index]
        overlay_slice = overlay_logits[start_index:end_index]
        crop_slice = crop_params[start_index:end_index]
        boundary_region = combined[max(0, end_index - 2): min(len(combined), end_index + 1)]
        boundary_confidence = float(np.max(boundary_region)) if boundary_region.size else float(combined[min(end_index - 1, max(len(combined) - 1, 0))]) if len(combined) else 0.0

        motion_index = int(motion_slice.mean(dim=0).argmax().item()) if motion_slice.numel() else len(MOTION_LABELS) - 1
        transition_index = int(transition_slice.mean(dim=0).argmax().item()) if transition_slice.numel() else 0
        overlay_index = int(overlay_slice.mean(dim=0).argmax().item()) if overlay_slice.numel() else 0
        transition_votes.append(TRANSITION_LABELS[transition_index])

        overlay = None
        if OVERLAY_LABELS[overlay_index] != "none":
            overlay = OverlaySpec(
                has_overlay=True,
                region=OVERLAY_LABELS[overlay_index],
                start_rel=0.0,
                end_rel=1.0,
                mask_confidence=float(torch.softmax(overlay_slice.mean(dim=0), dim=0)[overlay_index].item()) if overlay_slice.numel() else 0.0,
            )
        crop_mean = crop_slice.mean(dim=0) if crop_slice.numel() else torch.tensor([0.0, 0.0, 1.0, 1.0])
        slot = EditSlot(
            slot_id=slot_id,
            start=float(start),
            end=float(end),
            duration=max(float(end - start), min_slot_duration),
            boundary_confidence=boundary_confidence,
            transition_in=TRANSITION_LABELS[transition_index],
            transition_out=TRANSITION_LABELS[transition_index],
            motion=MotionSpec(
                kind=MOTION_LABELS[motion_index],
                confidence=float(torch.softmax(motion_slice.mean(dim=0), dim=0)[motion_index].item()) if motion_slice.numel() else 0.0,
                keyframes=[{"t": 0.0, "value": MOTION_LABELS[motion_index]}, {"t": 1.0, "value": MOTION_LABELS[motion_index]}],
            ),
            crop=CropSpec(
                x=float(crop_mean[0].item()),
                y=float(crop_mean[1].item()),
                width=float(crop_mean[2].item()),
                height=float(crop_mean[3].item()),
            ),
            overlay=overlay,
            style_vector=style_embedding[:8] if style_embedding else None,
        )
        slots.append(slot)

    if not slots:
        slots = [
            EditSlot(
                slot_id=1,
                start=0.0,
                end=float(sampled_video.duration),
                duration=max(float(sampled_video.duration), min_slot_duration),
                boundary_confidence=0.0,
                transition_in="cut",
                transition_out="cut",
                motion=MotionSpec(kind="unknown", confidence=0.0, keyframes=[]),
                crop=CropSpec(),
                overlay=None,
                style_vector=style_embedding[:8] if style_embedding else None,
            )
        ]
        fallback_used = True

    durations = [slot.duration for slot in slots]
    dominant_transition = Counter(transition_votes or ["cut"]).most_common(1)[0][0]
    aspect_ratio = None
    if sampled_video.original_height > 0:
        ratio = sampled_video.original_width / max(sampled_video.original_height, 1)
        if abs(ratio - (16 / 9)) < 0.15:
            aspect_ratio = "16:9"
        elif abs(ratio - (9 / 16)) < 0.15:
            aspect_ratio = "9:16"
        elif abs(ratio - 1.0) < 0.1:
            aspect_ratio = "1:1"

    warnings = list(dict.fromkeys(decode_warnings))
    if fallback_used:
        warnings.append("decoder_fallback_used")
    if slots and float(np.mean([slot.boundary_confidence for slot in slots])) < 0.35:
        warnings.append("Low-confidence boundary peaks were decoded into a valid template.")

    template = EditTemplate(
        version="0.1",
        source_reference=None,
        fps=sampled_video.fps,
        total_duration=float(sampled_video.duration),
        slots=slots,
        global_style=GlobalStyle(
            avg_slot_duration=float(np.mean(durations)),
            rhythm=[round(duration, 4) for duration in durations],
            pacing_label=_pacing_label(durations),
            dominant_transition=dominant_transition,
            aspect_ratio=aspect_ratio,
            style_embedding=style_embedding[:16] if style_embedding else None,
        ),
        training_summary=None,
        warnings=warnings,
    )
    validate_monotonic_slots(template)
    return template
