from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .frame_sampler import sample_video_frames
from .metrics import (
    boundary_precision_recall_with_tolerance,
    boundary_time_mae,
    decode_confidence_summary,
    duration_mae,
    rhythm_correlation,
    slot_count_error,
    timeline_validity_score,
    total_duration_error,
)
from .renderer_adapter import build_render_spec_from_vision_template
from .schemas import EditTemplate, SlotMapping, validate_monotonic_slots, validate_slot_mapping
from .train_reference import train_reference_adapter


@dataclass
class VisionTemplateBenchmarkCase:
    case_id: str
    case_dir: str
    reference_path: str
    slot_mapping_path: Optional[str] = None
    ground_truth_template_path: Optional[str] = None
    replacement_paths: List[str] = field(default_factory=list)
    notes_path: Optional[str] = None


@dataclass
class VisionTemplateBenchmarkResult:
    case_id: str
    passed: bool
    case_dir: str
    output_dir: str
    metrics: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None


def _write_json(path: str | Path, payload: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def load_ground_truth_template(path: str) -> EditTemplate:
    template = EditTemplate.from_json_file(path)
    validate_monotonic_slots(template)
    slot_ids = [int(slot.slot_id) for slot in template.slots]
    if len(slot_ids) != len(set(slot_ids)):
        raise ValueError("Ground-truth template slot IDs must be unique.")
    if template.total_duration <= 0:
        raise ValueError("Ground-truth template total_duration must be positive.")
    return template


def _stable_metrics(predicted: EditTemplate, target: EditTemplate, canonical_timeline: list[dict]) -> dict:
    pr_05 = boundary_precision_recall_with_tolerance(predicted, target, tolerance=0.5)
    pr_10 = boundary_precision_recall_with_tolerance(predicted, target, tolerance=1.0)
    confidence = decode_confidence_summary(predicted)
    return {
        "slot_count_error": slot_count_error(predicted, target),
        "total_duration_error": round(total_duration_error(predicted, target), 4),
        "duration_mae": round(duration_mae(predicted, target), 4),
        "boundary_time_mae": round(boundary_time_mae(predicted, target), 4),
        "boundary_precision_05s": round(pr_05["precision"], 4),
        "boundary_recall_05s": round(pr_05["recall"], 4),
        "boundary_precision_1s": round(pr_10["precision"], 4),
        "boundary_recall_1s": round(pr_10["recall"], 4),
        "rhythm_correlation": round(rhythm_correlation(predicted, target), 4),
        "mean_boundary_confidence": round(confidence["mean_boundary_confidence"], 4),
        "fallback_used": bool(confidence["fallback_used"]),
        "timeline_valid": timeline_validity_score(canonical_timeline) >= 0.99,
    }


def discover_real_benchmark_cases(benchmark_dir: str) -> list[VisionTemplateBenchmarkCase]:
    root = Path(benchmark_dir)
    if not root.exists():
        return []
    cases: list[VisionTemplateBenchmarkCase] = []
    for child in sorted(path for path in root.iterdir() if path.is_dir()):
        reference_path = child / "reference.mp4"
        replacement_paths = sorted(str(path) for path in child.glob("replacement_*.mp4"))
        cases.append(
            VisionTemplateBenchmarkCase(
                case_id=child.name,
                case_dir=str(child),
                reference_path=str(reference_path),
                slot_mapping_path=str(child / "slot_mapping.json") if (child / "slot_mapping.json").exists() else None,
                ground_truth_template_path=str(child / "ground_truth_template.json") if (child / "ground_truth_template.json").exists() else None,
                replacement_paths=replacement_paths,
                notes_path=str(child / "notes.md") if (child / "notes.md").exists() else None,
            )
        )
    return cases


def _load_slot_mapping(case: VisionTemplateBenchmarkCase, template: EditTemplate) -> SlotMapping:
    if not case.slot_mapping_path or not os.path.exists(case.slot_mapping_path):
        raise ValueError("Missing slot_mapping.json for benchmark case.")
    mapping = SlotMapping.from_json_file(case.slot_mapping_path)
    validate_slot_mapping(template, mapping)
    return mapping


def _validate_ground_truth_against_reference(case: VisionTemplateBenchmarkCase, template: EditTemplate, warnings: List[str]) -> None:
    sampled = sample_video_frames(case.reference_path, fps=max(float(template.fps), 1.0), size=64)
    if abs(float(sampled.duration) - float(template.total_duration)) > 1.0:
        warnings.append(
            f"Ground-truth total duration differs from reference by more than 1s "
            f"({template.total_duration:.3f}s vs {sampled.duration:.3f}s)."
        )


def run_real_benchmark_case(
    case: VisionTemplateBenchmarkCase,
    out_dir: str,
    config: dict,
) -> VisionTemplateBenchmarkResult:
    case_out_dir = Path(out_dir) / case.case_id
    case_out_dir.mkdir(parents=True, exist_ok=True)
    warnings: List[str] = []

    try:
        if not os.path.exists(case.reference_path):
            raise ValueError("Missing reference.mp4 for benchmark case.")
        if not case.ground_truth_template_path or not os.path.exists(case.ground_truth_template_path):
            raise ValueError("Missing ground_truth_template.json for benchmark case.")

        ground_truth = load_ground_truth_template(case.ground_truth_template_path)
        _validate_ground_truth_against_reference(case, ground_truth, warnings)
        mapping = _load_slot_mapping(case, ground_truth)

        result = train_reference_adapter(
            reference_video_path=case.reference_path,
            out_dir=str(case_out_dir),
            epochs=int(config.get("epochs", 8) or 8),
            fps=float(config.get("fps", ground_truth.fps or 8.0) or 8.0),
            size=int(config.get("size", 224) or 224),
            device=str(config.get("device", "auto") or "auto"),
            max_seconds=config.get("max_seconds"),
            expected_slots=int(config.get("expected_slots") or len(ground_truth.slots) or 0) or None,
            use_pretrained_backbone=bool(config.get("use_pretrained_backbone", False)),
            synthetic_pretrain=bool(config.get("synthetic_pretrain", False)),
            synthetic_pretrain_samples=int(config.get("synthetic_pretrain_samples", 16) or 16),
            synthetic_pretrain_epochs=int(config.get("synthetic_pretrain_epochs", 1) or 1),
        )

        predicted_path = case_out_dir / "predicted_edit_template.json"
        result.template.to_json_file(predicted_path)
        ground_truth.to_json_file(case_out_dir / "ground_truth_template.json")
        mapping.to_json_file(case_out_dir / "slot_mapping.json")

        canonical_timeline, overlay_timing, edit_summary = build_render_spec_from_vision_template(
            result.template,
            mapping,
            source_artifacts={},
            requirements={"generation_mode": "vision_template_learning"},
        )
        _write_json(
            case_out_dir / "canonical_timeline.json",
            {"timeline": canonical_timeline, "overlay_timing": overlay_timing, "edit_summary": edit_summary},
        )

        metrics = _stable_metrics(result.template, ground_truth, canonical_timeline)
        metrics["case_id"] = case.case_id
        _write_json(case_out_dir / "metrics.json", metrics)
        summary_payload = {"warnings": list(result.template.warnings), "benchmark_warnings": warnings}
        _write_json(case_out_dir / "warnings.json", summary_payload)

        training_summary_payload = {}
        if result.template.training_summary is not None:
            training_summary_payload = (
                result.template.training_summary.model_dump()
                if hasattr(result.template.training_summary, "model_dump")
                else result.template.training_summary.dict()
            )
        _write_json(case_out_dir / "training_summary.json", training_summary_payload)
        return VisionTemplateBenchmarkResult(
            case_id=case.case_id,
            passed=True,
            case_dir=case.case_dir,
            output_dir=str(case_out_dir),
            metrics=metrics,
            warnings=list(result.template.warnings) + warnings,
        )
    except Exception as exc:
        failure_metrics = {
            "case_id": case.case_id,
            "timeline_valid": False,
            "slot_count_error": None,
            "total_duration_error": None,
            "duration_mae": None,
            "boundary_time_mae": None,
            "boundary_precision_05s": None,
            "boundary_recall_05s": None,
            "boundary_precision_1s": None,
            "boundary_recall_1s": None,
            "rhythm_correlation": None,
            "mean_boundary_confidence": None,
            "fallback_used": None,
        }
        _write_json(case_out_dir / "metrics.json", failure_metrics)
        _write_json(case_out_dir / "warnings.json", {"warnings": warnings, "error": str(exc)})
        return VisionTemplateBenchmarkResult(
            case_id=case.case_id,
            passed=False,
            case_dir=case.case_dir,
            output_dir=str(case_out_dir),
            metrics=failure_metrics,
            warnings=warnings,
            error=str(exc),
        )


def run_real_benchmark_suite(
    benchmark_dir: str,
    out_dir: str,
    config: dict,
) -> dict:
    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    cases = discover_real_benchmark_cases(benchmark_dir)
    results = [run_real_benchmark_case(case, str(out_root), config) for case in cases]

    successful = [result for result in results if result.passed]
    warnings_count = sum(len(result.warnings) for result in results) + sum(1 for result in results if result.error)

    def _mean(key: str) -> Optional[float]:
        values = [float(result.metrics[key]) for result in successful if result.metrics.get(key) is not None]
        if not values:
            return None
        return round(sum(values) / len(values), 4)

    aggregate = {
        "cases_total": len(results),
        "cases_passed": len(successful),
        "cases_failed": len(results) - len(successful),
        "warnings_count": warnings_count,
        "mean_duration_mae": _mean("duration_mae"),
        "mean_boundary_time_mae": _mean("boundary_time_mae"),
        "mean_boundary_precision_05s": _mean("boundary_precision_05s"),
        "mean_boundary_recall_05s": _mean("boundary_recall_05s"),
        "mean_boundary_precision_1s": _mean("boundary_precision_1s"),
        "mean_boundary_recall_1s": _mean("boundary_recall_1s"),
        "mean_rhythm_correlation": _mean("rhythm_correlation"),
        "results": [
            {
                "case_id": result.case_id,
                "passed": result.passed,
                "metrics": result.metrics,
                "warnings": result.warnings,
                "error": result.error,
            }
            for result in results
        ],
    }
    _write_json(out_root / "aggregate_metrics.json", aggregate)

    report_lines = [
        "# Vision Template Real-Video Evaluation",
        "",
        f"- Cases total: {aggregate['cases_total']}",
        f"- Cases passed: {aggregate['cases_passed']}",
        f"- Cases failed: {aggregate['cases_failed']}",
        f"- Warnings count: {aggregate['warnings_count']}",
        "",
        "## Per-case Results",
        "",
    ]
    for result in results:
        report_lines.append(f"### {result.case_id}")
        report_lines.append(f"- Passed: {result.passed}")
        if result.error:
            report_lines.append(f"- Error: {result.error}")
        for key in (
            "duration_mae",
            "boundary_time_mae",
            "boundary_precision_05s",
            "boundary_recall_05s",
            "boundary_precision_1s",
            "boundary_recall_1s",
            "rhythm_correlation",
        ):
            if result.metrics.get(key) is not None:
                report_lines.append(f"- {key}: {result.metrics[key]}")
        if result.warnings:
            report_lines.append(f"- Warnings: {len(result.warnings)}")
        report_lines.append("")
    (out_root / "report.md").write_text("\n".join(report_lines), encoding="utf-8")
    return aggregate
