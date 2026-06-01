#!/usr/bin/env python3
"""Print diagnostics for the latest tmp/jobs render job."""

from __future__ import annotations

import json
from pathlib import Path


def _load(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    jobs_root = Path("tmp/jobs")
    if not jobs_root.exists():
        print("No tmp/jobs directory found.")
        return

    job_dirs = sorted(
        [path for path in jobs_root.iterdir() if path.is_dir()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not job_dirs:
        print("No job directories found under tmp/jobs.")
        return

    job_dir = job_dirs[0]
    print(f"job_id: {job_dir.name}")

    for relative in (
        "plans/render_spec.json",
        "plans/canonical_timeline.json",
        "plans/overlay_timing.json",
        "plans/reference_summary.json",
        "plans/reference_slots.json",
        "debug/render_filter_plan.json",
        "debug/ffmpeg_commands.json",
        "ffmpeg/concat.txt",
    ):
        path = job_dir / relative
        payload = _load(path)
        if payload is None and not path.exists():
            continue
        print(f"\n== {relative} ==")
        if path.suffix == ".txt":
            print(path.read_text(encoding="utf-8"))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False)[:4000])

    outputs = job_dir / "outputs"
    if outputs.exists():
        print("\n== outputs ==")
        for item in outputs.iterdir():
            print(item)


if __name__ == "__main__":
    main()
