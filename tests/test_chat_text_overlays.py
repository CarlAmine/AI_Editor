"""Tests for chat text overlay planning."""

from ai_editor.chat_intake.extractors import extract_text_overlay_preferences
from ai_editor.chat_intake.text_overlays import build_text_overlays_from_analysis
from ai_editor.chat_intake.state_machine import process_guided_turn
from ai_editor.chat_intake.payload_builder import build_pipeline_payload
from pipeline.executor import _apply_confirmed_text_overlays_to_timeline, _should_bake_reference_transitions


def test_build_text_overlays_from_ocr_spans():
    analysis = {
        "ocr_spans": [
            {"timestamp": 0.5, "text": "SALE"},
            {"timestamp": 1.0, "text": "50% OFF"},
            {"timestamp": 8.0, "text": "BUY NOW"},
        ],
        "keyframes": [],
    }
    slots = [
        {"slot_id": 1, "start_time": 0.0, "end_time": 5.0},
        {"slot_id": 2, "start_time": 5.0, "end_time": 10.0},
    ]
    overlays = build_text_overlays_from_analysis(analysis, slots)
    assert len(overlays) >= 2
    assert overlays[0]["detected_text"]
    assert overlays[0]["action"] == "ask_user"
    assert overlays[0]["render_text"] == ""
    assert overlays[0]["slot_id"] == 1


def test_extract_remove_all_text():
    overlays = [
        {"overlay_id": "text_1", "slot_id": 1, "start": 0.0, "end": 2.0, "detected_text": "Hi"},
    ]
    result = extract_text_overlay_preferences("please remove all text", overlays)
    assert result["text_overlays_resolved"] is True
    assert result["text_overlays"][0]["action"] == "remove"


def test_state_machine_waits_for_text_overlay_choice():
    state = {
        "phase": "awaiting_output",
        "primary_url": "https://example.com/ref",
        "reference_slots": [{"slot_id": 1, "role": "hook", "duration": 5.0}],
        "sources": [{"url": "https://example.com/src1"}],
        "slot_mapping": [{"slot_id": 1, "clip_url": "https://example.com/src1"}],
        "music_mode": "original",
        "aspect_ratio": "9:16",
        "refit_mode": "crop_center",
        "text_overlays": [
            {
                "overlay_id": "text_1",
                "slot_id": 1,
                "start": 0.0,
                "end": 2.0,
                "detected_text": "SALE",
                "render_text": "",
                "action": "ask_user",
            }
        ],
        "text_overlays_resolved": False,
    }
    result = process_guided_turn("", state)
    assert result["updated_state"]["phase"] == "awaiting_text_overlays"
    assert result["updated_state"]["ready_to_submit"] is False


def test_payload_includes_text_overlays():
    state = {
        "primary_url": "https://example.com/ref",
        "text_overlays": [{"overlay_id": "text_1", "action": "remove"}],
        "text_overlays_resolved": True,
    }
    payload = build_pipeline_payload(state)
    assert payload["requirements_state"]["text_overlays"][0]["overlay_id"] == "text_1"


def test_apply_confirmed_text_overlays_to_timeline():
    timeline = [
        {"start": 0.0, "end": 5.0, "duration": 5.0},
        {"start": 5.0, "end": 10.0, "duration": 5.0},
    ]
    overlays = [
        {
            "overlay_id": "text_1",
            "start": 1.0,
            "end": 3.0,
            "action": "render",
            "render_text": "50% OFF",
            "position": "bottom",
            "style": {"box": False, "stroke": True},
        }
    ]
    _apply_confirmed_text_overlays_to_timeline(timeline, overlays)
    assert timeline[0]["text"] == "50% OFF"
    assert timeline[0]["text_start"] == 1.0
    assert timeline[0]["text_end"] == 3.0
    assert timeline[0]["text_style"]["box"] is False
    assert "text" not in timeline[1]


def test_transitions_disabled_by_default():
    assert _should_bake_reference_transitions({}) is False
    assert _should_bake_reference_transitions({"disable_auto_transitions": True}) is False
