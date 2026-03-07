from pipeline.plans.builders import build_text_segments


def test_segments_follow_keyframe_timestamps():
    analysis = {
        "scenes": [{"start_time": 0.0, "end_time": 6.0}],
        "keyframes": [
            {"timestamp": 0.0, "detected_text": "TOP 10"},
            {"timestamp": 1.7333, "detected_text": "TOP 10"},
            {"timestamp": 3.4667, "detected_text": "10 MANDY"},
            {"timestamp": 5.2, "detected_text": "9 LOU"},
        ],
    }
    out = build_text_segments(analysis, video_end=6.0)
    segs = out["segments"]
    assert len(segs) == 3
    assert abs(segs[0]["start"] - 0.0) < 0.01
    assert abs(segs[0]["end"] - 3.4667) < 0.01
    assert abs(segs[1]["start"] - 3.4667) < 0.01
    assert abs(segs[1]["end"] - 5.2) < 0.01
    assert abs(segs[2]["start"] - 5.2) < 0.01
    assert abs(segs[2]["end"] - 6.0) < 0.01


def test_segments_do_not_cross_scene_boundaries():
    analysis = {
        "scenes": [
            {"start_time": 0.0, "end_time": 2.0},
            {"start_time": 2.0, "end_time": 4.0},
        ],
        "keyframes": [
            {"timestamp": 1.5, "detected_text": "A"},
            {"timestamp": 3.0, "detected_text": "B"},
        ],
    }
    out = build_text_segments(analysis, video_end=4.0)
    segs = out["segments"]
    assert any(abs(s["start"] - 1.5) < 0.01 and abs(s["end"] - 2.0) < 0.01 for s in segs)
    assert any(abs(s["start"] - 2.0) < 0.01 and abs(s["end"] - 3.0) < 0.01 for s in segs)
