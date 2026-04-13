from ai_editor.analysis.analysis_schema import (
    AnalysisResult,
    OCRSpan,
    Scene,
    Segment,
    StyleProfile,
    TranscriptResult,
    TranscriptSpan,
    VideoMetadata,
)


def test_analysis_schema_emits_canonical_and_legacy_shapes():
    result = AnalysisResult(
        metadata=VideoMetadata(
            path="sample.mp4",
            name="sample.mp4",
            fps=30.0,
            total_frames=300,
            duration_seconds=10.0,
            width=1920,
            height=1080,
        ),
        scenes=[
            Scene(
                scene_id=1,
                start_time=0.0,
                end_time=10.0,
                duration=10.0,
                start_frame=0,
                end_frame=300,
            )
        ],
        ocr_spans=[
            OCRSpan(timestamp=0.0, frame_number=0, text="TOP 10", source="easyocr"),
            OCRSpan(timestamp=0.0, frame_number=0, text="JAPAN", source="easyocr"),
            OCRSpan(timestamp=5.0, frame_number=150, text="NORWAY", source="paddleocr"),
        ],
        transcript=TranscriptResult(
            status="empty",
            backend="stub",
            reason="not configured",
            spans=[TranscriptSpan(start_time=0.0, end_time=1.0, text="hello")],
        ),
        segments=[
            Segment(
                start=0.0,
                end=10.0,
                label="full_video",
                editorial_score=0.55,
                novelty_score=0.41,
                visual_cluster_id="cluster_1",
                visual_signature={"brightness": 120.0, "edge_density": 0.15},
            )
        ],
        pacing={"pacing_category": "Medium"},
        style_profile=StyleProfile(avg_shot_length=3.4, scene_count=3, pacing_label="medium"),
    )

    payload = result.to_dict(include_legacy=True)

    assert payload["video_metadata"]["name"] == "sample.mp4"
    assert len(payload["ocr_spans"]) == 3
    assert payload["transcript"]["status"] == "empty"
    assert payload["transcript_spans"][0]["text"] == "hello"
    assert payload["segments"][0]["end_time"] == 10.0
    assert payload["segments"][0]["start"] == 0.0
    assert payload["segments"][0]["score"] == 0.55
    assert payload["segments"][0]["novelty_score"] == 0.41
    assert payload["segments"][0]["visual_cluster_id"] == "cluster_1"
    assert payload["segments"][0]["visual_signature"]["brightness"] == 120.0
    assert payload["style_profile"]["avg_shot_length"] == 3.4
    assert payload["scenes"][0]["start_time"] == 0.0
    assert len(payload["keyframes"]) == 2
    assert payload["keyframes"][0]["detected_text"] == "TOP 10; JAPAN"
