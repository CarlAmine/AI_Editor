import cv2
import numpy as np
import pandas as pd
from scenedetect import VideoManager, SceneManager
from scenedetect.detectors import ContentDetector
from paddleocr import PaddleOCR
import easyocr
import warnings
from datetime import timedelta
from collections import defaultdict
import math
from typing import Dict, Tuple


class VideoEditAnalyzer:
    def __init__(self, path: str):
        self.video_path = path
        self.cap = cv2.VideoCapture(path)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.duration = self.total_frames / self.fps if self.fps > 0 else 0
        self.results: Dict = {}
        self.video_name = path.split("/")[-1]  # Simple basename
        
        # Initialize OCR Engines
        # Note: In a production pipeline, these might be initialized globally to save load time
        # PaddleOCR depends on `paddle`. If it's not installed, we degrade gracefully and
        # rely only on EasyOCR so the rest of the analyzer still works.
        try:
            self.paddle_ocr = PaddleOCR(use_angle_cls=True, lang="en")
        except Exception as e:
            print(f"PaddleOCR initialization failed, continuing without it: {e}")
            self.paddle_ocr = None
        self.easy_reader = easyocr.Reader(["en"], gpu=False, verbose=False)

    def close(self):
        if self.cap.isOpened():
            self.cap.release()

    def detect_scenes(self, threshold: float = 30.0):
        video_manager = VideoManager([self.video_path])
        scene_manager = SceneManager()
        scene_manager.add_detector(ContentDetector(threshold=threshold))
        
        video_manager.start()
        scene_manager.detect_scenes(frame_source=video_manager)
        scene_list = scene_manager.get_scene_list()
        
        scenes_data = []
        for i, scene in enumerate(scene_list):
            start = scene[0].get_seconds()
            end = scene[1].get_seconds()
            scenes_data.append(
                {
                    "scene_id": i + 1,
                    "start_time": start,
                    "end_time": end,
                    "duration": end - start,
                    "start_frame": scene[0].get_frames(),
                    "end_frame": scene[1].get_frames(),
                }
            )
        
        video_manager.release()
        self.results["scenes"] = scenes_data
        return scenes_data

    def analyze_pacing(self):
        if "scenes" not in self.results:
            return
        
        durations = [s["duration"] for s in self.results["scenes"]]
        if not durations:
            return

        avg_duration = np.mean(durations)
        if avg_duration < 2.0:
            category = "Fast (rapid cuts)"
        elif avg_duration < 5.0:
            category = "Medium"
        else:
            category = "Slow (long takes)"

        self.results["pacing"] = {
            "total_shots": len(durations),
            "avg_shot_duration": avg_duration,
            "min_shot_duration": min(durations),
            "max_shot_duration": max(durations),
            "shots_per_minute": len(durations) / (self.duration / 60) if self.duration > 0 else 0,
            "pacing_category": category,
        }

    def detect_black_frames(self, threshold: float = 15):
        black_frames = []
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        frame_count = 0
        consecutive_black = 0
        black_start = None

        while True:
            ret, frame = self.cap.read()
            if not ret:
                break
            
            # Fast grayscale conversion
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
            if np.mean(gray) < threshold:
                if black_start is None:
                    black_start = frame_count / self.fps
                consecutive_black += 1
            else:
                if consecutive_black >= int(self.fps * 0.5):
                    black_end = (frame_count - 1) / self.fps
                    duration = black_end - black_start
                    
                    if consecutive_black > self.fps * 1.5:
                        b_type = "Fade to black"
                    elif consecutive_black > self.fps * 0.8:
                        b_type = "Medium black"
                    else:
                        b_type = "Quick black"
                    
                    black_frames.append(
                        {"start_time": black_start, "duration": duration, "type": b_type}
                    )
                consecutive_black = 0
                black_start = None
            frame_count += 1
        
        self.results["black_frames"] = black_frames

    def detect_transitions(self):
        if "scenes" not in self.results:
            return
        scenes = self.results["scenes"]
        transitions = []
        
        for i in range(len(scenes) - 1):
            gap = scenes[i + 1]["start_time"] - scenes[i]["end_time"]
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
        
        self.results["transitions"] = transitions

    def extract_and_analyze_keyframes(self, num_frames: int = 12):
        keyframes = []
        intervals = max(1, self.total_frames // num_frames)
        
        for i in range(0, self.total_frames, intervals):
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = self.cap.read()
            if not ret:
                break

            # 1. Basic Stats
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            brightness = np.mean(gray)
            
            # 2. PaddleOCR Detection (if available)
            paddle_text = []
            if self.paddle_ocr is not None:
                try:
                    # Paddle expects BGR or RGB. We pass the frame directly.
                    paddle_res = self.paddle_ocr.ocr(frame, cls=True)
                    if paddle_res and paddle_res[0]:
                        paddle_text = [line[1][0] for line in paddle_res[0] if line[1][0]]
                except Exception as e:
                    print(f"PaddleOCR per-frame OCR failed, skipping for this frame: {e}")
            
            # 3. EasyOCR Detection (Detailed)
            # EasyOCR expects the image array
            easy_res = self.easy_reader.readtext(frame)
            easy_details = []
            for bbox, text, conf in easy_res:
                if conf > 0.3:  # Filter low confidence
                    # Determine position
                    h, w = frame.shape[:2]
                    avg_y = sum(p[1] for p in bbox) / 4
                    if avg_y < h / 3:
                        pos = "Top"
                    elif avg_y < 2 * h / 3:
                        pos = "Middle"
                    else:
                        pos = "Bottom"
                    easy_details.append(f"'{text}' ({pos})")

            # Consolidate Text
            detected_text = "; ".join(paddle_text) if paddle_text else "No text"
            if not paddle_text and easy_details:
                detected_text = "; ".join(easy_details)

            keyframes.append(
                {
                    "timestamp": i / self.fps,
                    "frame_number": i,
                    "brightness": brightness,
                    "detected_text": detected_text,
                    "easyocr_details": easy_details,
                }
            )
        
        self.results["keyframes"] = keyframes


def analyze_video_content_with_results(video_path: str) -> Tuple[str, Dict]:
    """
    Run the full analysis and return both the human-readable summary and
    the structured results dictionary (scenes, pacing, keyframes, etc.).
    """
    # Suppress warnings for cleaner pipeline logs
    warnings.filterwarnings("ignore")

    try:
        analyzer = VideoEditAnalyzer(video_path)
        
        # Run Analysis Modules
        analyzer.detect_scenes()
        analyzer.analyze_pacing()
        analyzer.detect_black_frames()
        analyzer.detect_transitions()
        analyzer.extract_and_analyze_keyframes()
        analyzer.close()
        
        # --- Generate Summary Report ---
        res = analyzer.results
        
        # Header
        summary_lines = []
        summary_lines.append(" VIDEO ANALYSIS SUMMARY")
        summary_lines.append("=" * 40)
        summary_lines.append(f"File: {analyzer.video_name}")
        summary_lines.append(f"Duration: {timedelta(seconds=analyzer.duration)}")
        summary_lines.append(f"FPS: {analyzer.fps:.2f}")
        
        # Scene & Pacing
        if "pacing" in res:
            p = res["pacing"]
            summary_lines.append(f"\nPACING: {p['pacing_category']}")
            summary_lines.append(f"   • Total Shots: {p['total_shots']}")
            summary_lines.append(f"   • Avg Shot Duration: {p['avg_shot_duration']:.2f}s")
            summary_lines.append(f"   • Cuts per Minute: {p['shots_per_minute']:.1f}")
        
        # Transitions
        if "transitions" in res:
            t_counts = defaultdict(int)
            for t in res["transitions"]:
                t_counts[t["type"]] += 1
            most_common = max(t_counts, key=t_counts.get) if t_counts else "None"
            summary_lines.append("\nEDITING STYLE:")
            summary_lines.append(f"   • Dominant Transition: {most_common}")
            summary_lines.append(f"   • Transition Counts: {dict(t_counts)}")
            
        # Black Frames
        if "black_frames" in res and res["black_frames"]:
            summary_lines.append(f"\nBLACK SEQUENCES: {len(res['black_frames'])} detected")
            for bf in res["black_frames"][:3]:
                summary_lines.append(
                    f"   • At {bf['start_time']:.1f}s ({bf['duration']:.1f}s): {bf['type']}"
                )
        
        # Text Content (Content Analysis)
        summary_lines.append("\nDETECTED TEXT CONTENT:")
        text_found = False
        if "keyframes" in res:
            for kf in res["keyframes"]:
                if kf["detected_text"] and kf["detected_text"] != "No text":
                    summary_lines.append(
                        f"   • @ {kf['timestamp']:.1f}s: {kf['detected_text']}"
                    )
                    text_found = True
        
        if not text_found:
            summary_lines.append("   • No significant on-screen text detected.")
            
        return "\n".join(summary_lines), res

    except Exception as e:
        error_msg = f"Error analyzing video: {str(e)}"
        return error_msg, {}


def analyze_video_content(video_path: str) -> str:
    """
    Backwards-compatible wrapper that returns only the textual summary.
    """
    summary, _ = analyze_video_content_with_results(video_path)
    return summary
