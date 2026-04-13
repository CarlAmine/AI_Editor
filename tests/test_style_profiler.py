from ai_editor.analysis.analysis_schema import OCRSpan, Scene, Segment, TranscriptSpan, VideoMetadata
from ai_editor.analysis.style_profiler import StyleProfiler


def test_style_profile_generation_from_typical_inputs():
    profiler = StyleProfiler()
    metadata = VideoMetadata(path="demo.mp4", name="demo.mp4", duration_seconds=30.0)
    scenes = [
        Scene(scene_id=1, start_time=0.0, end_time=3.0, duration=3.0, start_frame=0, end_frame=90),
        Scene(scene_id=2, start_time=3.0, end_time=6.0, duration=3.0, start_frame=91, end_frame=180),
        Scene(scene_id=3, start_time=6.0, end_time=12.0, duration=6.0, start_frame=181, end_frame=360),
    ]
    ocr_spans = [
        OCRSpan(timestamp=0.5, frame_number=15, text="TOP 10"),
        OCRSpan(timestamp=1.5, frame_number=45, text="JAPAN"),
        OCRSpan(timestamp=8.0, frame_number=240, text="NORWAY"),
    ]
    transcript_spans = [
        TranscriptSpan(start_time=0.0, end_time=2.0, text="Fast intro"),
        TranscriptSpan(start_time=4.0, end_time=8.0, text="Some explanation in the middle"),
    ]
    segments = [
        Segment(start=0.0, end=2.0, editorial_score=0.78, hook_score=0.88, has_transcript=True, has_ocr=True),
        Segment(start=4.0, end=8.0, editorial_score=0.51, hook_score=0.32, has_transcript=True, has_ocr=False),
    ]

    profile = profiler.profile(
        metadata=metadata,
        scenes=scenes,
        ocr_spans=ocr_spans,
        transcript_spans=transcript_spans,
        segments=segments,
        pacing={"pacing_category": "Medium"},
        transitions=[{"type": "Hard Cut"}, {"type": "Quick Fade"}],
        keyframes=[{"timestamp": 0.5}, {"timestamp": 1.5}],
    )

    assert profile.scene_count == 3
    assert profile.avg_shot_length == 4.0
    assert profile.transition_density > 0.0
    assert profile.hook_window_seconds >= 2.0
    assert profile.pacing_label == "Medium"
    assert profile.metadata["segment_count"] == 2


def test_style_profiler_distinguishes_fast_and_slow_pacing():
    profiler = StyleProfiler()
    metadata = VideoMetadata(path="demo.mp4", name="demo.mp4", duration_seconds=30.0)

    fast_profile = profiler.profile(
        metadata=metadata,
        scenes=[
            Scene(scene_id=1, start_time=0.0, end_time=1.0, duration=1.0, start_frame=0, end_frame=30),
            Scene(scene_id=2, start_time=1.0, end_time=2.0, duration=1.0, start_frame=31, end_frame=60),
            Scene(scene_id=3, start_time=2.0, end_time=3.0, duration=1.0, start_frame=61, end_frame=90),
        ],
        ocr_spans=[],
        transcript_spans=[],
        segments=[Segment(start=0.0, end=1.5, editorial_score=0.8, hook_score=0.8)],
        pacing={},
        transitions=[],
        keyframes=[],
    )
    slow_profile = profiler.profile(
        metadata=metadata,
        scenes=[
            Scene(scene_id=1, start_time=0.0, end_time=10.0, duration=10.0, start_frame=0, end_frame=300),
            Scene(scene_id=2, start_time=10.0, end_time=20.0, duration=10.0, start_frame=301, end_frame=600),
        ],
        ocr_spans=[],
        transcript_spans=[],
        segments=[Segment(start=0.0, end=8.0, editorial_score=0.4, hook_score=0.2)],
        pacing={},
        transitions=[],
        keyframes=[],
    )

    assert fast_profile.intro_pacing_label == "fast"
    assert slow_profile.intro_pacing_label == "slow"
    assert fast_profile.short_form_likelihood > slow_profile.short_form_likelihood


def test_style_profiler_reflects_text_heavy_vs_text_light():
    profiler = StyleProfiler()
    metadata = VideoMetadata(path="demo.mp4", name="demo.mp4", duration_seconds=20.0)
    scenes = [Scene(scene_id=1, start_time=0.0, end_time=5.0, duration=5.0, start_frame=0, end_frame=150)]

    text_heavy = profiler.profile(
        metadata=metadata,
        scenes=scenes,
        ocr_spans=[
            OCRSpan(timestamp=0.2, frame_number=6, text="TOP"),
            OCRSpan(timestamp=0.8, frame_number=24, text="10"),
            OCRSpan(timestamp=1.2, frame_number=36, text="JAPAN"),
            OCRSpan(timestamp=1.8, frame_number=54, text="NORWAY"),
        ],
        transcript_spans=[TranscriptSpan(start_time=0.0, end_time=3.0, text="many words here for narration")],
        segments=[Segment(start=0.0, end=3.0, editorial_score=0.7, hook_score=0.7, has_ocr=True)],
        pacing={},
        transitions=[],
        keyframes=[],
    )
    text_light = profiler.profile(
        metadata=metadata,
        scenes=scenes,
        ocr_spans=[],
        transcript_spans=[],
        segments=[Segment(start=0.0, end=6.0, editorial_score=0.4, hook_score=0.2)],
        pacing={},
        transitions=[],
        keyframes=[],
    )

    assert text_heavy.text_density > text_light.text_density
    assert text_heavy.ocr_density > text_light.ocr_density
    assert any("Text-heavy" in note for note in text_heavy.notes)
