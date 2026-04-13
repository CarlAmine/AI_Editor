from ai_editor.analysis.analysis_schema import OCRSpan, Scene, TranscriptResult, TranscriptSpan, VideoMetadata
from ai_editor.analysis.segment_builder import SegmentBuilder


def test_segment_builder_prefers_transcript_and_clips_to_scene_boundaries():
    builder = SegmentBuilder()
    metadata = VideoMetadata(path="demo.mp4", name="demo.mp4", duration_seconds=12.0)
    scenes = [
        Scene(scene_id=1, start_time=0.0, end_time=5.0, duration=5.0, start_frame=0, end_frame=150),
        Scene(scene_id=2, start_time=5.0, end_time=10.0, duration=5.0, start_frame=151, end_frame=300),
    ]
    transcript = TranscriptResult(
        status="available",
        backend="stub",
        reason=None,
        spans=[
            TranscriptSpan(start_time=1.0, end_time=6.0, text="Opening narration"),
            TranscriptSpan(start_time=6.0, end_time=9.0, text="Second beat"),
        ],
    )
    ocr_spans = [
        OCRSpan(timestamp=2.0, frame_number=60, text="TOP 10"),
        OCRSpan(timestamp=6.5, frame_number=195, text="JAPAN"),
    ]

    result = builder.build(metadata=metadata, scenes=scenes, transcript=transcript, ocr_spans=ocr_spans)

    assert result.strategy == "transcript_scene_aligned"
    assert len(result.segments) == 3
    assert result.segments[0].start == 1.0
    assert result.segments[0].end == 5.0
    assert result.segments[0].scene_id == 1
    assert result.segments[0].has_transcript is True
    assert "Opening narration" in result.segments[0].transcript_text
    assert result.segments[1].start == 5.0
    assert result.segments[1].end == 6.0
    assert result.segments[1].scene_id == 2


def test_segment_builder_falls_back_to_scene_segments_without_transcript():
    builder = SegmentBuilder()
    metadata = VideoMetadata(path="demo.mp4", name="demo.mp4", duration_seconds=8.0)
    scenes = [
        Scene(scene_id=1, start_time=0.0, end_time=3.0, duration=3.0, start_frame=0, end_frame=90),
        Scene(scene_id=2, start_time=3.0, end_time=8.0, duration=5.0, start_frame=91, end_frame=240),
    ]
    transcript = TranscriptResult(status="unavailable", backend=None, reason="missing", spans=[])
    ocr_spans = [OCRSpan(timestamp=1.0, frame_number=30, text="HELLO")]

    result = builder.build(metadata=metadata, scenes=scenes, transcript=transcript, ocr_spans=ocr_spans)

    assert result.strategy == "scene_fallback"
    assert len(result.segments) == 2
    assert result.segments[0].scene_id == 1
    assert result.segments[0].has_transcript is False
    assert result.segments[0].has_ocr is True
    assert result.segments[1].start == 3.0
    assert result.segments[1].end == 8.0

