from __future__ import annotations

import json

import pytest

from ai_editor.edit_agent.model_client import (
    ReferenceEditAgentError,
    compile_edit_graph,
)


def _template() -> dict:
    return {
        "template_id": "template_001",
        "source_video_path": "/ref.mp4",
        "duration": 6.0,
        "fps": 30.0,
        "width": 1080,
        "height": 1920,
        "slots": [
            {
                "slot_id": 1,
                "start": 0.0,
                "end": 3.0,
                "duration": 3.0,
                "role": "hook",
                "scene_id": 1,
                "text_ref": {"value": "Original"},
                "transition_out": {"type": "hard_cut", "duration": 0.0},
                "motion": {"type": "push_in"},
                "style_tags": ["short_form"],
            },
            {
                "slot_id": 2,
                "start": 3.0,
                "end": 6.0,
                "duration": 3.0,
                "role": "outro",
                "scene_id": 2,
                "text_ref": None,
                "transition_out": {"type": "hard_cut", "duration": 0.0},
                "motion": None,
                "style_tags": ["short_form"],
            },
        ],
        "transitions": [],
        "overlays": [],
        "texts": [],
        "motion_effects": [],
        "style_profile": {},
        "audio_profile": {},
        "constraints": {},
        "warnings": [],
    }


def _user_plan() -> dict:
    return {
        "slot_replacements": [
            {
                "slot_id": 1,
                "clip_id": "clip_01",
                "source_index": 0,
                "replacement_text": "Look at this",
            }
        ],
        "text_replacements": [],
        "preserve": {"timing": True},
        "user_notes": "",
        "raw_requirements": {},
    }


def _inventory() -> dict:
    return {
        "clips": [
            {
                "clip_id": "clip_01",
                "source_index": 0,
                "path": "/src/clip_01.mp4",
                "duration": 5.0,
                "fps": 30.0,
                "width": 1920,
                "height": 1080,
                "candidate_segments": [{"start": 0.0, "end": 3.0, "duration": 3.0}],
                "metadata": {},
            },
            {
                "clip_id": "clip_02",
                "source_index": 1,
                "path": "/src/clip_02.mp4",
                "duration": 5.0,
                "fps": 30.0,
                "width": 1920,
                "height": 1080,
                "candidate_segments": [{"start": 1.0, "end": 4.0, "duration": 3.0}],
                "metadata": {},
            },
        ],
        "warnings": [],
    }


def _valid_graph() -> dict:
    return {
        "version": "edit_graph_v1",
        "timeline": [
            {
                "slot_id": 1,
                "clip_id": "clip_01",
                "source_index": 0,
                "video_src": None,
                "source_start": 0.0,
                "duration": 3.0,
                "crop": {"mode": "center", "aspect_ratio": "9:16"},
                "motion_effects": [{"type": "push_in"}],
                "transition_out": {"type": "hard_cut", "duration": 0.0},
                "text": {"value": "Look at this"},
                "style_ops": [{"type": "match_reference_style", "strength": 0.5}],
                "metadata": {},
            },
            {
                "slot_id": 2,
                "clip_id": "clip_02",
                "source_index": 1,
                "video_src": None,
                "source_start": 1.0,
                "duration": 3.0,
                "crop": {"mode": "center", "aspect_ratio": "9:16"},
                "motion_effects": [],
                "transition_out": {"type": "hard_cut", "duration": 0.0},
                "text": None,
                "style_ops": [{"type": "match_reference_style", "strength": 0.5}],
                "metadata": {},
            },
        ],
        "global_style_ops": [],
        "audio": {},
        "warnings": [],
        "model_metadata": {},
    }


def _configure_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EDIT_AGENT_BACKEND", "llm_json")
    monkeypatch.setenv("EDIT_AGENT_MODEL", "test-model")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")


def test_valid_llm_output_is_returned(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_env(monkeypatch)
    monkeypatch.setattr(
        "ai_editor.edit_agent.model_client._call_llm_json_agent",
        lambda prompt, *, model, temperature: json.dumps(_valid_graph()),
    )
    graph = compile_edit_graph(_template(), _user_plan(), _inventory(), {"prompt": "Use the reference edit"})
    assert graph["version"] == "edit_graph_v1"
    assert graph["model_metadata"]["backend"] == "llm_json"


def test_markdown_wrapped_json_is_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_env(monkeypatch)
    payload = "```json\n" + json.dumps(_valid_graph()) + "\n```"
    monkeypatch.setattr(
        "ai_editor.edit_agent.model_client._call_llm_json_agent",
        lambda prompt, *, model, temperature: payload,
    )
    graph = compile_edit_graph(_template(), _user_plan(), _inventory(), {"prompt": "Use the reference edit"})
    assert graph["timeline"][0]["clip_id"] == "clip_01"


def test_invalid_then_repaired_graph(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_env(monkeypatch)
    calls = []

    invalid = _valid_graph()
    invalid["timeline"][0]["clip_id"] = "invented"

    responses = [json.dumps(invalid), json.dumps(_valid_graph())]

    def fake_call(prompt: str, *, model: str, temperature: float) -> str:
        calls.append(prompt)
        return responses[len(calls) - 1]

    monkeypatch.setattr("ai_editor.edit_agent.model_client._call_llm_json_agent", fake_call)
    graph = compile_edit_graph(_template(), _user_plan(), _inventory(), {"prompt": "Fix it"})
    assert len(calls) == 2
    assert "VALIDATION_ERRORS:" in calls[1]
    assert graph["timeline"][0]["clip_id"] == "clip_01"


def test_invalid_twice_raises_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_env(monkeypatch)
    invalid = _valid_graph()
    invalid["timeline"][0]["clip_id"] = "invented"
    monkeypatch.setattr(
        "ai_editor.edit_agent.model_client._call_llm_json_agent",
        lambda prompt, *, model, temperature: json.dumps(invalid),
    )
    with pytest.raises(ReferenceEditAgentError) as exc:
        compile_edit_graph(_template(), _user_plan(), _inventory(), {"prompt": "Fix it"})
    assert exc.value.code == "REFERENCE_EDIT_AGENT_INVALID_GRAPH"


def test_missing_provider_raises_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("EDIT_AGENT_BACKEND", "llm_json")
    monkeypatch.setenv("EDIT_AGENT_MODEL", "test-model")
    with pytest.raises(ReferenceEditAgentError) as exc:
        compile_edit_graph(_template(), _user_plan(), _inventory(), {"prompt": "Use the reference edit"})
    assert exc.value.code == "REFERENCE_EDIT_AGENT_LLM_UNAVAILABLE"
