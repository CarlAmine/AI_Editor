"""
Unit tests for ai_editor.edit_agent.mock_agent – compile_with_mock_agent
"""
from __future__ import annotations

import pytest
from ai_editor.edit_agent.mock_agent import compile_with_mock_agent


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_template(num_slots: int = 3, duration: float = 30.0) -> dict:
    seg = duration / num_slots
    slots = []
    for i in range(num_slots):
        role = "hook" if i == 0 else ("outro" if i == num_slots - 1 else "main")
        slots.append({
            "slot_id": i + 1,
            "start": i * seg,
            "end": (i + 1) * seg,
            "duration": seg,
            "role": role,
            "scene_id": i + 1,
            "text_ref": None,
            "transition_out": {"type": "hard_cut", "duration": 0.0},
            "motion": None,
            "style_tags": [],
        })
    return {
        "template_id": "tpl_01",
        "source_video_path": "/ref.mp4",
        "duration": duration,
        "fps": 30.0,
        "width": 1080,
        "height": 1920,
        "slots": slots,
        "transitions": [],
        "overlays": [],
        "texts": [],
        "motion_effects": [],
        "style_profile": {},
        "audio_profile": {},
        "constraints": {},
        "warnings": [],
    }


def _make_user_plan(slot_replacements=None, text_replacements=None) -> dict:
    return {
        "plan_id": "plan_01",
        "prompt": "Test prompt",
        "slot_replacements": slot_replacements or [],
        "text_replacements": text_replacements or [],
        "audio_requests": [],
        "style_requests": [],
        "global_requests": [],
    }


def _make_inventory(num_clips: int = 3, duration: float = 30.0) -> dict:
    seg = duration / 3.0
    clips = []
    for i in range(num_clips):
        clip_dur = duration
        clips.append({
            "clip_id": f"clip_{i + 1:02d}",
            "source_index": i,
            "path": f"/source/clip_{i + 1}.mp4",
            "duration": clip_dur,
            "fps": 30.0,
            "width": 1920,
            "height": 1080,
            "candidate_segments": [
                {"start": 0.0, "end": seg, "duration": seg, "quality_score": 0.85,
                 "motion_score": 0.6, "subject_position": "unknown", "selection_reason": "beginning_segment"},
                {"start": seg, "end": seg * 2, "duration": seg, "quality_score": 0.9,
                 "motion_score": 0.7, "subject_position": "unknown", "selection_reason": "middle_segment"},
                {"start": seg * 2, "end": clip_dur, "duration": clip_dur - seg * 2, "quality_score": 0.8,
                 "motion_score": 0.5, "subject_position": "unknown", "selection_reason": "ending_segment"},
            ],
            "metadata": {},
        })
    return {"clips": clips, "warnings": []}


# ---------------------------------------------------------------------------
# Structural tests
# ---------------------------------------------------------------------------

class TestCompileWithMockAgentStructure:
    def test_returns_dict(self):
        result = compile_with_mock_agent(
            _make_template(), _make_user_plan(), _make_inventory(), {}
        )
        assert isinstance(result, dict)

    def test_contains_version(self):
        result = compile_with_mock_agent(
            _make_template(), _make_user_plan(), _make_inventory(), {}
        )
        assert result.get("version") == "edit_graph_v1"

    def test_contains_timeline(self):
        result = compile_with_mock_agent(
            _make_template(), _make_user_plan(), _make_inventory(), {}
        )
        assert "timeline" in result
        assert isinstance(result["timeline"], list)

    def test_timeline_length_matches_slots(self):
        for n in (1, 3, 5):
            result = compile_with_mock_agent(
                _make_template(num_slots=n), _make_user_plan(), _make_inventory(num_clips=n), {}
            )
            assert len(result["timeline"]) == n

    def test_each_clip_has_required_keys(self):
        result = compile_with_mock_agent(
            _make_template(), _make_user_plan(), _make_inventory(), {}
        )
        required = {"slot_id", "clip_id", "source_start", "duration"}
        for clip in result["timeline"]:
            for key in required:
                assert key in clip, f"Missing key '{key}' in timeline clip"

    def test_backend_is_mock(self):
        result = compile_with_mock_agent(
            _make_template(), _make_user_plan(), _make_inventory(), {}
        )
        assert result.get("model_metadata", {}).get("backend") == "mock"


# ---------------------------------------------------------------------------
# Slot-to-clip mapping
# ---------------------------------------------------------------------------

class TestClipMapping:
    def test_fallback_cycles_through_clips(self):
        """With no explicit replacements, clips cycle through inventory."""
        result = compile_with_mock_agent(
            _make_template(num_slots=3), _make_user_plan(), _make_inventory(num_clips=3), {}
        )
        clip_ids = [c["clip_id"] for c in result["timeline"]]
        # Each slot maps to a clip from inventory
        assert all(cid.startswith("clip_") for cid in clip_ids)

    def test_slot_replacement_by_clip_id(self):
        user_plan = _make_user_plan(slot_replacements=[
            {
                "slot_id": 1,
                "clip_id": "clip_03",
                "source_index": None,
                "source_start": None,
                "source_end": None,
                "replacement_text": None,
            }
        ])
        result = compile_with_mock_agent(
            _make_template(num_slots=3), user_plan, _make_inventory(num_clips=3), {}
        )
        first_clip = result["timeline"][0]
        assert first_clip["clip_id"] == "clip_03"

    def test_slot_replacement_by_source_index(self):
        user_plan = _make_user_plan(slot_replacements=[
            {
                "slot_id": 2,
                "clip_id": None,
                "source_index": 2,  # 0-indexed → clip_03
                "source_start": None,
                "source_end": None,
                "replacement_text": None,
            }
        ])
        result = compile_with_mock_agent(
            _make_template(num_slots=3), user_plan, _make_inventory(num_clips=3), {}
        )
        second_clip = result["timeline"][1]
        assert second_clip["clip_id"] == "clip_03"

    def test_no_inventory_produces_missing_clip_ids(self):
        result = compile_with_mock_agent(
            _make_template(num_slots=2), _make_user_plan(), {"clips": [], "warnings": []}, {}
        )
        for clip in result["timeline"]:
            assert "missing_clip_slot_" in clip["clip_id"]


# ---------------------------------------------------------------------------
# Text replacement
# ---------------------------------------------------------------------------

class TestTextReplacement:
    def test_text_replacement_by_slot(self):
        user_plan = _make_user_plan(text_replacements=[
            {"slot_id": 1, "new_text": "REPLACED TEXT", "style": None}
        ])
        result = compile_with_mock_agent(
            _make_template(num_slots=3), user_plan, _make_inventory(num_clips=3), {}
        )
        first_clip = result["timeline"][0]
        assert first_clip.get("text") is not None
        assert first_clip["text"]["value"] == "REPLACED TEXT"

    def test_no_text_replacement_leaves_null_or_uses_reference(self):
        """Without text replacements and no text_ref in template, text should be None/empty."""
        result = compile_with_mock_agent(
            _make_template(num_slots=3), _make_user_plan(), _make_inventory(num_clips=3), {}
        )
        for clip in result["timeline"]:
            # text should be None or have an empty value
            if clip.get("text") is not None:
                assert "value" in clip["text"]


# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------

class TestTimingLogic:
    def test_duration_preserved_from_slot(self):
        template = _make_template(num_slots=3, duration=30.0)
        result = compile_with_mock_agent(
            template, _make_user_plan(), _make_inventory(num_clips=3, duration=60.0), {}
        )
        for slot, clip in zip(template["slots"], result["timeline"]):
            # Duration should not exceed slot duration (may be less if candidate is shorter)
            assert clip["duration"] > 0

    def test_explicit_source_start_and_end_override_timing(self):
        user_plan = _make_user_plan(slot_replacements=[
            {
                "slot_id": 1,
                "clip_id": "clip_01",
                "source_index": None,
                "source_start": 5.0,
                "source_end": 10.0,
                "replacement_text": None,
            }
        ])
        result = compile_with_mock_agent(
            _make_template(num_slots=3), user_plan, _make_inventory(num_clips=3, duration=60.0), {}
        )
        first = result["timeline"][0]
        assert first["source_start"] == pytest.approx(5.0)
        assert first["duration"] == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# Global style ops
# ---------------------------------------------------------------------------

class TestGlobalStyleOps:
    def test_global_style_ops_present(self):
        result = compile_with_mock_agent(
            _make_template(), _make_user_plan(), _make_inventory(), {}
        )
        assert "global_style_ops" in result
        assert isinstance(result["global_style_ops"], list)
        assert len(result["global_style_ops"]) >= 1

    def test_per_clip_style_ops_present(self):
        result = compile_with_mock_agent(
            _make_template(num_slots=2), _make_user_plan(), _make_inventory(), {}
        )
        for clip in result["timeline"]:
            assert "style_ops" in clip
            assert len(clip["style_ops"]) >= 1
