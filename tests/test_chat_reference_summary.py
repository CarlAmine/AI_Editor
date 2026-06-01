# tests/test_chat_reference_summary.py

from ai_editor.chat_intake.reference_summary import (
    infer_slot_role,
    build_reference_slots,
    build_reference_summary,
    summarize_reference_for_chat,
)
from ai_editor.chat_intake.text_overlays import build_text_overlays_from_analysis

def test_infer_slot_role():
    assert infer_slot_role(0, 5) == "hook"
    assert infer_slot_role(4, 5) == "outro"
    assert infer_slot_role(3, 5) == "climax"
    assert infer_slot_role(1, 5) == "reveal"
    assert infer_slot_role(2, 5) == "b-roll"


def test_build_reference_slots_from_scenes():
    analysis_results = {
        "scenes": [
            {"start_time": 0.0, "end_time": 5.0},
            {"start_time": 5.0, "end_time": 12.0},
            {"start_time": 12.0, "end_time": 15.0},
        ]
    }
    slots = build_reference_slots(analysis_results, 15.0)
    assert len(slots) == 3
    assert slots[0]["slot_id"] == 1
    assert slots[0]["role"] == "hook"
    assert slots[0]["start_time"] == 0.0
    assert slots[0]["end_time"] == 5.0
    assert slots[0]["duration"] == 5.0

    assert slots[1]["slot_id"] == 2
    assert slots[1]["role"] == "reveal"
    assert slots[1]["start_time"] == 5.0
    assert slots[1]["end_time"] == 12.0
    assert slots[1]["duration"] == 7.0

    assert slots[2]["slot_id"] == 3
    assert slots[2]["role"] == "outro"
    assert slots[2]["start_time"] == 12.0
    assert slots[2]["end_time"] == 15.0
    assert slots[2]["duration"] == 3.0


def test_build_reference_slots_fallback():
    # Empty analysis_results
    slots = build_reference_slots({}, 15.0)
    assert len(slots) == 3  # 15.0 seconds divided by 5.0s steps
    assert slots[0]["slot_id"] == 1
    assert slots[0]["duration"] == 5.0
    assert slots[1]["slot_id"] == 2
    assert slots[1]["duration"] == 5.0
    assert slots[2]["slot_id"] == 3
    assert slots[2]["duration"] == 5.0


def test_build_reference_summary():
    analysis_results = {
        "metadata": {
            "duration_seconds": 15.0,
            "fps": 30.0,
            "width": 1080,
            "height": 1920,
        },
        "scenes": [
            {"start_time": 0.0, "end_time": 5.0},
            {"start_time": 5.0, "end_time": 15.0},
        ],
        "style_profile": {
            "editing_rhythm": "Fast-paced",
            "captions_style": "Bold Yellow",
            "transitions_rhythm": "Sharp cuts",
        }
    }
    summary = build_reference_summary(analysis_results, {})
    assert summary["duration_seconds"] == 15.0
    assert summary["fps"] == 30.0
    assert summary["aspect_ratio"] == "9:16"
    assert summary["scene_count"] == 2
    assert "Fast-paced" in summary["style_summary"]
    assert "Bold Yellow" in summary["style_summary"]


def test_summarize_reference_for_chat():
    summary = {
        "duration_seconds": 15.0,
        "aspect_ratio": "9:16",
        "width": 1080,
        "height": 1920,
        "fps": 30.0,
        "style_summary": "Editing Pacing: Fast-paced.",
    }
    slots = [
        {"slot_id": 1, "start_time": 0.0, "end_time": 5.0, "duration": 5.0, "role": "hook"},
        {"slot_id": 2, "start_time": 5.0, "end_time": 15.0, "duration": 10.0, "role": "outro"},
    ]
    chat_text = summarize_reference_for_chat(summary, slots)
    assert "Reference analysis is complete." in chat_text
    assert "Duration: 15.0 seconds" in chat_text
    assert "Format: 9:16" in chat_text
    assert "Detected slots: 2" in chat_text
    assert "Use the forms below" in chat_text


def test_build_text_overlays_attached_to_slots():
    analysis = {
        "ocr_spans": [{"timestamp": 1.0, "text": "Hello"}],
        "keyframes": [{"timestamp": 6.0, "detected_text": "World"}],
        "scenes": [
            {"start_time": 0.0, "end_time": 5.0},
            {"start_time": 5.0, "end_time": 10.0},
        ],
    }
    slots = build_reference_slots(analysis, 10.0)
    overlays = build_text_overlays_from_analysis(analysis, slots)
    assert overlays
    assert overlays[0]["slot_id"] in {1, 2}
