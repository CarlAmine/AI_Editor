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

from .analysis_schema import EffectType, MotionCurve, MotionEffect, MotionEffectManifest, Scene

log = logging.getLogger(__name__)

_SHAKE_FREQ_MIN_HZ = 3.0
_SHAKE_AMP_MIN_NORM = 0.008
_ZOOM_SCALE_DELTA_MIN = 0.004
_PAN_SMOOTHNESS_MAX = 0.30
_FREEZE_MOTION_MAX = 0.001
_RESIDUAL_GLITCH_MIN = 8.0
_RESIDUAL_SMEAR_MIN = 4.0
_MIN_EFFECT_DURATION_SEC = 0.15


class MotionEffectAnalyzer:
    """
    Extracts applied visual effects from a video by decomposing per-frame
    optical flow into global (camera/effect) motion and local (subject) motion.
    """

    def __init__(
        self,
        sample_every_n_frames: int = 1,
        max_corners: int = 400,
        lk_params: Optional[Dict[str, Any]] = None,
    ) -> None:
        criteria = None
        if _CV2_AVAILABLE:
            criteria = cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01
        self.sample_every_n_frames = max(1, int(sample_every_n_frames))
        self.max_corners = max(10, int(max_corners))
        self.lk_params = lk_params or {
            "winSize": (21, 21),
            "maxLevel": 3,
            "criteria": criteria,
        }

    def analyze(self, video_path: str, scenes: List[Scene]) -> MotionEffectManifest:
        if not _CV2_AVAILABLE:
            log.warning("cv2 not available; returning empty MotionEffectManifest")
            return self._empty_manifest(video_path)

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            log.error("Cannot open video: %s", video_path)
            return self._empty_manifest(video_path)

        fps = float(cap.get(cv2.CAP_PROP_FPS)) or 25.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

        try:
            raw_curves = self._extract_global_motion(cap, fps, width, height, total_frames)
        finally:
            cap.release()

        effects: List[MotionEffect] = []
        for shot_idx, scene in enumerate(scenes):
            shot_curve = self._slice_curve(raw_curves, scene, fps)
            effects.extend(self._classify_shot(shot_idx, shot_curve, fps, scene))

        all_dx = raw_curves.get("dx_norm", [])
        all_dy = raw_curves.get("dy_norm", [])
        if all_dx and all_dy:
            global_motion_budget = float(
                sum(abs(x) + abs(y) for x, y in zip(all_dx, all_dy)) / max(len(all_dx), 1)
            )
        else:
            global_motion_budget = 0.0

        return MotionEffectManifest(
            video_path=video_path,
            fps=fps,
            total_frames=total_frames,
            effects=effects,
            rhythm_pattern=[round(float(scene.duration), 4) for scene in scenes],
            global_motion_budget=round(global_motion_budget, 6),
        )

    def _extract_global_motion(
        self,
        cap: Any,
        fps: float,
        width: int,
        height: int,
        total_frames: int,
    ) -> Dict[str, List[Any]]:
        dx_norm: List[float] = []
        dy_norm: List[float] = []
        scale_list: List[float] = []
        rotation_list: List[float] = []
        residual_list: List[float] = []
        frame_indices: List[int] = []

        prev_gray: Optional[Any] = None
        prev_pts: Optional[Any] = None
        frame_idx = 0
        inlier_mask: Optional[Any] = None

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % self.sample_every_n_frames != 0:
                frame_idx += 1
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            if prev_gray is None:
                prev_gray = gray
                prev_pts = cv2.goodFeaturesToTrack(
                    gray,
                    maxCorners=self.max_corners,
                    qualityLevel=0.01,
                    minDistance=10,
                    blockSize=5,
                )
                frame_idx += 1
                continue

            if prev_pts is None or len(prev_pts) < 10:
                prev_pts = cv2.goodFeaturesToTrack(
                    prev_gray,
                    maxCorners=self.max_corners,
                    qualityLevel=0.01,
                    minDistance=10,
                    blockSize=5,
                )
                if prev_pts is None:
                    prev_gray = gray
                    frame_idx += 1
                    continue

            curr_pts, status, _ = cv2.calcOpticalFlowPyrLK(prev_gray, gray, prev_pts, None, **self.lk_params)
            if status is None or curr_pts is None:
                prev_gray = gray
                frame_idx += 1
                continue

            good_prev = prev_pts[status.ravel() == 1]
            good_curr = curr_pts[status.ravel() == 1]

            if len(good_prev) < 4:
                dx, dy, scale, angle, residual = self._fallback_transform(good_prev, good_curr)
                dx_norm.append(round(dx / max(width, 1), 6))
                dy_norm.append(round(dy / max(height, 1), 6))
                scale_list.append(round(scale, 6))
                rotation_list.append(round(angle, 4))
                residual_list.append(round(residual, 4))
                frame_indices.append(frame_idx)
                prev_gray = gray
                prev_pts = cv2.goodFeaturesToTrack(
                    gray,
                    maxCorners=self.max_corners,
                    qualityLevel=0.01,
                    minDistance=10,
                    blockSize=5,
                )
                frame_idx += 1
                continue

            transform, inlier_mask, is_homography = self._estimate_transform(good_prev, good_curr)
            if transform is None:
                dx, dy, scale, angle, residual = self._fallback_transform(good_prev, good_curr)
            else:
                dx, dy, scale, angle, residual = self._decompose_transform(
                    transform,
                    good_prev,
                    good_curr,
                    inlier_mask,
                    is_homography=is_homography,
                )
                dx_norm.append(round(dx / max(width, 1), 6))
                dy_norm.append(round(dy / max(height, 1), 6))
                scale_list.append(round(scale, 6))
                rotation_list.append(round(angle, 4))
                residual_list.append(round(residual, 4))
                frame_indices.append(frame_idx)

            if frame_idx % 30 == 0:
                prev_pts = cv2.goodFeaturesToTrack(
                    gray,
                    maxCorners=self.max_corners,
                    qualityLevel=0.01,
                    minDistance=10,
                    blockSize=5,
                )
            else:
                if inlier_mask is not None and len(good_curr) > 0:
                    next_pts = good_curr[inlier_mask.ravel() == 1]
                    prev_pts = next_pts.reshape(-1, 1, 2) if len(next_pts) else curr_pts
                else:
                    prev_pts = curr_pts

            prev_gray = gray
            frame_idx += 1

        return {
            "dx_norm": dx_norm,
            "dy_norm": dy_norm,
            "scale": scale_list,
            "rotation_deg": rotation_list,
            "residual": residual_list,
            "frame_indices": frame_indices,
        }

    def _slice_curve(self, raw_curves: Dict[str, List[Any]], scene: Scene, fps: float) -> Dict[str, List[Any]]:
        start_frame = int(scene.start_time * fps)
        end_frame = int(scene.end_time * fps)
        indices = raw_curves.get("frame_indices", [])
        mask = [i for i, frame_index in enumerate(indices) if start_frame <= frame_index <= end_frame]

        sliced: Dict[str, List[Any]] = {}
        for key in ("dx_norm", "dy_norm", "scale", "rotation_deg", "residual", "frame_indices"):
            values = raw_curves.get(key, [])
            sliced[key] = [values[i] for i in mask if i < len(values)]
        return sliced

    def _classify_shot(
        self,
        shot_index: int,
        curve: Dict[str, List[Any]],
        fps: float,
        scene: Scene,
    ) -> List[MotionEffect]:
        effects: List[MotionEffect] = []
        duration = float(scene.duration)
        if duration <= 0:
            return effects

        dx = curve.get("dx_norm", [])
        dy = curve.get("dy_norm", [])
        sc = curve.get("scale", [])
        res = curve.get("residual", [])
        fidx = curve.get("frame_indices", [])
        if not dx:
            return effects

        motion_mag = [abs(x) + abs(y) for x, y in zip(dx, dy)]
        glitch_frames = [
            i
            for i, value in enumerate(res)
            if value >= _RESIDUAL_GLITCH_MIN and motion_mag[i] > (_FREEZE_MOTION_MAX * 2.0)
        ]
        smear_frames = [
            i
            for i, value in enumerate(res)
            if _RESIDUAL_SMEAR_MIN <= value < _RESIDUAL_GLITCH_MIN and motion_mag[i] > _FREEZE_MOTION_MAX
        ]
        for cluster, effect_type in ((glitch_frames, EffectType.GLITCH), (smear_frames, EffectType.BLUR_SMEAR)):
            for span in self._contiguous_spans(cluster, gap=3):
                onset_frac = self._frame_frac(span[0], fidx, fps, scene)
                offset_frac = self._frame_frac(span[-1], fidx, fps, scene)
                if (offset_frac - onset_frac) * duration < _MIN_EFFECT_DURATION_SEC:
                    continue
                intensity = round(float(np.mean([res[i] for i in span])) / 10.0, 4) if np else 0.5
                effects.append(
                    MotionEffect(
                        shot_index=shot_index,
                        effect_type=effect_type,
                        onset_frac=round(onset_frac, 4),
                        offset_frac=round(offset_frac, 4),
                        intensity=intensity,
                        curve=self._sub_curve(curve, span),
                    )
                )

        freeze_frames = [i for i, value in enumerate(motion_mag) if value <= _FREEZE_MOTION_MAX]
        for span in self._contiguous_spans(freeze_frames, gap=2):
            onset_frac = self._frame_frac(span[0], fidx, fps, scene)
            offset_frac = self._frame_frac(span[-1], fidx, fps, scene)
            if (offset_frac - onset_frac) * duration < _MIN_EFFECT_DURATION_SEC:
                continue
            effects.append(
                MotionEffect(
                    shot_index=shot_index,
                    effect_type=EffectType.FREEZE,
                    onset_frac=round(onset_frac, 4),
                    offset_frac=round(offset_frac, 4),
                    intensity=0.0,
                    curve=self._sub_curve(curve, span),
                )
            )

        shake_frames = self._detect_shake_frames(dx, dy, fps)
        for span in self._contiguous_spans(shake_frames, gap=3):
            onset_frac = self._frame_frac(span[0], fidx, fps, scene)
            offset_frac = self._frame_frac(span[-1], fidx, fps, scene)
            if (offset_frac - onset_frac) * duration < _MIN_EFFECT_DURATION_SEC:
                continue
            sub_dx = [dx[i] for i in span]
            amplitude = float(max(abs(value) for value in sub_dx)) if sub_dx else 0.0
            intensity = min(amplitude / 0.05, 1.0)
            effects.append(
                MotionEffect(
                    shot_index=shot_index,
                    effect_type=EffectType.SHAKE,
                    onset_frac=round(onset_frac, 4),
                    offset_frac=round(offset_frac, 4),
                    intensity=round(intensity, 4),
                    curve=self._sub_curve(curve, span),
                )
            )

        if sc:
            scale_deltas = [sc[i + 1] - sc[i] for i in range(len(sc) - 1)]
            zoom_in_frames = [i for i, delta in enumerate(scale_deltas) if delta > _ZOOM_SCALE_DELTA_MIN]
            zoom_out_frames = [i for i, delta in enumerate(scale_deltas) if delta < -_ZOOM_SCALE_DELTA_MIN]
            for frames, effect_type in ((zoom_in_frames, EffectType.ZOOM_IN), (zoom_out_frames, EffectType.ZOOM_OUT)):
                for span in self._contiguous_spans(frames, gap=5):
                    onset_frac = self._frame_frac(span[0], fidx, fps, scene)
                    offset_frac = self._frame_frac(span[-1], fidx, fps, scene)
                    if (offset_frac - onset_frac) * duration < _MIN_EFFECT_DURATION_SEC:
                        continue
                    total_scale_change = abs(sc[span[-1]] - sc[span[0]]) if span else 0.0
                    effects.append(
                        MotionEffect(
                            shot_index=shot_index,
                            effect_type=effect_type,
                            onset_frac=round(onset_frac, 4),
                            offset_frac=round(offset_frac, 4),
                            intensity=round(min(total_scale_change / 0.3, 1.0), 4),
                            curve=self._sub_curve(curve, span),
                        )
                    )

        if not shake_frames and dx:
            pan_effect = self._detect_pan(shot_index, dx, dy, fidx, fps, scene, duration)
            if pan_effect is not None:
                effects.append(pan_effect)

        if effects and all(effect.effect_type == EffectType.FREEZE for effect in effects):
            total_freeze_coverage = sum(
                max(0.0, effect.offset_frac - effect.onset_frac)
                for effect in effects
            )
            covers_full_shot = total_freeze_coverage >= 0.9 or any(
                effect.onset_frac <= 0.05 and effect.offset_frac >= 0.95
                for effect in effects
            )
            if covers_full_shot:
                effects = []

        if not effects:
            effects.append(
                MotionEffect(
                    shot_index=shot_index,
                    effect_type=EffectType.STATIC,
                    onset_frac=0.0,
                    offset_frac=1.0,
                    intensity=0.0,
                    curve=MotionCurve(
                        dx_norm=list(dx),
                        dy_norm=list(dy),
                        scale=list(sc),
                        rotation_deg=curve.get("rotation_deg", []),
                        residual=list(res),
                        frame_indices=list(fidx),
                    ),
                )
            )
        return effects

    def _detect_shake_frames(self, dx: List[float], dy: List[float], fps: float) -> List[int]:
        if not dx or not np:
            return []

        dx_arr = np.array(dx, dtype=np.float32)
        dy_arr = np.array(dy, dtype=np.float32)
        dx_reversals = np.where(np.diff(np.sign(dx_arr)) != 0)[0]
        duration_sec = len(dx) / max(fps, 1.0)
        reversal_freq = len(dx_reversals) / max(duration_sec, 0.01)
        amplitude = float(np.max(np.abs(dx_arr))) + float(np.max(np.abs(dy_arr)))
        if reversal_freq < _SHAKE_FREQ_MIN_HZ or amplitude < _SHAKE_AMP_MIN_NORM:
            return []

        half_thresh = _SHAKE_AMP_MIN_NORM / 2.0
        return [i for i in range(len(dx)) if abs(dx[i]) > half_thresh or abs(dy[i]) > half_thresh]

    def _detect_pan(
        self,
        shot_index: int,
        dx: List[float],
        dy: List[float],
        fidx: List[int],
        fps: float,
        scene: Scene,
        duration: float,
    ) -> Optional[MotionEffect]:
        del fps, scene, duration
        if not np or len(dx) < 5:
            return None

        dx_arr = np.array(dx, dtype=np.float32)
        dy_arr = np.array(dy, dtype=np.float32)
        mean_dx = float(np.mean(dx_arr))
        mean_dy = float(np.mean(dy_arr))
        total_displacement = abs(mean_dx) + abs(mean_dy)
        if total_displacement < _SHAKE_AMP_MIN_NORM:
            return None

        velocity_variance = float(np.var(dx_arr) + np.var(dy_arr))
        if velocity_variance > _PAN_SMOOTHNESS_MAX:
            return None

        return MotionEffect(
            shot_index=shot_index,
            effect_type=EffectType.PAN,
            onset_frac=0.0,
            offset_frac=1.0,
            intensity=round(min(total_displacement * 20.0, 1.0), 4),
            curve=MotionCurve(
                dx_norm=list(dx),
                dy_norm=list(dy),
                frame_indices=list(fidx),
            ),
        )

    def _frame_frac(self, curve_idx: int, frame_indices: List[int], fps: float, scene: Scene) -> float:
        if not frame_indices or curve_idx >= len(frame_indices):
            return 0.0
        absolute_frame = frame_indices[curve_idx]
        shot_start_frame = scene.start_time * fps
        shot_frame_count = max(scene.duration * fps, 1.0)
        return max(0.0, min(1.0, (absolute_frame - shot_start_frame) / shot_frame_count))

    def _sub_curve(self, curve: Dict[str, List[Any]], indices: List[int]) -> MotionCurve:
        def pick(key: str) -> List[Any]:
            src = curve.get(key, [])
            return [src[i] for i in indices if i < len(src)]

        return MotionCurve(
            dx_norm=pick("dx_norm"),
            dy_norm=pick("dy_norm"),
            scale=pick("scale"),
            rotation_deg=pick("rotation_deg"),
            residual=pick("residual"),
            frame_indices=pick("frame_indices"),
        )

    def _contiguous_spans(self, indices: List[int], gap: int = 2) -> List[List[int]]:
        if not indices:
            return []
        spans: List[List[int]] = []
        current = [indices[0]]
        for value in indices[1:]:
            if value - current[-1] <= gap:
                current.append(value)
            else:
                spans.append(current)
                current = [value]
        spans.append(current)
        return spans

    def _empty_manifest(self, video_path: str) -> MotionEffectManifest:
        return MotionEffectManifest(video_path=video_path, fps=0.0, total_frames=0)

    def _estimate_transform(self, good_prev: Any, good_curr: Any) -> tuple[Any, Any, bool]:
        if len(good_prev) >= 8:
            homography, inlier_mask = cv2.findHomography(good_prev, good_curr, cv2.RANSAC, 3.0)
            if homography is not None:
                return homography, inlier_mask, True

        if len(good_prev) >= 3:
            affine, inlier_mask = cv2.estimateAffinePartial2D(good_prev, good_curr, method=cv2.RANSAC)
            if affine is not None:
                return affine, inlier_mask, False

        return None, None, False

    def _decompose_transform(
        self,
        transform: Any,
        good_prev: Any,
        good_curr: Any,
        inlier_mask: Any,
        *,
        is_homography: bool,
    ) -> tuple[float, float, float, float, float]:
        if is_homography:
            dx = float(transform[0, 2])
            dy = float(transform[1, 2])
            scale_x = float(np.sqrt(transform[0, 0] ** 2 + transform[1, 0] ** 2))
            scale_y = float(np.sqrt(transform[0, 1] ** 2 + transform[1, 1] ** 2))
            scale = float((scale_x + scale_y) / 2.0)
            angle = float(np.degrees(np.arctan2(transform[1, 0], transform[0, 0])))
        else:
            dx = float(transform[0, 2])
            dy = float(transform[1, 2])
            scale = float(np.sqrt(transform[0, 0] ** 2 + transform[1, 0] ** 2))
            angle = float(np.degrees(np.arctan2(transform[1, 0], transform[0, 0])))

        residual = 0.0
        if inlier_mask is not None:
            inliers_prev = good_prev[inlier_mask.ravel() == 1]
            inliers_curr = good_curr[inlier_mask.ravel() == 1]
            if len(inliers_prev) > 0:
                if is_homography:
                    projected = cv2.perspectiveTransform(inliers_prev.reshape(-1, 1, 2), transform).reshape(-1, 2)
                else:
                    projected = cv2.transform(inliers_prev.reshape(-1, 1, 2), transform).reshape(-1, 2)
                residual = float(np.mean(np.linalg.norm(projected - inliers_curr, axis=1)))

        return dx, dy, scale, angle, residual

    def _fallback_transform(self, good_prev: Any, good_curr: Any) -> tuple[float, float, float, float, float]:
        if len(good_prev) == 0 or len(good_curr) == 0 or not np:
            return 0.0, 0.0, 1.0, 0.0, 0.0
        flow = np.asarray(good_curr, dtype=np.float32) - np.asarray(good_prev, dtype=np.float32)
        dx = float(np.median(flow[:, 0]))
        dy = float(np.median(flow[:, 1]))
        residual = float(np.mean(np.linalg.norm(flow - np.array([dx, dy], dtype=np.float32), axis=1)))
        return dx, dy, 1.0, 0.0, residual
