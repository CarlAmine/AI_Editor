# Pipeline State & Artifacts

This document describes the stage-based runner and artifact registry used by the video pipeline.

## Job Directory Layout

Each job is stored under:

`tmp/jobs/<job_id>/`

Containing:

- `state.json`
- `artifacts.json`
- `plans/`
- `media/`
- `outputs/`
- `logs/`
- `debug/`

## Stages

Stages are tracked in `state.json`:

- `INGEST`
- `FETCH_PRIMARY`
- `ANALYZE_PRIMARY`
- `FETCH_SOURCES`
- `ALIGN_SOURCES`
- `AUDIO_PLAN`
- `RENDER_PLAN`
- `SHOTSTACK_RENDER`
- `POSTPROCESS`
- `PUBLISH`
- `CLEANUP`

Each stage has status:

- `PENDING`
- `RUNNING`
- `SUCCEEDED`
- `FAILED`
- `SKIPPED`

## Artifact Keys

Minimum key conventions:

- `primary.video`
- `analysis.json`
- `analysis.summary`
- `sources.raw.<n>`
- `sources.aligned.<n>`
- `audio.soundtrack`
- `render.master_16x9`
- `render.short_9x16`

Additional keys may be present (e.g. `sources.fetch.<n>`, `render.shotstack_url`).

## Plans

Plan JSON files are written to `plans/`:

- `overlay_plan.json`
- `timeline_plan.json`
- `audio_plan.json`
- `render_spec.json`
- `postprocess_plan.json`

Execution stages consume these plans.

## Generation Modes

Two explicit render modes are supported:

- `free_generation_mode`
- `reference_mimic_mode`

### Free Generation Mode

- Existing flexible behavior.
- Scene timing and overlays can be adapted from available source clips and prompt/script choices.

### Reference Mimic Mode

- The analyzed video timeline is canonical.
- A normalized timeline object is built and saved to `plans/canonical_timeline.json`.
- Each output scene maps 1:1 with analyzed scenes (`scene_id`, `start`, `end`, `duration`).
- Overlay windows are saved to `plans/overlay_timing.json` and are consumed directly by render assembly.
- If `music_mode=original`, the primary/analyzed video audio can be extracted as the final audio bed while source-clip audio is muted.

Canonical timeline shape:

```json
[
  {
    "scene_id": 1,
    "start": 0.0,
    "end": 2.4,
    "duration": 2.4,
    "video_src": "https://...",
    "text": "Top 10 Nature",
    "text_start": 0.0,
    "text_end": 2.4
  }
]
```

## Mimic Validation

Before render in `reference_mimic_mode`, validation checks:

- generated scene count equals analyzed scene count
- every generated duration matches analyzed duration within tolerance
- total generated duration matches analyzed total duration
- overlay timing windows are valid/non-negative and not unintentionally overlapping
- when reference audio bed is used, audio duration matches timeline duration

If validation fails, the pipeline does not render and records structured errors in `state.json`.

## Idempotency

Stages skip work if done criteria are already met (artifacts/plans exist and are valid).
Re-running the same `job_id` reuses existing outputs where possible.

## Warnings and Errors

State includes structured arrays:

- `warnings[]`: `{code, message, detail}`
- `errors[]`: `{stage, code, message, detail}`

Legacy response fields (`user_notice`, `ffmpeg_error`) are derived from warnings for backward compatibility.
