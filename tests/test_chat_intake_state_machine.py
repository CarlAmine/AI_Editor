# tests/test_chat_intake_state_machine.py

from ai_editor.chat_intake.state_machine import process_guided_turn
from ai_editor.chat_intake.schemas import (
    PHASE_AWAITING_REFERENCE,
    PHASE_REFERENCE_URL_RECEIVED,
    PHASE_AWAITING_SOURCES,
    PHASE_AWAITING_SLOT_MAPPING,
    PHASE_AWAITING_AUDIO,
    PHASE_AWAITING_CUSTOM_MUSIC,
    PHASE_AWAITING_OUTPUT,
    PHASE_AWAITING_FINAL_CONFIRMATION,
)

def test_empty_state_transition():
    res = process_guided_turn("", {})
    state = res["updated_state"]
    assert state["phase"] == PHASE_AWAITING_REFERENCE
    assert "Send the reference video URL" in res["next_message"]


def test_reference_url_received():
    res = process_guided_turn("https://www.youtube.com/watch?v=ref123", {})
    state = res["updated_state"]
    assert state["primary_url"] == "https://www.youtube.com/watch?v=ref123"
    assert state["phase"] == PHASE_REFERENCE_URL_RECEIVED
    assert "reference video is being analyzed" in res["next_message"].lower()


def test_sources_and_drive_received():
    initial_state = {
        "phase": PHASE_AWAITING_SOURCES,
        "primary_url": "https://www.youtube.com/watch?v=ref123",
        "reference_slots": [
            {"slot_id": 1, "role": "hook", "duration": 5.0},
            {"slot_id": 2, "role": "outro", "duration": 10.0},
        ]
    }
    
    # Send Google Drive folder URL
    res = process_guided_turn("https://drive.google.com/drive/folders/folder123", initial_state)
    state = res["updated_state"]
    assert state["google_drive_link"] == "https://drive.google.com/drive/folders/folder123"
    assert state["phase"] == PHASE_AWAITING_AUDIO  # Skipping slot mapping since it's drive folder
    assert "Audio settings are next" in res["next_message"]

    # Send replacement clips URLs
    res2 = process_guided_turn("use these: https://www.youtube.com/watch?v=src1 and https://www.youtube.com/watch?v=src2", initial_state)
    state2 = res2["updated_state"]
    assert len(state2["sources"]) == 2
    assert state2["sources"][0]["url"] == "https://www.youtube.com/watch?v=src1"
    assert len(state2["slot_mapping"]) == 2  # Sequentially auto-mapped
    assert state2["slot_mapping"][0]["clip_url"] == "https://www.youtube.com/watch?v=src1"
    assert state2["phase"] == PHASE_AWAITING_AUDIO  # Complete slots mapping sequentially auto-assigned
    assert "Audio settings are next" in res2["next_message"]


def test_awaiting_slot_mapping_sequential_partial():
    initial_state = {
        "phase": PHASE_AWAITING_SOURCES,
        "primary_url": "https://www.youtube.com/watch?v=ref123",
        "reference_slots": [
            {"slot_id": 1, "role": "hook", "duration": 5.0},
            {"slot_id": 2, "role": "outro", "duration": 10.0},
        ],
        "sources": [{"url": "https://www.youtube.com/watch?v=src1", "label": 1}]
    }
    
    res = process_guided_turn("", initial_state)
    state = res["updated_state"]
    assert len(state["slot_mapping"]) == 1
    assert state["phase"] == PHASE_AWAITING_SLOT_MAPPING
    assert "1 slot(s) are mapped and 1 remain" in res["next_message"]


def test_audio_and_custom_music():
    initial_state = {
        "phase": PHASE_AWAITING_AUDIO,
        "primary_url": "https://www.youtube.com/watch?v=ref123",
        "reference_slots": [{"slot_id": 1, "role": "hook", "duration": 5.0}],
        "sources": [{"url": "https://www.youtube.com/watch?v=src1", "label": 1}],
        "slot_mapping": [{"slot_id": 1, "clip_url": "https://www.youtube.com/watch?v=src1"}],
    }
    
    # Select original audio
    res = process_guided_turn("keep original reference audio", initial_state)
    assert res["updated_state"]["music_mode"] == "original"
    assert res["updated_state"]["phase"] == PHASE_AWAITING_OUTPUT

    # Select custom music without URL
    res2 = process_guided_turn("use custom music please", initial_state)
    assert res2["updated_state"]["music_mode"] == "custom"
    assert res2["updated_state"]["phase"] == PHASE_AWAITING_CUSTOM_MUSIC
    assert "Enter the custom music URL" in res2["next_message"]

    # Select custom music WITH URL
    res3 = process_guided_turn("use custom music from https://www.youtube.com/watch?v=song123 from 10 to 40", initial_state)
    assert res3["updated_state"]["music_mode"] == "custom"
    assert res3["updated_state"]["custom_music_url"] == "https://www.youtube.com/watch?v=song123"
    assert res3["updated_state"]["custom_music_segment"] == "10-40"
    assert res3["updated_state"]["phase"] == PHASE_AWAITING_OUTPUT


def test_output_format_and_final_confirmation():
    initial_state = {
        "phase": PHASE_AWAITING_OUTPUT,
        "primary_url": "https://www.youtube.com/watch?v=ref123",
        "reference_slots": [{"slot_id": 1, "role": "hook", "duration": 5.0}],
        "sources": [{"url": "https://www.youtube.com/watch?v=src1", "label": 1}],
        "slot_mapping": [{"slot_id": 1, "clip_url": "https://www.youtube.com/watch?v=src1"}],
        "music_mode": "original",
    }
    
    res = process_guided_turn("make it vertical 9:16 and crop it", initial_state)
    state = res["updated_state"]
    assert state["intent_mode"] == "shorts"
    assert state["aspect_ratio"] == "9:16"
    assert state["refit_mode"] == "crop_center"
    assert state["phase"] == PHASE_AWAITING_FINAL_CONFIRMATION
    assert state["ready_to_submit"] is True
    assert "The edit plan is ready" in res["next_message"]


def test_change_plan_path():
    initial_state = {
        "phase": PHASE_AWAITING_FINAL_CONFIRMATION,
        "primary_url": "https://www.youtube.com/watch?v=ref123",
        "reference_slots": [{"slot_id": 1, "role": "hook", "duration": 5.0}],
        "sources": [{"url": "https://www.youtube.com/watch?v=src1", "label": 1}],
        "slot_mapping": [{"slot_id": 1, "clip_url": "https://www.youtube.com/watch?v=src1"}],
        "music_mode": "original",
        "aspect_ratio": "9:16",
        "refit_mode": "crop_center",
        "ready_to_submit": True,
    }
    
    res = process_guided_turn("edit plan please", initial_state)
    state = res["updated_state"]
    assert state["phase"] == PHASE_AWAITING_SLOT_MAPPING
    assert state["ready_to_submit"] is False
    assert "Understood! Let's modify" in res["next_message"]
