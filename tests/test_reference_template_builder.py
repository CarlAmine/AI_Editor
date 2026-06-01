"""
Unit tests for ai_editor.reference_learning.template_builder
"""
from __future__ import annotations

import pytest
from ai_editor.reference_learning.template_builder import build_reference_edit_template


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _minimal_analysis(num_scenes: int = 3, duration: float = 30.0) -> dict:
    scenes = []
    seg = duration / num_scenes
    for i in range(num_scenes):
        scenes.append({
            "scene_id": i + 1,
            "start_time": i * seg,
            "end_time": (i + 1) * seg,
            "duration": seg,
        })
    return {
        "metadata": {"duration_seconds": duration, "fps": 30.0, "width": 1080, "height": 1920},
        "scenes": scenes,
        "transitions": [],
        "style_profile": {"avg_shot_length": seg, "pacing_label": "moderate"},
        "motion_effects": {},
        "ocr_spans": [],
        "keyframes": [],
    }


# ---------------------------------------------------------------------------
# Structural tests
# ---------------------------------------------------------------------------

class TestBuildReferenceEditTemplateStructure:
    def test_returns_dict(self):
        analysis = _minimal_analysis()
        result = build_reference_edit_template(analysis, "/fake/video.mp4", "job_001")
        assert isinstance(result, dict)

    def test_required_top_level_keys(self):
        analysis = _minimal_analysis()
        result = build_reference_edit_template(analysis, "/fake/video.mp4", "job_001")
        for key in ("template_id", "source_video_path", "duration", "slots"):
            assert key in result, f"Missing key: {key}"

    def test_template_id_matches_job_id(self):
        analysis = _minimal_analysis()
        result = build_reference_edit_template(analysis, "/fake/video.mp4", "my_job")
        assert result["template_id"] == "my_job"

    def test_source_video_path_preserved(self):
        analysis = _minimal_analysis()
        result = build_reference_edit_template(analysis, "/path/to/clip.mp4", "job_002")
        assert result["source_video_path"] == "/path/to/clip.mp4"

    def test_slot_count_matches_scenes(self):
        for n in (1, 3, 5):
            analysis = _minimal_analysis(num_scenes=n)
            result = build_reference_edit_template(analysis, "/v.mp4", "j")
            assert len(result["slots"]) == n, f"Expected {n} slots, got {len(result['slots'])}"

    def test_slots_are_list_of_dicts(self):
        analysis = _minimal_analysis()
        result = build_reference_edit_template(analysis, "/v.mp4", "j")
        assert isinstance(result["slots"], list)
        for slot in result["slots"]:
            assert isinstance(slot, dict)


# ---------------------------------------------------------------------------
# Slot role assignment
# ---------------------------------------------------------------------------

class TestSlotRoles:
    def test_single_scene_is_hook_and_outro(self):
        analysis = _minimal_analysis(num_scenes=1)
        result = build_reference_edit_template(analysis, "/v.mp4", "j")
        slots = result["slots"]
        assert slots[0]["role"] == "hook"  # only scene → also first = hook

    def test_first_slot_is_hook(self):
        analysis = _minimal_analysis(num_scenes=4)
        result = build_reference_edit_template(analysis, "/v.mp4", "j")
        assert result["slots"][0]["role"] == "hook"

    def test_last_slot_is_outro(self):
        analysis = _minimal_analysis(num_scenes=4)
        result = build_reference_edit_template(analysis, "/v.mp4", "j")
        assert result["slots"][-1]["role"] == "outro"

    def test_middle_slots_are_main(self):
        analysis = _minimal_analysis(num_scenes=5)
        result = build_reference_edit_template(analysis, "/v.mp4", "j")
        for slot in result["slots"][1:-1]:
            assert slot["role"] == "main"

    def test_two_scene_roles(self):
        analysis = _minimal_analysis(num_scenes=2)
        result = build_reference_edit_template(analysis, "/v.mp4", "j")
        assert result["slots"][0]["role"] == "hook"
        assert result["slots"][1]["role"] == "outro"


# ---------------------------------------------------------------------------
# Slot timing
# ---------------------------------------------------------------------------

class TestSlotTiming:
    def test_slot_start_end_present(self):
        analysis = _minimal_analysis(num_scenes=3, duration=30.0)
        result = build_reference_edit_template(analysis, "/v.mp4", "j")
        for slot in result["slots"]:
            assert "start" in slot
            assert "end" in slot
            assert "duration" in slot

    def test_slot_timing_values(self):
        analysis = _minimal_analysis(num_scenes=3, duration=30.0)
        result = build_reference_edit_template(analysis, "/v.mp4", "j")
        slots = result["slots"]
        assert slots[0]["start"] == pytest.approx(0.0)
        assert slots[0]["end"] == pytest.approx(10.0)
        assert slots[1]["start"] == pytest.approx(10.0)
        assert slots[2]["end"] == pytest.approx(30.0)

    def test_duration_from_metadata(self):
        analysis = _minimal_analysis(duration=60.0)
        result = build_reference_edit_template(analysis, "/v.mp4", "j")
        assert result["duration"] == pytest.approx(60.0)

    def test_duration_fallback_from_scenes_when_no_metadata(self):
        analysis = _minimal_analysis(num_scenes=2, duration=20.0)
        del analysis["metadata"]
        result = build_reference_edit_template(analysis, "/v.mp4", "j")
        # Should be inferred from max end_time of scenes
        assert result["duration"] == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# Style tags
# ---------------------------------------------------------------------------

class TestStyleTags:
    def test_fast_pacing_tag_from_avg_shot_length(self):
        analysis = _minimal_analysis(num_scenes=10, duration=10.0)  # avg ~1s
        analysis["style_profile"]["avg_shot_length"] = 1.0
        result = build_reference_edit_template(analysis, "/v.mp4", "j")
        all_tags = {tag for slot in result["slots"] for tag in slot.get("style_tags", [])}
        assert "fast_pacing" in all_tags

    def test_short_form_tag_for_videos_under_60s(self):
        analysis = _minimal_analysis(duration=45.0)
        result = build_reference_edit_template(analysis, "/v.mp4", "j")
        all_tags = {tag for slot in result["slots"] for tag in slot.get("style_tags", [])}
        assert "short_form" in all_tags

    def test_no_short_form_tag_for_long_videos(self):
        analysis = _minimal_analysis(duration=120.0)
        result = build_reference_edit_template(analysis, "/v.mp4", "j")
        all_tags = {tag for slot in result["slots"] for tag in slot.get("style_tags", [])}
        assert "short_form" not in all_tags

    def test_dense_text_tag_with_many_ocr_spans(self):
        analysis = _minimal_analysis(num_scenes=3, duration=30.0)
        # Add > 5 OCR spans
        analysis["ocr_spans"] = [
            {"timestamp": float(i), "text": f"Text{i}"} for i in range(6)
        ]
        result = build_reference_edit_template(analysis, "/v.mp4", "j")
        all_tags = {tag for slot in result["slots"] for tag in slot.get("style_tags", [])}
        assert "dense_text" in all_tags


# ---------------------------------------------------------------------------
# OCR / keyframe text refs
# ---------------------------------------------------------------------------

class TestTextRefs:
    def test_ocr_span_attached_to_correct_slot(self):
        analysis = _minimal_analysis(num_scenes=3, duration=30.0)
        # Add OCR at t=5 → inside slot 1 (0–10)
        analysis["ocr_spans"] = [{"timestamp": 5.0, "text": "Hello"}]
        result = build_reference_edit_template(analysis, "/v.mp4", "j")
        slot1 = result["slots"][0]
        assert slot1["text_ref"] is not None
        assert "Hello" in slot1["text_ref"]["value"]

    def test_ocr_span_not_attached_to_wrong_slot(self):
        analysis = _minimal_analysis(num_scenes=3, duration=30.0)
        # OCR at t=5 → should NOT appear in slot 2 (10–20)
        analysis["ocr_spans"] = [{"timestamp": 5.0, "text": "Hello"}]
        result = build_reference_edit_template(analysis, "/v.mp4", "j")
        slot2 = result["slots"][1]
        assert slot2.get("text_ref") is None

    def test_keyframe_text_attached(self):
        analysis = _minimal_analysis(num_scenes=3, duration=30.0)
        analysis["keyframes"] = [{"timestamp": 15.0, "detected_text": "Frame; Text"}]
        result = build_reference_edit_template(analysis, "/v.mp4", "j")
        # Slot 2 spans 10–20 → t=15 is inside
        slot2 = result["slots"][1]
        assert slot2["text_ref"] is not None


# ---------------------------------------------------------------------------
# Metadata fields
# ---------------------------------------------------------------------------

class TestMetadataFields:
    def test_fps_propagated(self):
        analysis = _minimal_analysis()
        analysis["metadata"]["fps"] = 25.0
        result = build_reference_edit_template(analysis, "/v.mp4", "j")
        assert result.get("fps") == pytest.approx(25.0)

    def test_width_height_propagated(self):
        analysis = _minimal_analysis()
        analysis["metadata"]["width"] = 1920
        analysis["metadata"]["height"] = 1080
        result = build_reference_edit_template(analysis, "/v.mp4", "j")
        assert result["width"] == 1920
        assert result["height"] == 1080

    def test_style_profile_preserved(self):
        analysis = _minimal_analysis()
        analysis["style_profile"]["color_grade"] = "warm"
        result = build_reference_edit_template(analysis, "/v.mp4", "j")
        assert result["style_profile"]["color_grade"] == "warm"

    def test_empty_analysis_does_not_crash(self):
        result = build_reference_edit_template({}, "/v.mp4", "j")
        assert isinstance(result, dict)
        assert result["slots"] == []


# ---------------------------------------------------------------------------
# Transition mapping
# ---------------------------------------------------------------------------

class TestTransitions:
    def test_transition_hard_cut_default(self):
        analysis = _minimal_analysis(num_scenes=3, duration=30.0)
        result = build_reference_edit_template(analysis, "/v.mp4", "j")
        for slot in result["slots"]:
            assert slot["transition_out"]["type"] == "hard_cut"

    def test_named_transition_mapped_to_slot(self):
        analysis = _minimal_analysis(num_scenes=3, duration=30.0)
        analysis["transitions"] = [
            {"outgoing_shot_index": 0, "transition_type": "cross_dissolve", "duration": 0.5}
        ]
        result = build_reference_edit_template(analysis, "/v.mp4", "j")
        assert result["slots"][0]["transition_out"]["type"] == "cross_dissolve"
        assert result["slots"][0]["transition_out"]["duration"] == pytest.approx(0.5)
