from ai_editor.vision_template.metrics import boundary_precision_recall_with_tolerance, decode_confidence_summary
from ai_editor.vision_template.schemas import CropSpec, EditSlot, EditTemplate, GlobalStyle, MotionSpec


def _template(boundaries: list[tuple[float, float, float]]) -> EditTemplate:
    slots = [
        EditSlot(
            slot_id=index + 1,
            start=start,
            end=end,
            duration=duration,
            boundary_confidence=0.7,
            motion=MotionSpec(kind="static", confidence=1.0),
            crop=CropSpec(),
        )
        for index, (start, end, duration) in enumerate(boundaries)
    ]
    return EditTemplate(
        version="0.1",
        fps=8.0,
        total_duration=boundaries[-1][1],
        slots=slots,
        global_style=GlobalStyle(avg_slot_duration=1.0, rhythm=[slot.duration for slot in slots], pacing_label="medium", dominant_transition="cut"),
        warnings=[],
    )


def test_metrics_boundary_precision_recall():
    pred = _template([(0.0, 1.1, 1.1), (1.1, 2.1, 1.0), (2.1, 3.0, 0.9)])
    target = _template([(0.0, 1.0, 1.0), (1.0, 2.0, 1.0), (2.0, 3.0, 1.0)])
    metrics = boundary_precision_recall_with_tolerance(pred, target, tolerance=0.2)

    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0


def test_decode_confidence_summary_reports_fallback():
    template = _template([(0.0, 1.0, 1.0), (1.0, 2.0, 1.0)])
    template.warnings.append("decoder_fallback_used")
    summary = decode_confidence_summary(template)
    assert summary["fallback_used"] is True
