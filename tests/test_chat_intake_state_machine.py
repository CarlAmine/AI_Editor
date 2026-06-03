# tests/test_chat_intake_state_machine.py

import pytest
from ai_editor.chat_intake.state_machine import process_guided_turn
from ai_editor.chat_intake.schemas import (
    PHASE_AWAITING_REFERENCE,
    PHASE_REFERENCE_URL_RECEIVED,
    PHASE_AWAITING_SOURCES,
    PHASE_AWAITING_SLOT_MAPPING,
    PHASE_AWAITING_FINAL_CONFIRMATION,
)


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    """Force regex fallback in all tests by suppressing LLM calls."""
    import ai_editor.chat_intake.extractors as ext
    monkeypatch.setattr(ext, "chat_json", lambda **kwargs: None)


def test_empty_state_transition():
    res = process_guided_turn("", {})
    state = res["updated_state"]
    assert state["phase"] == PHASE_AWAITING_REFERENCE
    assert "reference video URL" in res["next_message"]


def test_reference_url_received():
    res = process_guided_turn("https://www.youtube.com/watch?v=ref123", {})
    state = res["updated_state"]
    assert state["primary_url"] == "https://www.youtube.com/watch?v=ref123"
    assert state["phase"] == PHASE_REFERENCE_URL_RECEIVED
    assert "editing style" in res["next_message"].lower()


def test_sources_and_drive_received():
    initial_state = {
        "phase": PHASE_AWAITING_SOURCES,
        "primary_url": "https://www.youtube.com/watch?v=ref123",
        "reference_slots": [
            {"slot_id": 1, "role": "hook", "duration": 5.0},
            {"slot_id": 2, "role": "outro", "duration": 10.0},
        ]
    }

    # Send Google Drive folder URL — skips slot mapping, goes straight to confirmation
    res = process_guided_turn("https://drive.google.com/drive/folders/folder123", initial_state)
    state = res["updated_state"]
    assert state["google_drive_link"] == "https://drive.google.com/drive/folders/folder123"
    assert state["phase"] == PHASE_AWAITING_FINAL_CONFIRMATION

    # Send replacement clip URLs — auto-mapped, goes to confirmation
    res2 = process_guided_turn(
        "use these: https://www.youtube.com/watch?v=src1 and https://www.youtube.com/watch?v=src2",
        initial_state,
    )
    state2 = res2["updated_state"]
    assert len(state2["sources"]) == 2
    assert state2["sources"][0]["url"] == "https://www.youtube.com/watch?v=src1"
    assert len(state2["slot_mapping"]) == 2
    assert state2["slot_mapping"][0]["clip_url"] == "https://www.youtube.com/watch?v=src1"
    assert state2["phase"] == PHASE_AWAITING_FINAL_CONFIRMATION


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
    assert "1 clip" in res["next_message"]
    assert "1 still needed" in res["next_message"]


def test_slots_complete_goes_to_confirmation():
    initial_state = {
        "phase": PHASE_AWAITING_SLOT_MAPPING,
        "primary_url": "https://www.youtube.com/watch?v=ref123",
        "reference_slots": [{"slot_id": 1, "role": "hook", "duration": 5.0}],
        "sources": [{"url": "https://www.youtube.com/watch?v=src1", "label": 1}],
        "slot_mapping": [{"slot_id": 1, "clip_url": "https://www.youtube.com/watch?v=src1"}],
    }

    res = process_guided_turn("", initial_state)
    state = res["updated_state"]
    assert state["phase"] == PHASE_AWAITING_FINAL_CONFIRMATION
    assert state["ready_to_submit"] is True
    assert "everything" in res["next_message"].lower()


def test_change_plan_path():
    initial_state = {
        "phase": PHASE_AWAITING_FINAL_CONFIRMATION,
        "primary_url": "https://www.youtube.com/watch?v=ref123",
        "reference_slots": [{"slot_id": 1, "role": "hook", "duration": 5.0}],
        "sources": [{"url": "https://www.youtube.com/watch?v=src1", "label": 1}],
        "slot_mapping": [{"slot_id": 1, "clip_url": "https://www.youtube.com/watch?v=src1"}],
        "ready_to_submit": True,
    }

    res = process_guided_turn("edit plan please", initial_state)
    state = res["updated_state"]
    assert state["phase"] == PHASE_AWAITING_SLOT_MAPPING
    assert state["ready_to_submit"] is False
    assert "tweak" in res["next_message"].lower()


def test_llm_extraction_path(monkeypatch):
    """Verify the LLM path is used when chat_json returns a valid result."""
    import ai_editor.chat_intake.extractors as ext

    def fake_chat_json(messages, temperature, **kwargs):
        return {"primary_url": "https://www.youtube.com/watch?v=llm_ref"}

    monkeypatch.setattr(ext, "chat_json", fake_chat_json)

    res = process_guided_turn("here is my reference https://www.youtube.com/watch?v=llm_ref", {})
    state = res["updated_state"]
    assert state["primary_url"] == "https://www.youtube.com/watch?v=llm_ref"
    assert state["phase"] == PHASE_REFERENCE_URL_RECEIVED
