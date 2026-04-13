from ai_editor.analysis.analysis_schema import Segment, VideoMetadata
from ai_editor.analysis.segment_scorer import SegmentScorer


def test_segment_scores_are_deterministic_and_populated():
    scorer = SegmentScorer()
    metadata = VideoMetadata(path="demo.mp4", name="demo.mp4", duration_seconds=20.0)
    segments = [
        Segment(
            start=0.0,
            end=4.0,
            scene_id=1,
            transcript_text="Fast intro hook",
            ocr_text="TOP 10",
            has_transcript=True,
            has_ocr=True,
            novelty_score=0.82,
            visual_cluster_id="cluster_1",
            visual_signature={"contrast": 40.0, "edge_density": 0.22},
        ),
        Segment(
            start=10.0,
            end=16.0,
            scene_id=2,
            transcript_text="Longer explanatory middle section with more context",
            ocr_text="",
            has_transcript=True,
            has_ocr=False,
            novelty_score=0.12,
            visual_cluster_id="cluster_1",
            visual_signature={"contrast": 12.0, "edge_density": 0.04},
        ),
    ]

    scored = scorer.score(
        segments,
        metadata=metadata,
        pacing={"pacing_category": "Fast (rapid cuts)"},
        transitions=[{"type": "Hard Cut"}, {"type": "Quick Fade"}],
    )

    assert scored[0].quality_score == scorer.score(
        [
            Segment(
                start=0.0,
                end=4.0,
                scene_id=1,
                transcript_text="Fast intro hook",
                ocr_text="TOP 10",
                has_transcript=True,
                has_ocr=True,
            ),
            Segment(
                start=10.0,
                end=16.0,
                scene_id=2,
                transcript_text="Longer explanatory middle section with more context",
                ocr_text="",
                has_transcript=True,
                has_ocr=False,
            ),
        ],
        metadata=metadata,
        pacing={"pacing_category": "Fast (rapid cuts)"},
        transitions=[{"type": "Hard Cut"}, {"type": "Quick Fade"}],
    )[0].quality_score
    assert 0.0 <= scored[0].quality_score <= 1.0
    assert 0.0 <= scored[0].hook_score <= 1.0
    assert 0.0 <= scored[0].broll_score <= 1.0
    assert 0.0 <= scored[0].editorial_score <= 1.0
    assert 0.0 <= scored[0].novelty_score <= 1.0
    assert scored[0].editorial_score > scored[1].editorial_score
    assert scored[0].broll_score > scored[1].broll_score
