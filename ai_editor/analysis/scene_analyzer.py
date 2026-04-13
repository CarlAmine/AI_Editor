from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

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
        transitions = self.detect_transitions(scenes)
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

    def detect_transitions(self, scenes: List[Scene]) -> List[Dict[str, Any]]:
        transitions: List[Dict[str, Any]] = []
        for index in range(len(scenes) - 1):
            gap = scenes[index + 1].start_time - scenes[index].end_time
            if gap < 0.05:
                t_type = "Hard Cut"
            elif gap < 0.2:
                t_type = "Quick Fade"
            elif gap < 0.8:
                t_type = "Standard Dissolve"
            elif gap < 2.0:
                t_type = "Long Fade"
            else:
                t_type = "Pause/Gap"
            transitions.append({"type": t_type, "gap": gap})
        return transitions
