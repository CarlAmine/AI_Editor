from ai_editor.analysis.analysis_schema import (
    AnalysisResult,
    EffectType,
    MotionCurve,
    MotionEffect,
    MotionEffectManifest,
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
        motion_effects=MotionEffectManifest(
            video_path="sample.mp4",
            fps=30.0,
            total_frames=300,
            effects=[
                MotionEffect(
                    shot_index=0,
                    effect_type=EffectType.STATIC,
                    onset_frac=0.0,
                    offset_frac=1.0,
                    intensity=0.0,
                    curve=MotionCurve(dx_norm=[0.0], dy_norm=[0.0], frame_indices=[0]),
                )
            ],
            rhythm_pattern=[10.0],
            global_motion_budget=0.0,
        ),
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
    assert payload["motion_effects"]["video_path"] == "sample.mp4"
    assert payload["motion_effects"]["effects"][0]["effect_type"] == "static"
    assert payload["scenes"][0]["start_time"] == 0.0
    assert len(payload["keyframes"]) == 2
    assert payload["keyframes"][0]["detected_text"] == "TOP 10; JAPAN"


def test_motion_effect_manifest_round_trips_from_dict():
    manifest = MotionEffectManifest(
        video_path="reference.mp4",
        fps=25.0,
        total_frames=100,
        effects=[
            MotionEffect(
                shot_index=1,
                effect_type=EffectType.SHAKE,
                onset_frac=0.1,
                offset_frac=0.7,
                intensity=0.65,
                curve=MotionCurve(
                    dx_norm=[0.01, -0.01],
                    dy_norm=[0.005, -0.004],
                    scale=[1.0, 1.01],
                    rotation_deg=[0.2, -0.2],
                    residual=[0.1, 0.2],
                    frame_indices=[10, 11],
                ),
                metadata={"source": "unit-test"},
            )
        ],
        rhythm_pattern=[2.0, 2.0],
        global_motion_budget=0.0123,
    )

    restored = MotionEffectManifest.from_dict(manifest.to_dict())

    assert restored.video_path == manifest.video_path
    assert restored.effects[0].effect_type == EffectType.SHAKE
    assert restored.effects[0].metadata["source"] == "unit-test"
    assert restored.effects[0].curve.dx_norm == [0.01, -0.01]
