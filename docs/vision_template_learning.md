# Vision Template Learning

`vision_template_learning` is an experimental edit-replication mode that learns a reusable control template from a reference edited video and transfers that structure onto new replacement clips.

It does not generate new video pixels. It does not OCR text content. It does not use PySceneDetect as the core extractor. Instead, it samples raw frames, adapts a compact vision model on the reference edit, decodes a structured `EditTemplate`, and converts that template into the same canonical timeline and render-spec path the existing renderer already uses.

## What It Preserves

- Reference total duration
- Slot and shot rhythm
- Approximate cut timing
- Slot duration order
- Replacement clip order from `slot_mapping`
- Transition and motion metadata when inferable
- Overlay region and timing when inferable
- Aspect-ratio and crop behavior when inferable

## What It Does Not Do

- Exact pixel-level recreation
- OCR text recovery in this mode
- Hallucinated generative video
- Perfect recovery of invisible editor decisions from one reference alone

## How It Differs From `reference_mimic_mode`

`reference_mimic_mode` relies on existing deterministic analysis outputs and direct canonical timeline construction. `vision_template_learning` instead trains/adapts a compact vision model on the reference frames themselves, decodes a learned edit structure, and then transfers that structure to replacement clips.

## Request Shape

```json
{
  "primary_url": "https://example.com/reference.mp4",
  "sources": [
    {"id": "clip_1", "url": "https://example.com/a.mp4"},
    {"id": "clip_2", "url": "https://example.com/b.mp4"}
  ],
  "slot_mapping": [
    {"slot_id": 1, "clip_id": "clip_2"},
    {"slot_id": 2, "clip_id": "clip_1"}
  ],
  "requirements_state": {
    "generation_mode": "vision_template_learning",
    "expected_slots": 2,
    "vision_template": {
      "fps": 8.0,
      "size": 224,
      "epochs": 5,
      "device": "auto",
      "max_seconds": null,
      "use_pretrained_backbone": false
    }
  }
}
```

## CLI

Generate a synthetic sample:

```bash
python -m scripts.vision_template_cli generate-synthetic --out tmp/vision_synth --num-slots 5
```

Train on the synthetic reference:

```bash
python -m scripts.vision_template_cli train-reference --reference tmp/vision_synth/reference.mp4 --out tmp/vision_run --epochs 5 --expected-slots 5
```

Transfer a learned template to replacement clips:

```bash
python -m scripts.vision_template_cli transfer --template tmp/vision_run/edit_template.json --slot-mapping tmp/vision_synth/slot_mapping.json --out tmp/vision_run/canonical_timeline.json
```

Run the end-to-end smoke demo:

```bash
python -m scripts.vision_template_cli smoke-demo --out tmp/vision_demo --num-slots 5 --epochs 3
```

Run a slower quality-oriented demo with synthetic pretraining:

```bash
python -m scripts.vision_template_cli quality-demo --out tmp/vision_quality_demo --num-slots 5 --pretrain-samples 32 --pretrain-epochs 2 --adapt-epochs 8
```

Initialize a real benchmark case scaffold:

```bash
python -m scripts.vision_template_cli init-real-benchmark-case --out benchmarks/vision_template_real/example_001
```

Evaluate a directory of real benchmark cases:

```bash
python -m scripts.vision_template_cli eval-real --benchmark-dir benchmarks/vision_template_real --out tmp/vision_real_eval --epochs 8 --synthetic-pretrain true --synthetic-pretrain-samples 32 --synthetic-pretrain-epochs 2
```

## Model Quality Modes

`smoke-demo` is the fast structural proof:

- keeps runtime short
- runs a tiny CPU-safe model
- now uses lightweight synthetic pretraining by default to give the model a boundary prior
- is best for pipeline verification and quick regressions

`quality-demo` is the slower quality check:

- increases synthetic pretraining and adaptation time
- writes extra debug artifacts such as `boundary_debug.json`
- is the better benchmark for learned-template quality on the synthetic task

The tiny CPU model is still a prototype. Real-video quality will improve further with stronger optional pretrained video backbones or richer pretraining, but those are intentionally not required for the default path.

## Real-Video Benchmark Workflow

Create a benchmark case directory like:

```text
benchmarks/vision_template_real/
  example_001/
    reference.mp4
    replacement_001.mp4
    replacement_002.mp4
    replacement_003.mp4
    slot_mapping.json
    ground_truth_template.json
    notes.md
```

Use `ground_truth_template.json` with the existing `EditTemplate` schema. The minimum useful annotation is:

```json
{
  "version": "0.1",
  "source_reference": "reference.mp4",
  "fps": 8.0,
  "total_duration": 4.2,
  "slots": [
    {
      "slot_id": 1,
      "start": 0.0,
      "end": 1.6,
      "duration": 1.6,
      "transition_in": "cut",
      "transition_out": "cut",
      "motion": {"kind": "static", "confidence": 1.0, "keyframes": []},
      "crop": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}
    }
  ],
  "global_style": {
    "avg_slot_duration": 1.6,
    "rhythm": [1.6],
    "pacing_label": "medium",
    "dominant_transition": "cut"
  },
  "warnings": []
}
```

Run `eval-real` to:

1. discover all benchmark cases,
2. train/adapt on each `reference.mp4`,
3. decode a predicted template,
4. compare against `ground_truth_template.json`,
5. transfer the template to replacement clips,
6. write per-case outputs and aggregate metrics.

Interpret the metrics as a generalization check, not a guarantee of production readiness:

- `duration_mae` and `boundary_time_mae` show timing accuracy
- `boundary_precision_*` and `boundary_recall_*` show tolerance-based cut localization
- `rhythm_correlation` shows whether slot duration structure was preserved
- `fallback_used` indicates whether the decoder had to lean on safer priors

Strong synthetic metrics do not mean the same performance on real edited footage. Real-video evaluation is the bridge from pipeline credibility to actual model readiness.

## Artifacts Produced

- `vision_model.pt`
- `vision_template_raw_output.pt`
- `edit_template.json`
- `training_summary.json`
- `canonical_timeline.json`
- `metrics.json`

When run through the pipeline, the mode also writes the usual `render_spec.json`, `timeline_plan.json`, and canonical timeline artifacts under the job directory.

Stable pipeline artifact keys:

- `vision.template.model`
- `vision.template.json`
- `vision.template.raw_output`
- `vision.template.training_summary`
- `semantic.video_graph` when semantic attachment is enabled and succeeds

Job-plan sidecar files:

- `vision_template.json`
- `vision_template_timeline.json`
- `render_spec.json`
- `timeline_plan.json`

Smoke and quality demos also write:

- `ground_truth_template.json`
- `metrics.json`
- `boundary_debug.json`

Real benchmark evaluation writes:

- `aggregate_metrics.json`
- `report.md`
- per-case `predicted_edit_template.json`
- per-case `ground_truth_template.json`
- per-case `canonical_timeline.json`
- per-case `training_summary.json`
- per-case `metrics.json`
- per-case `warnings.json`

## Limitations

- The tiny model can still miss or shift boundaries on harder references.
- One-reference adaptation alone is underdetermined; synthetic pretraining mainly improves the prior, not the theoretical limit.
- Real footage will usually need a stronger pretrained video representation for production-grade quality.
- One-reference adaptation cannot perfectly infer invisible edit decisions.
- Text content still requires user input or a separate OCR-aware workflow.
- Camera motion and editor-applied zoom can be ambiguous.
- The model learns a control template, not pixels.
- If a replacement source clip is shorter than a learned slot, the system preserves the learned slot duration and records warnings plus fallback hints in canonical timeline metadata rather than silently pretending the timing is exact.
- This mode is experimental and should surface warnings rather than pretending confidence it does not have.
