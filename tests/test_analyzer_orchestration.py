import builtins

import ai_editor.analyzer as analyzer_module
from ai_editor.analysis.analysis_schema import AnalysisStatus, OCRSpan, Scene, TranscriptResult


class _FakeCapture:
    def __init__(self, path: str):
        self.path = path
        self.opened = True

    def get(self, prop: int):
        mapping = {
            analyzer_module.cv2.CAP_PROP_FPS: 24.0,
            analyzer_module.cv2.CAP_PROP_FRAME_COUNT: 240.0,
            analyzer_module.cv2.CAP_PROP_FRAME_WIDTH: 1280.0,
            analyzer_module.cv2.CAP_PROP_FRAME_HEIGHT: 720.0,
        }
        return mapping.get(prop, 0.0)

    def isOpened(self):
        return self.opened

    def release(self):
        self.opened = False


class _FakeSceneAnalyzer:
    def analyze(self, video_path, metadata):
        return type(
            "SceneOutput",
            (),
            {
                "scenes": [
                    Scene(
                        scene_id=1,
                        start_time=0.0,
                        end_time=10.0,
                        duration=10.0,
                        start_frame=0,
                        end_frame=240,
                    )
                ],
                "pacing": {
                    "total_shots": 1,
                    "avg_shot_duration": 10.0,
                    "min_shot_duration": 10.0,
                    "max_shot_duration": 10.0,
                    "shots_per_minute": 6.0,
                    "pacing_category": "Slow (long takes)",
                },
                "black_frames": [],
                "transitions": [],
            },
        )()

    def detect_scenes(self, video_path, threshold=30.0):
        return self.analyze(video_path, None).scenes

    def analyze_pacing(self, scenes, duration_seconds):
        return self.analyze("", None).pacing

    def detect_black_frames(self, video_path, fps, threshold=15):
        return []

    def detect_transitions(self, scenes):
        return []


class _FakeOCRAnalyzer:
    def analyze(self, video_path, metadata, num_frames=12):
        return type(
            "OCROutput",
            (),
            {
                "keyframes": [
                    {
                        "timestamp": 0.0,
                        "frame_number": 0,
                        "brightness": 100.0,
                        "contrast": 24.0,
                        "detected_text": "TOP 10",
                        "easyocr_details": ["TOP 10"],
                        "visual_signature": {
                            "sample_count": 1,
                            "brightness": 100.0,
                            "contrast": 24.0,
                            "edge_density": 0.12,
                            "mean_bgr": [110.0, 90.0, 80.0],
                            "color_histogram": [0.08] * 12,
                            "ahash": "1010" * 16,
                            "dominant_channel": "blue",
                        },
                    }
                ],
                "ocr_spans": [
                    OCRSpan(timestamp=0.0, frame_number=0, text="TOP 10", source="easyocr")
                ],
            },
        )()


class _FakeTranscriptAnalyzer:
    def analyze(self, video_path):
        return TranscriptResult(
            status=AnalysisStatus.UNAVAILABLE.value,
            backend=None,
            reason="No transcript backend installed.",
            spans=[],
        )


def test_video_edit_analyzer_orchestrates_sub_analyzers(monkeypatch):
    monkeypatch.setattr(analyzer_module.cv2, "VideoCapture", _FakeCapture)

    analyzer = analyzer_module.VideoEditAnalyzer(
        "demo.mp4",
        scene_analyzer=_FakeSceneAnalyzer(),
        ocr_analyzer=_FakeOCRAnalyzer(),
        transcript_analyzer=_FakeTranscriptAnalyzer(),
    )

    context = analyzer.run_full_analysis()
    payload = context.result.to_dict(include_legacy=True)
    payload["keyframes"] = context.keyframes

    assert payload["video_metadata"]["duration_seconds"] == 10.0
    assert payload["scenes"][0]["scene_id"] == 1
    assert payload["keyframes"][0]["detected_text"] == "TOP 10"
    assert payload["transcript"]["status"] == "unavailable"
    assert payload["segments"][0]["label"] == "scene_1"
    assert payload["segments"][0]["editorial_score"] >= 0.0
    assert payload["segments"][0]["novelty_score"] >= 0.0
    assert "visual_signature" in payload["segments"][0]
    assert payload["style_profile"]["scene_count"] == 1
    assert "pacing_label" in payload["style_profile"]
    assert "motion_effects" in payload


def test_transcript_analyzer_falls_back_gracefully(monkeypatch):
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name in {"faster_whisper", "whisper"}:
            raise ImportError(name)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    result = analyzer_module.TranscriptAnalyzer().analyze("demo.mp4")

    assert result.status == "unavailable"
    assert result.spans == []
    assert "No transcript backend installed" in (result.reason or "")
