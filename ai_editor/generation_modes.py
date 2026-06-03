from __future__ import annotations

from typing import Optional

FREE_GENERATION_MODE = "free_generation_mode"
REFERENCE_STYLE_TRANSFER_MODE = "reference_style_transfer"
VISION_TEMPLATE_LEARNING_MODE = "vision_template_learning"

REFERENCE_EDIT_AGENT_MODE = "reference_edit_agent"

_STYLE_TRANSFER_ALIASES = {
    "reference_style_transfer",
    "reference_vision_mode",
    "reference vision mode",
    "reference vision",
    "reference mimic mode",
    "reference mimic",
    "reference_mimic_mode",
    "replicate edit",
    "replicate the edit",
    "replicate this edit",
    "copy style",
    "copy the style",
    "copy editing style",
    "copy the editing style",
    "match reference",
    "match the reference",
    "same edit",
    "same edit style",
    "same style",
    "use reference style",
    "vision mode",
}

_FREE_GENERATION_ALIASES = {
    FREE_GENERATION_MODE,
    "free generation mode",
    "free generation",
    "free mode",
}

_VISION_TEMPLATE_ALIASES = {
    VISION_TEMPLATE_LEARNING_MODE,
    "vision template learning",
    "template learning",
    "learn template",
    "learn a template",
    "train template",
    "train a template",
    "train model",
    "learn model",
}

_REFERENCE_EDIT_AGENT_ALIASES = {
    REFERENCE_EDIT_AGENT_MODE,
    "edit agent",
    "editing agent",
    "trained editing agent",
    "reference edit learning",
    "edit dna transfer",
    "template edit agent",
    "plan to edit graph",
}


def normalize_generation_mode(
    value: Optional[str],
    *,
    default: str = FREE_GENERATION_MODE,
) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return default
    if normalized in _STYLE_TRANSFER_ALIASES:
        return REFERENCE_STYLE_TRANSFER_MODE
    if normalized in _VISION_TEMPLATE_ALIASES:
        return VISION_TEMPLATE_LEARNING_MODE
    if normalized in _REFERENCE_EDIT_AGENT_ALIASES:
        return REFERENCE_EDIT_AGENT_MODE
    if normalized in _FREE_GENERATION_ALIASES:
        return FREE_GENERATION_MODE
    return default


def is_reference_style_transfer_mode(value: Optional[str]) -> bool:
    return normalize_generation_mode(value, default="") == REFERENCE_STYLE_TRANSFER_MODE


def is_vision_mode(value: Optional[str]) -> bool:
    normalized = normalize_generation_mode(value, default="")
    return normalized in {REFERENCE_STYLE_TRANSFER_MODE, VISION_TEMPLATE_LEARNING_MODE, REFERENCE_EDIT_AGENT_MODE}


NEURAL_STYLE_TRANSFER_MODE = "neural_style_transfer"
