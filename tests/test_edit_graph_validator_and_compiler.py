from __future__ import annotations

import pytest

from ai_editor.edit_agent.compiler import compile_edit_graph_to_render_spec
from ai_editor.edit_agent.validator import validate_edit_graph


def _template(num_slots: int = 3, duration: float = 30.0) -> dict:
    seg = duration / num_slots
    return {
        "template_id": "template_001",
        "source_video_path": "/ref.mp4",
        "duration": duration,
        "fps": 30.0,
        "width": 1080,
        "height": 1920,
        "slots": [
            {
                "slot_id": i + 1,
                "start": i * seg,
                "end": (i + 1) * seg,
                "duration": seg,
                "role": "hook" if i == 0 else ("outro" if i == num_slots - 1 else "main"),
                "scene_id": i + 1,
                "text_ref": None,
                "transition_out": {"type": "hard_cut", "duration": 0.0},
                "motion": None,
                "style_tags": [],
            }
            for i in range(num_slots)
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


def _inventory(num_clips: int = 3, duration: float = 30.0) -> dict:
    return {
        "clips": [
            {
                "clip_id": f"clip_{i + 1:02d}",
                "source_index": i,
                "path": f"/src/c{i + 1}.mp4",
                "duration": duration,
                "fps": 30.0,
                "width": 1920,
                "height": 1080,
                "candidate_segments": [
                    {
                        "start": 0.0,
                        "end": duration / 2.0,
                        "duration": duration / 2.0,
                        "quality_score": 0.9,
                        "motion_score": 0.7,
                        "subject_position": "unknown",
                        "selection_reason": "beginning_segment",
                    }
                ],
                "metadata": {},
            }
            for i in range(num_clips)
        ],
        "warnings": [],
    }


def _graph(num_slots: int = 3, duration: float = 30.0) -> dict:
    seg = duration / num_slots
    return {
        "version": "edit_graph_v1",
        "timeline": [
            {
                "slot_id": i + 1,
                "clip_id": f"clip_{i + 1:02d}",
                "source_index": i,
                "video_src": None,
                "source_start": 0.0,
                "duration": seg,
                "crop": {"mode": "center", "aspect_ratio": "9:16"},
                "motion_effects": [],
                "transition_out": {"type": "hard_cut", "duration": 0.0},
                "text": None,
                "style_ops": [{"type": "match_reference_style", "strength": 0.5}],
                "metadata": {},
            }
            for i in range(num_slots)
        ],
        "global_style_ops": [],
        "audio": {},
        "warnings": [],
        "model_metadata": {"backend": "llm_json"},
    }


def test_valid_graph_passes_validation() -> None:
    result = validate_edit_graph(_graph(), _template(), _inventory())
    assert result["valid"] is True
    assert result["errors"] == []


def test_missing_timeline_fails() -> None:
    graph = _graph()
    del graph["timeline"]
    result = validate_edit_graph(graph, _template(), _inventory())
    assert result["valid"] is False
    assert any("timeline" in error.lower() for error in result["errors"])


def test_invalid_version_fails() -> None:
    graph = _graph()
    graph["version"] = "wrong_version"
    result = validate_edit_graph(graph, _template(), _inventory())
    assert result["valid"] is False
    assert any("version" in error.lower() for error in result["errors"])


def test_invented_clip_id_fails() -> None:
    graph = _graph()
    graph["timeline"][0]["clip_id"] = "made_up_clip"
    result = validate_edit_graph(graph, _template(), _inventory())
    assert result["valid"] is False
    assert any("made_up_clip" in error for error in result["errors"])


def test_source_overrun_fails() -> None:
    graph = _graph(num_slots=1, duration=10.0)
    graph["timeline"][0]["source_start"] = 8.0
    graph["timeline"][0]["duration"] = 5.0
    result = validate_edit_graph(graph, _template(num_slots=1, duration=10.0), _inventory(num_clips=1, duration=10.0))
    assert result["valid"] is False
    assert any("overruns" in error for error in result["errors"])


def test_string_text_is_accepted() -> None:
    graph = _graph(num_slots=1, duration=10.0)
    graph["timeline"][0]["text"] = "Look at this"
    result = validate_edit_graph(graph, _template(num_slots=1, duration=10.0), _inventory(num_clips=1, duration=10.0))
    assert result["valid"] is True


def test_valid_graph_compiles_to_canonical_timeline() -> None:
    result = compile_edit_graph_to_render_spec(
        _graph(num_slots=2, duration=12.0),
        _inventory(num_clips=2, duration=12.0),
        _template(num_slots=2, duration=12.0),
        {"resolution": "1080x1920"},
    )
    rows = result["canonical_timeline"]
    assert len(rows) == 2
    assert rows[0]["label"] == "slot_001"
    assert rows[0]["video_src"] == "/src/c1.mp4"
    assert rows[0]["videoSrc"] == "/src/c1.mp4"
    assert rows[0]["trim"] == pytest.approx(0.0)
    assert rows[1]["end"] == pytest.approx(12.0)
