from __future__ import annotations
import pytest
from ai_editor.generation_modes import (
    REFERENCE_EDIT_AGENT_MODE,
    normalize_generation_mode,
    is_vision_mode,
)

def test_reference_edit_agent_mode_normalization():
    aliases = [
        "reference_edit_agent",
        "edit agent",
        "editing agent",
        "trained editing agent",
        "reference edit learning",
        "edit dna transfer",
        "template edit agent",
        "plan to edit graph",
        "REFERENCE_EDIT_AGENT",
        "  edit agent  ",
    ]
    for alias in aliases:
        assert normalize_generation_mode(alias) == REFERENCE_EDIT_AGENT_MODE

def test_reference_edit_agent_mode_is_vision_mode():
    assert is_vision_mode(REFERENCE_EDIT_AGENT_MODE)
    assert is_vision_mode("edit agent")
    assert is_vision_mode("plan to edit graph")
