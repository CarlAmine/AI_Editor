from __future__ import annotations

import logging
from typing import Any, List, Tuple

try:
    import cv2
    import numpy as np

    _CV2_AVAILABLE = True
except Exception:  # pragma: no cover - dependency availability varies by environment
    cv2 = None  # type: ignore
    np = None  # type: ignore
    _CV2_AVAILABLE = False

from ai_editor.analysis.analysis_schema import EffectType, MotionCurve, MotionEffect, MotionEffectManifest

log = logging.getLogger(__name__)

MAX_TRANSITION_DURATION_SEC = 0.25


class MotionEffectApplier:
    """
    Applies a MotionEffectManifest extracted from a reference video onto
    replacement clips, reproducing editing motion effects without using
    any content understanding.
    """

    def apply_to_clip(
        self,
        clip_path: str,
        shot_index: int,
        manifest: MotionEffectManifest,
        output_path: str,
        fourcc: str = "mp4v",
    ) -> str:
        if not _CV2_AVAILABLE:
            log.warning("cv2 not available; returning original clip unchanged")
            return clip_path

        shot_effects = [effect for effect in manifest.effects if effect.shot_index == shot_index]
        active_effects = [effect for effect in shot_effects if effect.effect_type != EffectType.STATIC]
        if not active_effects:
            log.debug("No active effects for shot %d; returning original clip", shot_index)
            return clip_path

        cap = cv2.VideoCapture(clip_path)
        if not cap.isOpened():
            log.error("Cannot open clip: %s", clip_path)
            return clip_path

        fps = float(cap.get(cv2.CAP_PROP_FPS)) or 25.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        writer = cv2.VideoWriter(output_path, cv2.VideoWriter_fourcc(*fourcc), fps, (width, height))
        clip_duration_sec = n_frames / max(fps, 1.0)
        for effect in active_effects:
            effect.metadata["clip_duration_sec"] = clip_duration_sec

        frozen_frame = None
        try:
            frame_idx = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                frac = frame_idx / max(n_frames - 1, 1)
                frame, frozen_frame = self._apply_frame_effects(
                    frame,
                    frac,
                    active_effects,
                    width,
                    height,
                    frozen_frame=frozen_frame,
                )
                writer.write(frame)
                frame_idx += 1
        finally:
            cap.release()
            writer.release()

        log.info("Applied %d effects to shot %d -> %s", len(active_effects), shot_index, output_path)
        return output_path

    def _apply_frame_effects(
        self,
        frame: Any,
        frac: float,
        effects: List[MotionEffect],
        width: int,
        height: int,
        *,
        frozen_frame: Any = None,
    ) -> Tuple[Any, Any]:
        result = frame.copy()
        current_frozen = frozen_frame
        freeze_active = False

        for effect in effects:
            if not (effect.onset_frac <= frac <= effect.offset_frac):
                continue

            window_frac = frac - effect.onset_frac
            window_duration = max(effect.offset_frac - effect.onset_frac, 1e-6)
            local_frac = window_frac / window_duration

            if effect.effect_type == EffectType.FREEZE:
                freeze_active = True
                if current_frozen is None:
                    current_frozen = result.copy()
                result = current_frozen.copy()
                continue

            if effect.effect_type == EffectType.SHAKE:
                result = self._apply_shake(result, local_frac, effect, width, height)
            elif effect.effect_type in (EffectType.ZOOM_IN, EffectType.ZOOM_OUT):
                result = self._apply_zoom(result, local_frac, effect, width, height)
            elif effect.effect_type == EffectType.PAN:
                result = self._apply_pan(result, local_frac, effect, width, height)
            elif effect.effect_type in (EffectType.BLUR_SMEAR, EffectType.GLITCH):
                if effect.intensity <= 2.0:
                    result = self._apply_blur_smear(result, effect)

        if not freeze_active:
            current_frozen = None
        return result, current_frozen

    def _apply_shake(self, frame: Any, local_frac: float, effect: MotionEffect, width: int, height: int) -> Any:
        dx_list = effect.curve.dx_norm
        dy_list = effect.curve.dy_norm
        if not dx_list:
            return frame

        curve_frame_count = int(effect.metadata.get("curve_frame_count", len(dx_list)))
        ref_fps = float(effect.metadata.get("reference_fps", 25.0))
        window_duration = max(effect.offset_frac - effect.onset_frac, 1e-6)
        clip_duration = float(effect.metadata.get("clip_duration_sec", window_duration))
        effect_duration_sec = window_duration * clip_duration
        elapsed_sec = local_frac * effect_duration_sec
        curve_frame_idx = int(elapsed_sec * ref_fps)
        if curve_frame_idx >= curve_frame_count or curve_frame_idx >= len(dx_list):
            return frame

        dx_norm = dx_list[min(curve_frame_idx, len(dx_list) - 1)]
        dy_norm = dy_list[min(curve_frame_idx, len(dy_list) - 1)] if dy_list else 0.0
        dx_px = dx_norm * width
        dy_px = dy_norm * height
        dx_px = max(-width * 0.05, min(width * 0.05, dx_px))
        dy_px = max(-height * 0.05, min(height * 0.05, dy_px))
        matrix = np.float32([[1, 0, dx_px], [0, 1, dy_px]])
        return cv2.warpAffine(frame, matrix, (width, height), borderMode=cv2.BORDER_REFLECT)

    def _apply_zoom(self, frame: Any, local_frac: float, effect: MotionEffect, width: int, height: int) -> Any:
        if effect.curve.scale:
            idx = int(local_frac * max(len(effect.curve.scale) - 1, 0))
            scale = float(effect.curve.scale[min(idx, len(effect.curve.scale) - 1)])
        else:
            if effect.effect_type == EffectType.ZOOM_IN:
                scale = 1.0 + local_frac * 0.15 * effect.intensity
            else:
                scale = 1.15 - local_frac * 0.15 * effect.intensity

        cx, cy = width / 2.0, height / 2.0
        matrix = cv2.getRotationMatrix2D((cx, cy), 0.0, scale)
        return cv2.warpAffine(frame, matrix, (width, height), borderMode=cv2.BORDER_REFLECT)

    def _apply_pan(self, frame: Any, local_frac: float, effect: MotionEffect, width: int, height: int) -> Any:
        if effect.curve.dx_norm and np:
            mean_dx = float(np.mean(effect.curve.dx_norm)) * width
            mean_dy = float(np.mean(effect.curve.dy_norm)) * height if effect.curve.dy_norm else 0.0
        else:
            mean_dx = 0.0
            mean_dy = 0.0
        dx_px = mean_dx * local_frac * effect.intensity
        dy_px = mean_dy * local_frac * effect.intensity
        matrix = np.float32([[1, 0, dx_px], [0, 1, dy_px]])
        return cv2.warpAffine(frame, matrix, (width, height), borderMode=cv2.BORDER_REFLECT)

    def _apply_blur_smear(self, frame: Any, effect: MotionEffect) -> Any:
        if not np:
            return frame
        dx = float(np.mean(effect.curve.dx_norm)) if effect.curve.dx_norm else 0.0
        dy = float(np.mean(effect.curve.dy_norm)) if effect.curve.dy_norm else 0.0
        capped_intensity = min(effect.intensity, 1.0)
        size = max(int(capped_intensity * 15), 3) | 1
        kernel = np.zeros((size, size), dtype=np.float32)
        if abs(dx) >= abs(dy):
            kernel[size // 2, :] = 1.0 / size
        else:
            kernel[:, size // 2] = 1.0 / size
        return cv2.filter2D(frame, -1, kernel)

    def _sample_curve(self, curve: MotionCurve, local_frac: float, width: int, height: int) -> Tuple[float, float]:
        dx_list = curve.dx_norm
        dy_list = curve.dy_norm
        if not dx_list:
            return 0.0, 0.0

        idx_float = local_frac * (len(dx_list) - 1)
        idx_lo = int(idx_float)
        idx_hi = min(idx_lo + 1, len(dx_list) - 1)
        t = idx_float - idx_lo
        dx_norm = dx_list[idx_lo] * (1 - t) + dx_list[idx_hi] * t
        dy_norm = (dy_list[idx_lo] * (1 - t) + dy_list[idx_hi] * t) if dy_list else 0.0
        return dx_norm * width, dy_norm * height

    def apply_transition_to_clip(
        self,
        clip_path: str,
        transition: Any,
        output_path: str,
        position: str = "end",
        fourcc: str = "mp4v",
    ) -> str:
        from ai_editor.analysis.analysis_schema import TransitionType

        del position
        transition_type = transition.transition_type
        n_frames = max(1, int(transition.duration_frames or 1))

        if transition_type in (
            TransitionType.HARD_CUT,
            TransitionType.CROSS_DISSOLVE,
            TransitionType.ZOOM_PUNCH,
            TransitionType.UNKNOWN,
        ):
            return clip_path
        if not _CV2_AVAILABLE:
            return clip_path

        cap = cv2.VideoCapture(clip_path)
        if not cap.isOpened():
            return clip_path

        fps = float(cap.get(cv2.CAP_PROP_FPS)) or 25.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        frames = []
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame)
        cap.release()

        if not frames:
            return clip_path

        clip_duration_sec = len(frames) / max(fps, 1.0)
        max_transition_frames = max(
            1,
            int(min(MAX_TRANSITION_DURATION_SEC * fps, len(frames) * 0.5)),
        )
        if n_frames > max_transition_frames:
            log.warning(
                "Clamping transition frames from %s to %s (clip %.2fs)",
                n_frames,
                max_transition_frames,
                clip_duration_sec,
            )
            n_frames = max_transition_frames

        if transition_type in (TransitionType.FADE_TO_BLACK, TransitionType.FADE_TO_WHITE):
            target = 0 if transition_type == TransitionType.FADE_TO_BLACK else 255
            for index in range(min(n_frames, len(frames))):
                frame_index = len(frames) - n_frames + index
                if frame_index < 0:
                    continue
                alpha = index / max(n_frames - 1, 1)
                frames[frame_index] = cv2.addWeighted(
                    frames[frame_index],
                    1.0 - alpha,
                    np.full_like(frames[frame_index], target),
                    alpha,
                    0,
                )
        elif transition_type in (TransitionType.FADE_FROM_BLACK, TransitionType.FADE_FROM_WHITE):
            source = 0 if transition_type == TransitionType.FADE_FROM_BLACK else 255
            for index in range(min(n_frames, len(frames))):
                alpha = index / max(n_frames - 1, 1)
                frames[index] = cv2.addWeighted(
                    frames[index],
                    alpha,
                    np.full_like(frames[index], source),
                    1.0 - alpha,
                    0,
                )
        elif transition_type == TransitionType.WHIP_PAN:
            blur_size = max(int(transition.intensity * 31), 3) | 1
            kernel = np.zeros((blur_size, blur_size), dtype=np.float32)
            kernel[blur_size // 2, :] = 1.0 / blur_size
            for index in range(min(n_frames, len(frames))):
                frame_index = len(frames) - n_frames + index
                if frame_index >= 0:
                    frames[frame_index] = cv2.filter2D(frames[frame_index], -1, kernel)
        elif transition_type == TransitionType.FLASH_CUT:
            frames[-1] = np.full_like(frames[-1], 255)

        writer = cv2.VideoWriter(output_path, cv2.VideoWriter_fourcc(*fourcc), fps, (width, height))
        for frame in frames:
            writer.write(frame)
        writer.release()
        return output_path
