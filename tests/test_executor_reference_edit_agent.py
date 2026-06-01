from __future__ import annotations

import json

import pytest

from ai_editor.edit_agent.executor_adapter import run_edit_agent_compile_stage
from ai_editor.edit_agent.model_client import ReferenceEditAgentError


def _make_template() -> dict:
    return {
        "template_id": "tpl_exec",
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
                "text_ref": {"value": "Original one"},
                "transition_out": {"type": "hard_cut", "duration": 0.0},
                "motion": None,
                "style_tags": [],
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
                "style_tags": [],
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


def _make_inventory() -> dict:
    return {
        "clips": [
            {
                "clip_id": "clip_01",
                "source_index": 0,
                "path": "/src/c1.mp4",
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
                "path": "/src/c2.mp4",
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
                "motion_effects": [],
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
        "model_metadata": {"backend": "llm_json"},
    }


def _payload() -> dict:
    return {
        "prompt": "Use the reference edit but replace the clip and text.",
        "sources": [],
        "slot_mapping": [],
        "requirements_state": {},
    }


def _requirements() -> dict:
    return {
        "prompt": "Use the reference edit but replace the clip and text.",
        "generation_mode": "reference_edit_agent",
        "slot_replacements": [{"slot_id": 1, "source_index": 0, "replacement_text": "Look at this"}],
    }


def test_valid_llm_graph_writes_expected_artifacts(tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ai_editor.edit_agent.executor_adapter.compile_edit_graph",
        lambda reference_template, user_patched_plan, source_inventory, requirements: _valid_graph(),
    )
    result = run_edit_agent_compile_stage(
        job_id="job_valid",
        job_dir=str(tmp_path),
        requirements=_requirements(),
        request_payload=_payload(),
        reference_template=_make_template(),
        source_inventory=_make_inventory(),
    )
    assert result["validation"]["valid"] is True
    assert result["render_spec"]["canonical_timeline"]
    assert (tmp_path / "plans" / "user_patched_plan.json").exists()
    assert (tmp_path / "plans" / "executable_edit_graph.json").exists()
    assert (tmp_path / "plans" / "edit_graph_validation.json").exists()
    assert (tmp_path / "plans" / "compiled_render_spec.json").exists()
    assert (tmp_path / "training" / "edit_agent_sample.json").exists()


def test_failure_writes_error_and_no_compiled_render_spec(tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_invalid(*args, **kwargs):
        raise ReferenceEditAgentError(
            "REFERENCE_EDIT_AGENT_INVALID_GRAPH",
            "The LLM returned invalid graph output twice.",
            {"attempts": 2},
        )

    monkeypatch.setattr("ai_editor.edit_agent.executor_adapter.compile_edit_graph", raise_invalid)
    with pytest.raises(ReferenceEditAgentError) as exc:
        run_edit_agent_compile_stage(
            job_id="job_invalid",
            job_dir=str(tmp_path),
            requirements=_requirements(),
            request_payload=_payload(),
            reference_template=_make_template(),
            source_inventory=_make_inventory(),
        )
    assert exc.value.code == "REFERENCE_EDIT_AGENT_INVALID_GRAPH"
    assert (tmp_path / "plans" / "edit_agent_error.json").exists()
    assert not (tmp_path / "plans" / "compiled_render_spec.json").exists()
    assert not (tmp_path / "training" / "edit_agent_sample.json").exists()


def test_error_artifact_is_structured_json(tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ai_editor.edit_agent.executor_adapter.compile_edit_graph",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ReferenceEditAgentError(
                "REFERENCE_EDIT_AGENT_LLM_UNAVAILABLE",
                "reference_edit_agent requires an LLM provider.",
                {"backend": "llm_json"},
            )
        ),
    )
    with pytest.raises(ReferenceEditAgentError):
        run_edit_agent_compile_stage(
            job_id="job_missing_provider",
            job_dir=str(tmp_path),
            requirements=_requirements(),
            request_payload=_payload(),
            reference_template=_make_template(),
            source_inventory=_make_inventory(),
        )
    error_path = tmp_path / "plans" / "edit_agent_error.json"
    with open(error_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    assert payload["code"] == "REFERENCE_EDIT_AGENT_LLM_UNAVAILABLE"
