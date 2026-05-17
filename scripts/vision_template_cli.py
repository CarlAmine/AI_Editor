from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.benchmark_real import run_real_benchmark_suite
from scripts.generate_synthetic import generate_synthetic_edit_sample
from scripts.vision_template_metrics import (
    boundary_precision_recall_with_tolerance,
    boundary_time_mae,
    decode_confidence_summary,
    duration_mae,
    rhythm_correlation,
    slot_count_error,
    timeline_validity_score,
    total_duration_error,
)
from ai_editor.vision_template.renderer_adapter import build_render_spec_from_vision_template
from ai_editor.vision_template.schemas import EditTemplate, SlotMapping
from ai_editor.vision_template.train_reference import train_reference_adapter


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _parse_bool(value):
    if isinstance(value, bool):
        return value
    lowered = str(value or "").strip().lower()
    if lowered in {"1", "true", "yes", "y", "on"}:
        return True
    if lowered in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean value: {value}")


def _metrics_payload(template: EditTemplate, ground_truth: EditTemplate, canonical_timeline: list[dict]) -> dict:
    pr = boundary_precision_recall_with_tolerance(template, ground_truth, tolerance=0.5)
    confidence = decode_confidence_summary(template)
    return {
        "slot_count_error": slot_count_error(template, ground_truth),
        "total_duration_error": round(total_duration_error(template, ground_truth), 4),
        "duration_mae": round(duration_mae(template, ground_truth), 4),
        "boundary_time_mae": round(boundary_time_mae(template, ground_truth), 4),
        "rhythm_correlation": round(rhythm_correlation(template, ground_truth), 4),
        "boundary_precision_05s": round(pr["precision"], 4),
        "boundary_recall_05s": round(pr["recall"], 4),
        "mean_boundary_confidence": round(confidence["mean_boundary_confidence"], 4),
        "fallback_used": bool(confidence["fallback_used"]),
        "timeline_valid": timeline_validity_score(canonical_timeline) >= 0.99,
    }


def _print_quality_summary(metrics_payload: dict) -> None:
    print(json.dumps(metrics_payload, indent=2))
    if (
        metrics_payload["duration_mae"] >= 0.75
        or metrics_payload["boundary_time_mae"] >= 1.0
        or metrics_payload["rhythm_correlation"] < 0.8
    ):
        print("warning: quality target not fully reached; consider quality-demo or stronger pretraining.")


def _cmd_generate_synthetic(args: argparse.Namespace) -> int:
    reference_path, template = generate_synthetic_edit_sample(
        args.out,
        num_slots=args.num_slots,
        fps=args.fps,
        size=(args.size, args.size),
        seed=args.seed,
    )
    print(json.dumps({"reference": reference_path, "slot_count": len(template.slots)}, indent=2))
    return 0


def _cmd_train_reference(args: argparse.Namespace) -> int:
    result = train_reference_adapter(
        reference_video_path=args.reference,
        out_dir=args.out,
        epochs=args.epochs,
        fps=args.fps,
        size=args.size,
        expected_slots=args.expected_slots,
        device=args.device,
        max_seconds=args.max_seconds,
        use_pretrained_backbone=args.use_pretrained_backbone,
        synthetic_pretrain=args.synthetic_pretrain,
        synthetic_pretrain_samples=args.synthetic_pretrain_samples,
        synthetic_pretrain_epochs=args.synthetic_pretrain_epochs,
    )
    print(json.dumps({"template_path": result.template_path, "slot_count": len(result.template.slots)}, indent=2))
    return 0


def _cmd_transfer(args: argparse.Namespace) -> int:
    template = EditTemplate.from_json_file(args.template)
    mapping = SlotMapping.from_json_file(args.slot_mapping)
    canonical_timeline, overlay_timing, edit_summary = build_render_spec_from_vision_template(
        template,
        mapping,
        source_artifacts={},
        requirements={"generation_mode": "vision_template_learning"},
    )
    payload = {
        "timeline": canonical_timeline,
        "overlay_timing": overlay_timing,
        "edit_summary": edit_summary,
    }
    _write_json(Path(args.out), payload)
    print(json.dumps({"segments": len(canonical_timeline), "out": args.out}, indent=2))
    return 0


def _run_demo(
    *,
    out_dir: Path,
    num_slots: int,
    adapt_epochs: int,
    fps: int,
    size: int,
    seed: int,
    device: str,
    synthetic_pretrain: bool,
    synthetic_pretrain_samples: int,
    synthetic_pretrain_epochs: int,
) -> dict:
    reference_path, ground_truth = generate_synthetic_edit_sample(
        str(out_dir),
        num_slots=num_slots,
        fps=fps,
        size=(size, size),
        seed=seed,
    )
    result = train_reference_adapter(
        reference_video_path=reference_path,
        out_dir=str(out_dir),
        epochs=adapt_epochs,
        fps=fps,
        size=size,
        expected_slots=num_slots,
        device=device,
        synthetic_pretrain=synthetic_pretrain,
        synthetic_pretrain_samples=synthetic_pretrain_samples,
        synthetic_pretrain_epochs=synthetic_pretrain_epochs,
    )
    mapping = SlotMapping.from_json_file(out_dir / "slot_mapping.json")
    canonical_timeline, overlay_timing, edit_summary = build_render_spec_from_vision_template(
        result.template,
        mapping,
        source_artifacts={},
        requirements={"generation_mode": "vision_template_learning"},
    )
    canonical_payload = {
        "timeline": canonical_timeline,
        "overlay_timing": overlay_timing,
        "edit_summary": edit_summary,
    }
    _write_json(out_dir / "canonical_timeline.json", canonical_payload)
    metrics_payload = _metrics_payload(result.template, ground_truth, canonical_timeline)
    _write_json(out_dir / "metrics.json", metrics_payload)
    _write_json(out_dir / "ground_truth_template.json", ground_truth.model_dump() if hasattr(ground_truth, "model_dump") else ground_truth.dict())
    _write_json(
        out_dir / "boundary_debug.json",
        {
            "predicted_boundaries": [float(slot.end) for slot in result.template.slots[:-1]],
            "ground_truth_boundaries": [float(slot.end) for slot in ground_truth.slots[:-1]],
            "warnings": list(result.template.warnings),
        },
    )
    return metrics_payload


def _cmd_smoke_demo(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    metrics_payload = _run_demo(
        out_dir=out_dir,
        num_slots=args.num_slots,
        adapt_epochs=args.epochs,
        fps=args.fps,
        size=args.size,
        seed=args.seed,
        device=args.device,
        synthetic_pretrain=args.synthetic_pretrain,
        synthetic_pretrain_samples=args.synthetic_pretrain_samples,
        synthetic_pretrain_epochs=args.synthetic_pretrain_epochs,
    )
    _print_quality_summary(metrics_payload)
    return 0


def _cmd_quality_demo(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    metrics_payload = _run_demo(
        out_dir=out_dir,
        num_slots=args.num_slots,
        adapt_epochs=args.adapt_epochs,
        fps=args.fps,
        size=args.size,
        seed=args.seed,
        device=args.device,
        synthetic_pretrain=True,
        synthetic_pretrain_samples=args.pretrain_samples,
        synthetic_pretrain_epochs=args.pretrain_epochs,
    )
    _print_quality_summary(metrics_payload)
    return 0


def _cmd_eval_real(args: argparse.Namespace) -> int:
    aggregate = run_real_benchmark_suite(
        args.benchmark_dir,
        args.out,
        {
            "epochs": args.epochs,
            "fps": args.fps,
            "size": args.size,
            "device": args.device,
            "max_seconds": args.max_seconds,
            "synthetic_pretrain": args.synthetic_pretrain,
            "synthetic_pretrain_samples": args.synthetic_pretrain_samples,
            "synthetic_pretrain_epochs": args.synthetic_pretrain_epochs,
            "use_pretrained_backbone": args.use_pretrained_backbone,
        },
    )
    print(json.dumps(aggregate, indent=2))
    return 0


def _cmd_init_real_benchmark_case(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    notes = """# Benchmark Notes

- Describe the reference edit intent here.
- Record any ambiguous transitions, crop behavior, or overlays.
- Note whether replacement clips are full-length or trimmed.
"""
    (out_dir / "notes.md").write_text(notes, encoding="utf-8")
    _write_json(
        out_dir / "slot_mapping.example.json",
        {
            "items": [
                {"slot_id": 1, "clip_id": "replacement_001", "clip_path": "replacement_001.mp4"},
                {"slot_id": 2, "clip_id": "replacement_002", "clip_path": "replacement_002.mp4"},
            ]
        },
    )
    _write_json(
        out_dir / "ground_truth_template.example.json",
        {
            "version": "0.1",
            "source_reference": "reference.mp4",
            "fps": 8.0,
            "total_duration": 4.0,
            "slots": [
                {
                    "slot_id": 1,
                    "start": 0.0,
                    "end": 1.5,
                    "duration": 1.5,
                    "transition_in": "cut",
                    "transition_out": "cut",
                    "motion": {"kind": "static", "confidence": 1.0, "keyframes": []},
                    "crop": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
                },
                {
                    "slot_id": 2,
                    "start": 1.5,
                    "end": 4.0,
                    "duration": 2.5,
                    "transition_in": "fade",
                    "transition_out": "fade",
                    "motion": {"kind": "zoom_in", "confidence": 1.0, "keyframes": []},
                    "crop": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
                },
            ],
            "global_style": {
                "avg_slot_duration": 2.0,
                "rhythm": [1.5, 2.5],
                "pacing_label": "medium",
                "dominant_transition": "cut",
            },
            "warnings": [],
        },
    )
    print(json.dumps({"out": str(out_dir)}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m scripts.vision_template_cli")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate-synthetic")
    gen.add_argument("--out", required=True)
    gen.add_argument("--num-slots", type=int, default=5)
    gen.add_argument("--fps", type=int, default=12)
    gen.add_argument("--size", type=int, default=224)
    gen.add_argument("--seed", type=int, default=0)
    gen.set_defaults(func=_cmd_generate_synthetic)

    train = sub.add_parser("train-reference")
    train.add_argument("--reference", required=True)
    train.add_argument("--out", required=True)
    train.add_argument("--epochs", type=int, default=5)
    train.add_argument("--fps", type=float, default=8.0)
    train.add_argument("--size", type=int, default=224)
    train.add_argument("--expected-slots", type=int, default=None)
    train.add_argument("--device", default="auto")
    train.add_argument("--max-seconds", type=float, default=None)
    train.add_argument("--use-pretrained-backbone", action="store_true")
    train.add_argument("--synthetic-pretrain", action="store_true")
    train.add_argument("--synthetic-pretrain-samples", type=int, default=16)
    train.add_argument("--synthetic-pretrain-epochs", type=int, default=1)
    train.set_defaults(func=_cmd_train_reference)

    transfer = sub.add_parser("transfer")
    transfer.add_argument("--template", required=True)
    transfer.add_argument("--slot-mapping", required=True)
    transfer.add_argument("--out", required=True)
    transfer.set_defaults(func=_cmd_transfer)

    smoke = sub.add_parser("smoke-demo")
    smoke.add_argument("--out", required=True)
    smoke.add_argument("--num-slots", type=int, default=5)
    smoke.add_argument("--epochs", type=int, default=3)
    smoke.add_argument("--fps", type=int, default=8)
    smoke.add_argument("--size", type=int, default=224)
    smoke.add_argument("--seed", type=int, default=0)
    smoke.add_argument("--device", default="auto")
    smoke.add_argument("--synthetic-pretrain", action="store_true", default=True)
    smoke.add_argument("--synthetic-pretrain-samples", type=int, default=16)
    smoke.add_argument("--synthetic-pretrain-epochs", type=int, default=1)
    smoke.set_defaults(func=_cmd_smoke_demo)

    quality = sub.add_parser("quality-demo")
    quality.add_argument("--out", required=True)
    quality.add_argument("--num-slots", type=int, default=5)
    quality.add_argument("--pretrain-samples", type=int, default=32)
    quality.add_argument("--pretrain-epochs", type=int, default=2)
    quality.add_argument("--adapt-epochs", type=int, default=8)
    quality.add_argument("--fps", type=int, default=8)
    quality.add_argument("--size", type=int, default=224)
    quality.add_argument("--seed", type=int, default=0)
    quality.add_argument("--device", default="auto")
    quality.set_defaults(func=_cmd_quality_demo)

    eval_real = sub.add_parser("eval-real")
    eval_real.add_argument("--benchmark-dir", required=True)
    eval_real.add_argument("--out", required=True)
    eval_real.add_argument("--epochs", type=int, default=8)
    eval_real.add_argument("--fps", type=float, default=8.0)
    eval_real.add_argument("--size", type=int, default=224)
    eval_real.add_argument("--device", default="auto")
    eval_real.add_argument("--max-seconds", type=float, default=None)
    eval_real.add_argument("--synthetic-pretrain", type=_parse_bool, default=True)
    eval_real.add_argument("--synthetic-pretrain-samples", type=int, default=32)
    eval_real.add_argument("--synthetic-pretrain-epochs", type=int, default=2)
    eval_real.add_argument("--use-pretrained-backbone", action="store_true")
    eval_real.set_defaults(func=_cmd_eval_real)

    init_case = sub.add_parser("init-real-benchmark-case")
    init_case.add_argument("--out", required=True)
    init_case.set_defaults(func=_cmd_init_real_benchmark_case)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
