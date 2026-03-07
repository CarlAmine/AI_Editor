from ai_editor.editor import (
    MIN_TEXT_DURATION,
    normalize_text_clips,
    normalize_tracks,
)


def test_track_ordering_overlay_first():
    edit = {
        "aspect_ratio": "16:9",
        "tracks": [
            {"clips": [{"asset": {"type": "title", "text": "Hello"}, "start": 0.0, "length": 1.0}]},
            {"clips": [{"asset": {"type": "video", "src": "v.mp4"}, "start": 0.0, "length": 5.0}]},
        ],
    }
    warnings = normalize_tracks(edit)
    assert edit["tracks"][0]["clips"][0]["asset"]["type"] == "title"
    assert any(w["code"] == "TRACK_ORDER_FIXED" for w in warnings)


def test_track_ordering_html_overlay_moves_above_video():
    edit = {
        "aspect_ratio": "16:9",
        "tracks": [
            {"clips": [{"asset": {"type": "video", "src": "v.mp4"}, "start": 0.0, "length": 5.0}]},
            {"clips": [{"asset": {"type": "html", "html": "<div>Hello</div>"}, "start": 0.5, "length": 2.0}]},
        ],
    }
    warnings = normalize_tracks(edit)
    assert edit["tracks"][0]["clips"][0]["asset"]["type"] == "html"
    assert edit["tracks"][1]["clips"][0]["asset"]["type"] == "video"
    assert any(w["code"] == "TRACK_ORDER_FIXED" for w in warnings)


def test_min_text_duration_enforced():
    edit = {
        "aspect_ratio": "16:9",
        "tracks": [
            {"clips": [{"asset": {"type": "video", "src": "v.mp4"}, "start": 0.0, "length": 5.0}]},
            {"clips": [{"asset": {"type": "title", "text": "Hi"}, "start": 0.0, "length": 0.1, "offset": {"x": 0, "y": 0.2}}]},
        ],
    }
    warnings = normalize_text_clips(edit)
    text_clip = edit["tracks"][1]["clips"][0]
    assert text_clip["length"] >= MIN_TEXT_DURATION
    assert any(w["code"] == "TEXT_DURATION_EXTENDED" for w in warnings)


def test_offset_clamped():
    edit = {
        "aspect_ratio": "16:9",
        "tracks": [
            {"clips": [{"asset": {"type": "video", "src": "v.mp4"}, "start": 0.0, "length": 5.0}]},
            {"clips": [{"asset": {"type": "title", "text": "Hi"}, "start": 0.0, "length": 2.5, "offset": {"x": 2.1, "y": 1.3}}]},
        ],
    }
    warnings = normalize_text_clips(edit)
    text_clip = edit["tracks"][1]["clips"][0]
    assert -0.8 <= text_clip["offset"]["x"] <= 0.8
    assert -0.8 <= text_clip["offset"]["y"] <= 0.8
    assert any(w["code"] == "TEXT_OFFSET_CLAMPED" for w in warnings)
