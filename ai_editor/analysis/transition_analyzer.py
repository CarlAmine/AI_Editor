from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

try:
    import cv2
    import numpy as np

    _CV2_AVAILABLE = True
except Exception:  # pragma: no cover - dependency availability varies by environment
    cv2 = None  # type: ignore
    np = None  # type: ignore
    _CV2_AVAILABLE = False

from .analysis_schema import Scene, TransitionEvent, TransitionType

log = logging.getLogger(__name__)

_BOUNDARY_WINDOW_FRAMES = 18
_BLACK_LUMA_MAX = 18
_WHITE_LUMA_MIN = 237
_FADE_SLOPE_MIN = 4.0
_DISSOLVE_VARIANCE_MAX = 1800.0
_ZOOM_PUNCH_SCALE_MIN = 1.12
_WHIP_PAN_FLOW_MIN = 0.06


class TransitionAnalyzer:
    """
    Detects the type of transition between each pair of consecutive shots.
    """

    def analyze(self, video_path: str, scenes: List[Scene]) -> List[TransitionEvent]:
        if not _CV2_AVAILABLE or len(scenes) < 2:
            return []

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            log.error("Cannot open video: %s", video_path)
            return []

        fps = float(cap.get(cv2.CAP_PROP_FPS)) or 25.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        transitions: List[TransitionEvent] = []

        for index in range(len(scenes) - 1):
            boundary_frame = int(scenes[index].end_time * fps)
            window_start = max(0, boundary_frame - _BOUNDARY_WINDOW_FRAMES)
            window_end = min(total_frames - 1, boundary_frame + _BOUNDARY_WINDOW_FRAMES)
            frames = self._extract_frames(cap, window_start, window_end)

            if len(frames) < 4:
                transitions.append(self._hard_cut(index, index + 1, boundary_frame, fps))
                continue

            event = self._classify_boundary(
                frames=frames,
                boundary_frame=boundary_frame,
                window_start=window_start,
                outgoing_idx=index,
                incoming_idx=index + 1,
                fps=fps,
                width=width,
                height=height,
            )
            transitions.append(event)

        cap.release()
        return transitions

    def _extract_frames(self, cap: Any, start: int, end: int) -> List[Any]:
        cap.set(cv2.CAP_PROP_POS_FRAMES, float(start))
        frames = []
        for _ in range(end - start + 1):
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame)
        return frames

    def _classify_boundary(
        self,
        frames: List[Any],
        boundary_frame: int,
        window_start: int,
        outgoing_idx: int,
        incoming_idx: int,
        fps: float,
        width: int,
        height: int,
    ) -> TransitionEvent:
        luma_curve = [self._mean_luma(frame) for frame in frames]
        cut_local = boundary_frame - window_start

        flash = self._detect_flash(luma_curve, cut_local)
        if flash:
            return TransitionEvent(
                boundary_frame_index=boundary_frame,
                outgoing_shot_index=outgoing_idx,
                incoming_shot_index=incoming_idx,
                transition_type=TransitionType.FLASH_CUT,
                duration_frames=flash["duration_frames"],
                duration_sec=flash["duration_frames"] / max(fps, 1.0),
                intensity=round(flash["intensity"], 4),
                luminance_curve=luma_curve,
                metadata=flash,
            )

        fade = self._detect_fade(luma_curve, cut_local)
        if fade:
            return TransitionEvent(
                boundary_frame_index=boundary_frame,
                outgoing_shot_index=outgoing_idx,
                incoming_shot_index=incoming_idx,
                transition_type=fade["transition_type"],
                duration_frames=fade["duration_frames"],
                duration_sec=fade["duration_frames"] / max(fps, 1.0),
                intensity=round(fade["intensity"], 4),
                luminance_curve=luma_curve,
                metadata=fade,
            )

        dissolve = self._detect_dissolve(luma_curve, cut_local)
        if dissolve:
            return TransitionEvent(
                boundary_frame_index=boundary_frame,
                outgoing_shot_index=outgoing_idx,
                incoming_shot_index=incoming_idx,
                transition_type=TransitionType.CROSS_DISSOLVE,
                duration_frames=dissolve["duration_frames"],
                duration_sec=dissolve["duration_frames"] / max(fps, 1.0),
                intensity=round(dissolve["intensity"], 4),
                luminance_curve=luma_curve,
                metadata=dissolve,
            )

        zoom = self._detect_zoom_punch(frames, cut_local, width, height)
        if zoom:
            return TransitionEvent(
                boundary_frame_index=boundary_frame,
                outgoing_shot_index=outgoing_idx,
                incoming_shot_index=incoming_idx,
                transition_type=TransitionType.ZOOM_PUNCH,
                duration_frames=1,
                duration_sec=round(1.0 / max(fps, 1.0), 4),
                intensity=round(min(zoom["scale_ratio"] / 2.0, 1.0), 4),
                luminance_curve=luma_curve,
                metadata=zoom,
            )

        whip = self._detect_whip_pan(frames, cut_local, width)
        if whip:
            return TransitionEvent(
                boundary_frame_index=boundary_frame,
                outgoing_shot_index=outgoing_idx,
                incoming_shot_index=incoming_idx,
                transition_type=TransitionType.WHIP_PAN,
                duration_frames=whip["blur_frames"],
                duration_sec=whip["blur_frames"] / max(fps, 1.0),
                intensity=round(whip["intensity"], 4),
                luminance_curve=luma_curve,
                metadata=whip,
            )

        return self._hard_cut(outgoing_idx, incoming_idx, boundary_frame, fps, luma_curve=luma_curve)

    def _mean_luma(self, frame: Any) -> float:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return float(np.mean(gray))

    def _detect_flash(self, luma: List[float], cut_local: int) -> Optional[Dict[str, Any]]:
        window = range(max(0, cut_local - 3), min(len(luma), cut_local + 4))
        flash_frames = [index for index in window if luma[index] > _WHITE_LUMA_MIN or luma[index] < _BLACK_LUMA_MAX]
        if not flash_frames or len(flash_frames) > 4:
            return None
        if len(flash_frames) >= 2:
            monotonic_luma = [luma[index] for index in flash_frames]
            if monotonic_luma == sorted(monotonic_luma, reverse=True) or monotonic_luma == sorted(monotonic_luma):
                return None
        before = cut_local - len(flash_frames) - 1
        if before >= 0 and (luma[before] > _WHITE_LUMA_MIN or luma[before] < _BLACK_LUMA_MAX):
            return None
        after = flash_frames[-1] + 1
        if after < len(luma) and (luma[after] > _WHITE_LUMA_MIN or luma[after] < _BLACK_LUMA_MAX):
            return None
        peak = max(luma[index] for index in flash_frames)
        if peak > _WHITE_LUMA_MIN:
            intensity = peak / 255.0
        else:
            intensity = 1.0 - (min(luma[index] for index in flash_frames) / max(_BLACK_LUMA_MAX, 1))
        return {
            "duration_frames": len(flash_frames),
            "intensity": round(float(intensity), 4),
            "peak_luma": round(float(peak), 2),
        }

    def _detect_fade(self, luma: List[float], cut_local: int) -> Optional[Dict[str, Any]]:
        out_luma = luma[:cut_local]
        in_luma = luma[cut_local:]

        if out_luma and out_luma[-1] < _BLACK_LUMA_MAX:
            span = self._monotonic_run_end(out_luma, "down")
            if span >= 3:
                slope = (out_luma[-span] - out_luma[-1]) / max(span, 1)
                if slope >= _FADE_SLOPE_MIN:
                    return {
                        "transition_type": TransitionType.FADE_TO_BLACK,
                        "duration_frames": span,
                        "intensity": round(1.0 - out_luma[-1] / 255.0, 4),
                        "slope": round(float(slope), 3),
                    }

        if in_luma and in_luma[0] < _BLACK_LUMA_MAX:
            span = self._monotonic_run_start(in_luma, "up")
            if span >= 3:
                slope = (in_luma[span - 1] - in_luma[0]) / max(span, 1)
                if slope >= _FADE_SLOPE_MIN:
                    return {
                        "transition_type": TransitionType.FADE_FROM_BLACK,
                        "duration_frames": span,
                        "intensity": round(1.0 - in_luma[0] / 255.0, 4),
                        "slope": round(float(slope), 3),
                    }

        if out_luma and out_luma[-1] > _WHITE_LUMA_MIN:
            span = self._monotonic_run_end(out_luma, "up")
            if span >= 3:
                slope = (out_luma[-1] - out_luma[-span]) / max(span, 1)
                if slope >= _FADE_SLOPE_MIN:
                    return {
                        "transition_type": TransitionType.FADE_TO_WHITE,
                        "duration_frames": span,
                        "intensity": round(out_luma[-1] / 255.0, 4),
                        "slope": round(float(slope), 3),
                    }

        if in_luma and in_luma[0] > _WHITE_LUMA_MIN:
            span = self._monotonic_run_start(in_luma, "down")
            if span >= 3:
                slope = (in_luma[0] - in_luma[span - 1]) / max(span, 1)
                if slope >= _FADE_SLOPE_MIN:
                    return {
                        "transition_type": TransitionType.FADE_FROM_WHITE,
                        "duration_frames": span,
                        "intensity": round(in_luma[0] / 255.0, 4),
                        "slope": round(float(slope), 3),
                    }
        return None

    def _detect_dissolve(self, luma: List[float], cut_local: int) -> Optional[Dict[str, Any]]:
        lo = max(0, cut_local - 6)
        hi = min(len(luma), cut_local + 7)
        window = luma[lo:hi]
        if len(window) < 6:
            return None
        if min(window) < _BLACK_LUMA_MAX or max(window) > _WHITE_LUMA_MIN:
            return None
        variance = float(np.var(window))
        if variance > _DISSOLVE_VARIANCE_MAX:
            return None
        diffs = [abs(window[index + 1] - window[index]) for index in range(len(window) - 1)]
        if diffs and max(diffs) > 25.0:
            return None
        return {
            "duration_frames": hi - lo,
            "intensity": round(1.0 - variance / _DISSOLVE_VARIANCE_MAX, 4),
            "luma_variance": round(variance, 2),
            "max_frame_jump": round(float(max(diffs)) if diffs else 0.0, 2),
        }

    def _detect_zoom_punch(self, frames: List[Any], cut_local: int, width: int, height: int) -> Optional[Dict[str, Any]]:
        if cut_local == 0 or cut_local >= len(frames) - 1:
            return None
        out_frame = frames[cut_local]
        in_frame = frames[cut_local + 1]
        cy, cx = height // 2, width // 2
        crop_h, crop_w = int(height * 0.60), int(width * 0.60)
        y1, x1 = cy - crop_h // 2, cx - crop_w // 2
        out_crop = out_frame[y1:y1 + crop_h, x1:x1 + crop_w]
        out_resized = cv2.resize(out_crop, (width, height))
        out_gray = cv2.cvtColor(out_resized, cv2.COLOR_BGR2GRAY).astype(np.float32)
        in_gray = cv2.cvtColor(in_frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
        if float(np.std(out_gray)) < 8.0 or float(np.std(in_gray)) < 8.0:
            return None
        if abs(float(np.mean(out_gray)) - float(np.mean(in_gray))) > 25.0:
            return None
        out_norm = out_gray / (float(np.std(out_gray)) + 1e-6)
        in_norm = in_gray / (float(np.std(in_gray)) + 1e-6)
        similarity = float(np.mean(out_norm * in_norm))
        if similarity < 0.55:
            return None
        scale_ratio = 1.0 / 0.60
        if scale_ratio < _ZOOM_PUNCH_SCALE_MIN:
            return None
        return {"scale_ratio": round(scale_ratio, 3), "crop_similarity": round(similarity, 4)}

    def _detect_whip_pan(self, frames: List[Any], cut_local: int, width: int) -> Optional[Dict[str, Any]]:
        start = max(0, cut_local - 4)
        pre_frames = frames[start:cut_local + 1]
        if len(pre_frames) < 2:
            return None
        total_flow = 0.0
        flow_count = 0
        for index in range(len(pre_frames) - 1):
            gray_a = cv2.cvtColor(pre_frames[index], cv2.COLOR_BGR2GRAY)
            gray_b = cv2.cvtColor(pre_frames[index + 1], cv2.COLOR_BGR2GRAY)
            flow = cv2.calcOpticalFlowFarneback(
                gray_a,
                gray_b,
                None,
                pyr_scale=0.5,
                levels=3,
                winsize=15,
                iterations=3,
                poly_n=5,
                poly_sigma=1.2,
                flags=0,
            )
            mag = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)
            total_flow += float(np.mean(mag)) / max(width, 1)
            flow_count += 1
        if flow_count == 0:
            return None
        avg_flow = total_flow / flow_count
        if avg_flow < _WHIP_PAN_FLOW_MIN:
            return None
        return {
            "blur_frames": len(pre_frames) - 1,
            "intensity": round(min(avg_flow / 0.15, 1.0), 4),
            "avg_flow_norm": round(avg_flow, 4),
        }

    def _monotonic_run_end(self, luma: List[float], direction: str) -> int:
        count = 0
        for index in range(len(luma) - 1, 0, -1):
            if direction == "down" and luma[index] <= luma[index - 1]:
                count += 1
            elif direction == "up" and luma[index] >= luma[index - 1]:
                count += 1
            else:
                break
        return count

    def _monotonic_run_start(self, luma: List[float], direction: str) -> int:
        count = 0
        for index in range(len(luma) - 1):
            if direction == "up" and luma[index + 1] >= luma[index]:
                count += 1
            elif direction == "down" and luma[index + 1] <= luma[index]:
                count += 1
            else:
                break
        return count + 1 if count > 0 else 1

    def _hard_cut(
        self,
        outgoing_idx: int,
        incoming_idx: int,
        boundary_frame: int,
        fps: float,
        luma_curve: Optional[List[float]] = None,
    ) -> TransitionEvent:
        return TransitionEvent(
            boundary_frame_index=boundary_frame,
            outgoing_shot_index=outgoing_idx,
            incoming_shot_index=incoming_idx,
            transition_type=TransitionType.HARD_CUT,
            duration_frames=1,
            duration_sec=round(1.0 / max(fps, 1.0), 4),
            intensity=1.0,
            luminance_curve=luma_curve or [],
        )
