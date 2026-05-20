from ai_editor.chatbot_interface import _extract_generation_mode
from ai_editor.generation_modes import normalize_generation_mode
from pipeline.state import new_state


def test_normalize_generation_mode_maps_reference_vision_alias():
    assert normalize_generation_mode("reference_vision_mode") == "reference_style_transfer"


def test_normalize_generation_mode_maps_reference_mimic_alias():
    assert normalize_generation_mode("reference_mimic_mode") == "reference_style_transfer"


def test_extract_generation_mode_detects_copy_style_language():
    assert _extract_generation_mode("please copy the style of the reference") == "reference_style_transfer"


def test_extract_generation_mode_detects_replicate_edit_language():
    assert _extract_generation_mode("replicate this edit on my clips") == "reference_style_transfer"


def test_job_state_is_vision_mode_for_reference_style_transfer():
    state = new_state(
        "job-1",
        input_summary={"primary_url": "https://example.com/ref.mp4", "sources_count": 1},
        requirements={"generation_mode": "reference_style_transfer"},
    )
    assert state.is_vision_mode() is True
