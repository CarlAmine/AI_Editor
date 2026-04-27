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
python -m ai_editor.vision_template.cli generate-synthetic --out tmp/vision_synth --num-slots 5
```

Train on the synthetic reference:

```bash
python -m ai_editor.vision_template.cli train-reference --reference tmp/vision_synth/reference.mp4 --out tmp/vision_run --epochs 5 --expected-slots 5
```

Transfer a learned template to replacement clips:

```bash
python -m ai_editor.vision_template.cli transfer --template tmp/vision_run/edit_template.json --slot-mapping tmp/vision_synth/slot_mapping.json --out tmp/vision_run/canonical_timeline.json
```

Run the end-to-end smoke demo:

```bash
python -m ai_editor.vision_template.cli smoke-demo --out tmp/vision_demo --num-slots 5 --epochs 3
```

## Artifacts Produced

- `vision_model.pt`
- `vision_template_raw_output.pt`
- `edit_template.json`
- `training_summary.json`
- `canonical_timeline.json`
- `metrics.json`

When run through the pipeline, the mode also writes the usual `render_spec.json`, `timeline_plan.json`, and canonical timeline artifacts under the job directory.

## Limitations

- One-reference adaptation cannot perfectly infer invisible edit decisions.
- Text content still requires user input or a separate OCR-aware workflow.
- Camera motion and editor-applied zoom can be ambiguous.
- The model learns a control template, not pixels.
- This mode is experimental and should surface warnings rather than pretending confidence it does not have.
