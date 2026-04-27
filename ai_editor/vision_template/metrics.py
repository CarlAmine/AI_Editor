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
