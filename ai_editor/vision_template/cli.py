from __future__ import annotations

import argparse
import json
from pathlib import Path

from .metrics import (
    boundary_time_mae,
    duration_mae,
    rhythm_correlation,
    slot_count_error,
    timeline_validity_score,
    total_duration_error,
)
from .renderer_adapter import build_render_spec_from_vision_template
from .schemas import EditTemplate, SlotMapping
from .synthetic_dataset import generate_synthetic_edit_sample
from .train_reference import train_reference_adapter


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


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


def _cmd_smoke_demo(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    reference_path, ground_truth = generate_synthetic_edit_sample(
        str(out_dir),
        num_slots=args.num_slots,
        fps=args.fps,
        size=(args.size, args.size),
        seed=args.seed,
    )
    result = train_reference_adapter(
        reference_video_path=reference_path,
        out_dir=str(out_dir),
        epochs=args.epochs,
        fps=args.fps,
        size=args.size,
        expected_slots=args.num_slots,
        device=args.device,
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
    metrics_payload = {
        "slot_count_error": slot_count_error(result.template, ground_truth),
        "total_duration_error": round(total_duration_error(result.template, ground_truth), 4),
        "duration_mae": round(duration_mae(result.template, ground_truth), 4),
        "boundary_time_mae": round(boundary_time_mae(result.template, ground_truth), 4),
        "rhythm_correlation": round(rhythm_correlation(result.template, ground_truth), 4),
        "timeline_valid": timeline_validity_score(canonical_timeline) >= 0.99,
    }
    _write_json(out_dir / "metrics.json", metrics_payload)
    print(json.dumps(metrics_payload, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m ai_editor.vision_template.cli")
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
    smoke.set_defaults(func=_cmd_smoke_demo)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
