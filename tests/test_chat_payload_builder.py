# tests/test_chat_payload_builder.py

from ai_editor.chat_intake.payload_builder import build_pipeline_payload

def test_build_pipeline_payload_basic():
    state = {
        "primary_url": "https://www.youtube.com/watch?v=ref123",
        "sources": [
            "https://www.youtube.com/watch?v=src1",
            {"url": "https://www.youtube.com/watch?v=src2", "label": 2}
        ],
        "aspect_ratio": "16:9",
        "refit_mode": "crop_center",
        "music_mode": "original",
    }
    
    payload = build_pipeline_payload(state)
    
    assert payload["primary_url"] == "https://www.youtube.com/watch?v=ref123"
    assert len(payload["sources"]) == 2
    assert payload["sources"][0]["url"] == "https://www.youtube.com/watch?v=src1"
    assert payload["sources"][0]["label"] == 1
    assert payload["sources"][1]["url"] == "https://www.youtube.com/watch?v=src2"
    assert payload["sources"][1]["label"] == 2
    assert payload["music_mode"] == "original"
    assert payload["custom_music_url"] is None
    assert "Replicate the editing style" in payload["prompt"]
    assert payload["requirements_state"]["aspect_ratio"] == "16:9"
    assert payload["requirements_state"]["intent_mode"] == "video"


def test_build_pipeline_payload_custom_music():
    state = {
        "primary_url": "https://www.youtube.com/watch?v=ref123",
        "sources": ["https://www.youtube.com/watch?v=src1"],
        "music_mode": "custom",
        "custom_music_url": "https://www.youtube.com/watch?v=song123",
        "custom_music_segment": "10-40",
    }
    
    payload = build_pipeline_payload(state)
    
    assert payload["music_mode"] == "custom"
    assert payload["custom_music_url"] == "https://www.youtube.com/watch?v=song123"
    assert payload["custom_music_segment"] == "10-40"
    assert "Audio: Custom track from" in payload["prompt"]
