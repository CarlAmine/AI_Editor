"""Tests for LLM-powered IntentParser."""
import pytest
from unittest.mock import patch, MagicMock

from ai_editor.editing.intent_parser import IntentParser
from ai_editor.editing.edit_operations import EditOperation


class TestIntentParser:

    def _mock_llm(self, return_value):
        """Helper that patches chat_json to return a fixed value."""
        return patch("ai_editor.editing.intent_parser.chat_json", return_value=return_value)

    def test_simple_remove_returns_remove_segment(self):
        parser = IntentParser()
        with self._mock_llm([{"operation": "remove_segment", "target": "shot_3",
                              "scope": "global", "segment_target": "shot_3"}]):
            ops = parser.parse("cut the third clip", {})
        assert len(ops) == 1
        assert ops[0].operation == "remove_segment"
        assert ops[0].target == "shot_3"

    def test_vague_instruction_returns_increase_pacing(self):
        parser = IntentParser()
        with self._mock_llm([{"operation": "increase_pacing", "scope": "opening",
                              "intensity": 0.8}]):
            ops = parser.parse("the intro feels too slow", {})
        assert len(ops) == 1
        assert ops[0].operation == "increase_pacing"
        assert ops[0].scope == "opening"

    def test_multiple_instructions_returns_multiple_ops(self):
        parser = IntentParser()
        with self._mock_llm([
            {"operation": "increase_pacing", "scope": "middle", "intensity": 0.9},
            {"operation": "set_clip_duration", "target": "shot_2", "scope": "global"},
        ]):
            ops = parser.parse(
                "make the energy pick up after the hook and faster cut between clips 2 and 4",
                {}
            )
        assert len(ops) == 2
        assert ops[0].operation == "increase_pacing"
        assert ops[1].operation == "set_clip_duration"

    def test_llm_returns_dict_wrapped_array_is_unwrapped(self):
        parser = IntentParser()
        with self._mock_llm({"operations": [
            {"operation": "remove_segment", "target": "shot_1", "scope": "opening"}
        ]}):
            ops = parser.parse("remove the intro", {})
        assert len(ops) == 1
        assert ops[0].operation == "remove_segment"

    def test_llm_failure_returns_custom_fallback(self):
        parser = IntentParser()
        with self._mock_llm(None):
            ops = parser.parse("do something weird", {})
        assert len(ops) == 1
        assert ops[0].operation == "custom"
        assert ops[0].metadata.get("unresolved") is True

    def test_time_window_parsed_correctly(self):
        parser = IntentParser()
        with self._mock_llm([{
            "operation": "trim_clip",
            "target": "shot_2",
            "scope": "global",
            "time_window": {"start": 2.0, "end": 5.0, "label": "explicit_range"},
        }]):
            ops = parser.parse("trim clip 2 between 2 and 5 seconds", {})
        assert ops[0].time_window is not None
        assert ops[0].time_window.start == 2.0
        assert ops[0].time_window.end == 5.0

    def test_vision_mode_instruction_detected(self):
        parser = IntentParser()
        with self._mock_llm([{
            "operation": "reference_vision_mode",
            "scope": "global",
            "value": "full_replication",
            "metadata": {"apply_motion_effects": True},
        }]):
            ops = parser.parse(
                "replicate the same edit style as the reference onto my clips",
                {"motion_effects_path": "/tmp/motion_effects.json"}
            )
        assert ops[0].operation == "reference_vision_mode"

    def test_plan_context_includes_shot_list(self):
        """Verifies that shot identifiers from the plan are included in context."""
        from ai_editor.editing.intent_parser import _build_plan_context
        state = {
            "current_plan": {
                "canonical_timeline": [
                    {"scene_id": 1, "duration": 3.4},
                    {"scene_id": 2, "duration": 2.1},
                    {"scene_id": 3, "duration": 4.8},
                ]
            }
        }
        context = _build_plan_context(state)
        assert "3 shots" in context
        assert "shot_1" in context
        assert "3.4" in context
