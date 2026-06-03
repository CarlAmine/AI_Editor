from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

try:
    import cv2
except Exception:  # pragma: no cover - dependency availability varies by environment
    cv2 = None  # type: ignore

try:
    import numpy as np
except Exception:  # pragma: no cover - dependency availability varies by environment
    np = None  # type: ignore

from .analysis_schema import Scene, VideoMetadata

try:
    from scenedetect import SceneManager, VideoManager
    from scenedetect.detectors import ContentDetector
except Exception:  # pragma: no cover - dependency availability varies by environment
    SceneManager = None
    VideoManager = None
    ContentDetector = None


@dataclass
class SceneAnalysisOutput:
    scenes: List[Scene]
    pacing: Dict[str, Any]
    black_frames: List[Dict[str, Any]]
    transitions: List[Dict[str, Any]]


class SceneAnalyzer:
    """Scene-oriented analysis with backward-compatible pacing metadata."""

    def analyze(self, video_path: str, metadata: VideoMetadata, threshold: float = 30.0) -> SceneAnalysisOutput:
        scenes = self.detect_scenes(video_path, threshold=threshold)
        pacing = self.analyze_pacing(scenes, metadata.duration_seconds)
        black_frames = self.detect_black_frames(video_path, metadata.fps)
        transitions = self.detect_transitions(scenes, video_path)
        return SceneAnalysisOutput(
            scenes=scenes,
            pacing=pacing,
            black_frames=black_frames,
            transitions=transitions,
        )

    def detect_scenes(self, video_path: str, threshold: float = 30.0) -> List[Scene]:
        if VideoManager is None or SceneManager is None or ContentDetector is None:
            return []
        video_manager = VideoManager([video_path])
        scene_manager = SceneManager()
        scene_manager.add_detector(ContentDetector(threshold=threshold))

        video_manager.start()
        scene_manager.detect_scenes(frame_source=video_manager)
        scene_list = scene_manager.get_scene_list()
        video_manager.release()

        scenes: List[Scene] = []
        for index, scene in enumerate(scene_list, start=1):
            start = scene[0].get_seconds()
            end = scene[1].get_seconds()
            scenes.append(
                Scene(
                    scene_id=index,
                    start_time=start,
                    end_time=end,
                    duration=end - start,
                    start_frame=scene[0].get_frames(),
                    end_frame=scene[1].get_frames(),
                )
            )
        return scenes

    def analyze_pacing(self, scenes: List[Scene], duration_seconds: float) -> Dict[str, Any]:
        if np is None:
            return {}
        durations = [scene.duration for scene in scenes if scene.duration > 0]
        if not durations:
            return {}

        avg_duration = float(np.mean(durations))
        if avg_duration < 2.0:
            category = "Fast (rapid cuts)"
        elif avg_duration < 5.0:
            category = "Medium"
        else:
            category = "Slow (long takes)"

        return {
            "total_shots": len(durations),
            "avg_shot_duration": avg_duration,
            "min_shot_duration": min(durations),
            "max_shot_duration": max(durations),
            "shots_per_minute": len(durations) / (duration_seconds / 60) if duration_seconds > 0 else 0,
            "pacing_category": category,
        }

    def detect_black_frames(self, video_path: str, fps: float, threshold: float = 15) -> List[Dict[str, Any]]:
        if cv2 is None or np is None or fps <= 0:
            return []
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return []
        black_frames: List[Dict[str, Any]] = []
        frame_count = 0
        consecutive_black = 0
        black_start = None
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
                if float(np.mean(gray)) < threshold:
                    if black_start is None:
                        black_start = frame_count / fps
                    consecutive_black += 1
                else:
                    if consecutive_black >= int(fps * 0.5):
                        black_end = (frame_count - 1) / fps
                        duration = black_end - float(black_start or 0.0)
                        if consecutive_black > fps * 1.5:
                            b_type = "Fade to black"
                        elif consecutive_black > fps * 0.8:
                            b_type = "Medium black"
                        else:
                            b_type = "Quick black"
                        black_frames.append(
                            {
                                "start_time": float(black_start or 0.0),
                                "duration": duration,
                                "type": b_type,
                            }
                        )
                    consecutive_black = 0
                    black_start = None
                frame_count += 1
        finally:
            cap.release()
        return black_frames

    def detect_transitions(self, scenes: List[Scene], video_path: str = "") -> List[Dict[str, Any]]:
        transitions: List[Dict[str, Any]] = []

        def _gap_label(gap: float) -> str:
            if gap < 0.05:
                return "Hard Cut"
            if gap < 0.2:
                return "Quick Fade"
            if gap < 0.8:
                return "Standard Dissolve"
            if gap < 2.0:
                return "Long Fade"
            return "Pause/Gap"

        def _histogram_for_frame(frame):
            if frame is None:
                return None
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
            hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
            if hist is None:
                return None
            cv2.normalize(hist, hist)
            return hist

        def _compare_hist(hist_a, hist_b) -> Optional[float]:
            if hist_a is None or hist_b is None:
                return None
            try:
                return float(cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_CORREL))
            except Exception:
                return None

        if cv2 is None or np is None or not scenes:
            for index in range(len(scenes) - 1):
                gap = scenes[index + 1].start_time - scenes[index].end_time
                transitions.append({"type": _gap_label(gap), "gap": gap, "correlation": None})
            return transitions

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            log.warning("Scene transition analysis fallback: unable to open video %s", video_path)
            for index in range(len(scenes) - 1):
                gap = scenes[index + 1].start_time - scenes[index].end_time
                transitions.append({"type": _gap_label(gap), "gap": gap, "correlation": None})
            return transitions

        try:
            for index in range(len(scenes) - 1):
                current = scenes[index]
                next_scene = scenes[index + 1]
                gap = next_scene.start_time - current.end_time
                correlation: Optional[float] = None
                transition_type: str = "Fade" if gap > 1.0 else _gap_label(gap)

                if gap <= 1.0:
                    last_frame_index = int(round(current.end_frame))
                    first_frame_index = int(round(next_scene.start_frame))

                    def _clamp(index: int, minimum: int, maximum: int) -> int:
                        return max(minimum, min(index, maximum))

                    last_indices = [
                        _clamp(last_frame_index - 2, current.start_frame, current.end_frame),
                        _clamp(last_frame_index - 1, current.start_frame, current.end_frame),
                        _clamp(last_frame_index, current.start_frame, current.end_frame),
                    ]
                    next_indices = [
                        _clamp(first_frame_index, next_scene.start_frame, next_scene.end_frame),
                        _clamp(first_frame_index + 1, next_scene.start_frame, next_scene.end_frame),
                        _clamp(first_frame_index + 2, next_scene.start_frame, next_scene.end_frame),
                    ]

                    last_frames = []
                    for frame_index in sorted(set(last_indices)):
                        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                        ret, frame = cap.read()
                        if not ret or frame is None:
                            last_frames = []
                            break
                        last_frames.append(frame)

                    next_frames = []
                    for frame_index in sorted(set(next_indices)):
                        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                        ret, frame = cap.read()
                        if not ret or frame is None:
                            next_frames = []
                            break
                        next_frames.append(frame)

                    if last_frames and next_frames:
                        last_hist = _histogram_for_frame(last_frames[-1])
                        next_hist = _histogram_for_frame(next_frames[0])
                        correlation = _compare_hist(last_hist, next_hist)
                        if correlation is None:
                            transition_type = _gap_label(gap)
                        elif correlation < 0.6:
                            transition_type = "Hard Cut"
                        elif correlation > 0.85:
                            transition_type = "Soft Cut"
                        else:
                            sequence: List[float] = []
                            for prev_frame, next_frame in zip(last_frames, next_frames):
                                prev_hist = _histogram_for_frame(prev_frame)
                                next_hist = _histogram_for_frame(next_frame)
                                corr_value = _compare_hist(prev_hist, next_hist)
                                if corr_value is None:
                                    sequence = []
                                    break
                                sequence.append(corr_value)
                            if len(sequence) >= 2 and all(sequence[i] >= sequence[i - 1] for i in range(1, len(sequence))):
                                transition_type = "Dissolve"
                            else:
                                transition_type = "Wipe or Match Cut"
                    else:
                        log.warning(
                            "Scene transition frame sampling failed for scenes %d-%d: falling back to gap heuristic",
                            current.scene_id,
                            next_scene.scene_id,
                        )
                        transition_type = _gap_label(gap)
                        correlation = None

                transitions.append({"type": transition_type, "gap": gap, "correlation": correlation})
        finally:
            cap.release()
        return transitions
