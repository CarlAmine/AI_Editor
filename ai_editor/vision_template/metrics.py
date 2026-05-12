from __future__ import annotations

from typing import Sequence

import numpy as np

from .schemas import EditTemplate


def _durations(template: EditTemplate) -> list[float]:
    return [float(slot.duration) for slot in template.slots]


def _boundaries(template: EditTemplate) -> list[float]:
    if not template.slots:
        return [0.0]
    return [float(slot.start) for slot in template.slots] + [float(template.slots[-1].end)]


def _internal_boundaries(template: EditTemplate) -> list[float]:
    return [float(slot.end) for slot in template.slots[:-1]]


def slot_count_error(pred: EditTemplate, target: EditTemplate) -> int:
    return abs(len(pred.slots) - len(target.slots))


def total_duration_error(pred: EditTemplate, target: EditTemplate) -> float:
    return abs(float(pred.total_duration) - float(target.total_duration))


def duration_mae(pred: EditTemplate, target: EditTemplate) -> float:
    pred_durations = _durations(pred)
    target_durations = _durations(target)
    count = min(len(pred_durations), len(target_durations))
    if count == 0:
        return 0.0
    return float(np.mean(np.abs(np.array(pred_durations[:count]) - np.array(target_durations[:count]))))


def boundary_time_mae(pred: EditTemplate, target: EditTemplate) -> float:
    pred_bounds = _boundaries(pred)
    target_bounds = _boundaries(target)
    count = min(len(pred_bounds), len(target_bounds))
    if count == 0:
        return 0.0
    return float(np.mean(np.abs(np.array(pred_bounds[:count]) - np.array(target_bounds[:count]))))


def rhythm_correlation(pred: EditTemplate, target: EditTemplate) -> float:
    pred_rhythm = pred.global_style.rhythm or _durations(pred)
    target_rhythm = target.global_style.rhythm or _durations(target)
    count = min(len(pred_rhythm), len(target_rhythm))
    if count < 2:
        return 1.0
    corr = np.corrcoef(np.array(pred_rhythm[:count]), np.array(target_rhythm[:count]))[0, 1]
    if np.isnan(corr):
        return 0.0
    return float(corr)


def boundary_precision_recall_with_tolerance(pred: EditTemplate, target: EditTemplate, tolerance: float = 0.5) -> dict:
    pred_bounds = _internal_boundaries(pred)
    target_bounds = _internal_boundaries(target)
    if not pred_bounds and not target_bounds:
        return {"precision": 1.0, "recall": 1.0, "tp": 0, "fp": 0, "fn": 0}

    matched_target = set()
    tp = 0
    for pred_bound in pred_bounds:
        best_index = None
        best_error = None
        for index, target_bound in enumerate(target_bounds):
            if index in matched_target:
                continue
            error = abs(pred_bound - target_bound)
            if error <= tolerance and (best_error is None or error < best_error):
                best_error = error
                best_index = index
        if best_index is not None:
            matched_target.add(best_index)
            tp += 1
    fp = max(0, len(pred_bounds) - tp)
    fn = max(0, len(target_bounds) - tp)
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    return {"precision": float(precision), "recall": float(recall), "tp": tp, "fp": fp, "fn": fn}


def decode_confidence_summary(template: EditTemplate) -> dict:
    confidences = [float(slot.boundary_confidence) for slot in template.slots]
    if not confidences:
        return {"mean_boundary_confidence": 0.0, "min_boundary_confidence": 0.0, "fallback_used": False}
    return {
        "mean_boundary_confidence": float(np.mean(confidences)),
        "min_boundary_confidence": float(np.min(confidences)),
        "fallback_used": any(str(warning).strip().lower() == "decoder_fallback_used" for warning in (template.warnings or [])),
    }


def timeline_validity_score(timeline: dict | Sequence[dict]) -> float:
    rows = timeline.get("timeline", []) if isinstance(timeline, dict) else list(timeline)
    if not rows:
        return 0.0
    previous_end = 0.0
    valid = 0
    for row in rows:
        start = float(row.get("start", 0.0))
        end = float(row.get("end", start))
        duration = float(row.get("duration", row.get("length", 0.0)))
        if end > start and duration > 0 and start >= previous_end - 1e-6 and row.get("video_src"):
            valid += 1
        previous_end = max(previous_end, end)
    return float(valid / max(len(rows), 1))
