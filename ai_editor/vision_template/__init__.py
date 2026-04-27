from .schemas import (
    CropSpec,
    EditSlot,
    EditTemplate,
    GlobalStyle,
    MotionSpec,
    OverlaySpec,
    SlotMapping,
    SlotMappingItem,
    TrainingSummary,
    validate_monotonic_slots,
    validate_slot_mapping,
)


class VisionTemplateError(RuntimeError):
    """Raised when the experimental vision-template workflow cannot proceed."""


__all__ = [
    "CropSpec",
    "EditSlot",
    "EditTemplate",
    "GlobalStyle",
    "MotionSpec",
    "OverlaySpec",
    "SlotMapping",
    "SlotMappingItem",
    "TrainingSummary",
    "VisionTemplateError",
    "validate_monotonic_slots",
    "validate_slot_mapping",
]
