from __future__ import annotations

import argparse
import json
from pathlib import Path

from ai_editor.vision_template.frame_sampler import sample_video_frames

from .edit_event_classifier import classify_semantic_edit_events
from .layer_stack import build_layer_stack
from .object_detector import detect_objects
from .object_segmenter import segment_objects
from .object_tracker import track_objects
from .scene_graph import build_semantic_video_graph
from .schemas import SemanticEditVerification, SemanticVideoGraph
from .synthetic_objects import generate_synthetic_object_video
from .verifier import verify_object_edit


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _analyze_video(video_path: str, out_dir: Path, backend: str, text_queries: list[str] | None = None) -> SemanticVideoGraph:
    sampled = sample_video_frames(video_path, fps=8.0, size=224)
    detections = detect_objects(sampled.frames, sampled.timestamps, text_queries=text_queries, backend=backend)
    segment_objects(sampled.frames, detections, backend="bbox_mask")
    tracks = track_objects(detections, sampled.timestamps)
    layers = build_layer_stack(tracks)
    graph = build_semantic_video_graph(video_path, sampled.frames, sampled.timestamps, detections, tracks, layers)
    classify_semantic_edit_events(graph)
    graph.to_json_file(out_dir / "semantic_video_graph.json")
    return graph


def _cmd_synthetic_demo(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    video_path, graph = generate_synthetic_object_video(str(out_dir), scenario=args.scenario, fps=args.fps, size=(args.size, args.size), seed=args.seed)
    graph.to_json_file(out_dir / "semantic_video_graph.json")
    print(json.dumps({"video": video_path, "objects": len(graph.objects), "events": len(graph.edit_events)}, indent=2))
    return 0


def _cmd_analyze(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    graph = _analyze_video(args.video, out_dir, backend=args.backend, text_queries=args.text_queries)
    print(json.dumps({"objects": len(graph.objects), "layers": len(graph.layers), "events": len(graph.edit_events)}, indent=2))
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    before = SemanticVideoGraph.from_json_file(args.before)
    after = SemanticVideoGraph.from_json_file(args.after)
    verification = verify_object_edit(before, after, args.instruction, target_object_label=args.target_object_label)
    verification.to_json_file(args.out)
    print(json.dumps(verification.model_dump() if hasattr(verification, "model_dump") else verification.dict(), indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m ai_editor.semantic_edit.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    synth = sub.add_parser("synthetic-demo")
    synth.add_argument("--out", required=True)
    synth.add_argument("--scenario", required=True)
    synth.add_argument("--fps", type=int, default=12)
    synth.add_argument("--size", type=int, default=224)
    synth.add_argument("--seed", type=int, default=0)
    synth.set_defaults(func=_cmd_synthetic_demo)

    analyze = sub.add_parser("analyze")
    analyze.add_argument("--video", required=True)
    analyze.add_argument("--out", required=True)
    analyze.add_argument("--backend", default="synthetic_color")
    analyze.add_argument("--text-queries", nargs="*", default=None)
    analyze.set_defaults(func=_cmd_analyze)

    verify = sub.add_parser("verify")
    verify.add_argument("--before", required=True)
    verify.add_argument("--after", required=True)
    verify.add_argument("--instruction", required=True)
    verify.add_argument("--out", required=True)
    verify.add_argument("--target-object-label", default=None)
    verify.set_defaults(func=_cmd_verify)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
