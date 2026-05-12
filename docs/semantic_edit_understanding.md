# Semantic Edit Understanding

The optional `semantic_edit` layer adds object-aware and layer-aware understanding on top of `vision_template_learning`.

It does not replace the temporal edit-template model. Instead, it complements it by describing what appears inside the reference video:

- tracked objects such as chair, person, table, product, phone, or car
- foreground/background and overlay-like layers
- persistent identities across frames
- simple semantic edit events such as object appearance, disappearance, replacement, scale change, and overlay transitions

## Why This Exists

`vision_template_learning` already learns structure:

- slot rhythm
- durations
- approximate boundaries
- transitions
- motion metadata

The semantic layer adds content understanding:

- which object is the chair
- when the chair is visible
- whether the chair changed while the background stayed stable
- which layers belong to objects versus overlays or background

That makes future instructions like "edit the chair" representable in a structured, verifiable way.

## CPU-Safe MVP

The default implementation is intentionally lightweight and testable:

- synthetic object videos generated from colored geometric shapes
- color-based fallback detector
- rectangular bbox masks
- IoU tracking
- heuristic layer stack and event classification

Heavy backends are optional placeholders only:

- Grounding DINO
- SAM 2
- richer video segmentation or matting models

Those are not required for tests and not required for normal CPU execution.

## Configuration

```json
{
  "semantic_edit": {
    "enabled": true,
    "backend": "auto",
    "text_queries": ["person", "chair", "table", "product"],
    "attach_to_template": true
  }
}
```

When enabled inside `vision_template_learning`, the pipeline:

1. samples the reference video,
2. runs object detection and tracking,
3. builds a semantic video graph,
4. classifies object/layer edit events,
5. saves `semantic_video_graph.json`,
6. attaches semantic metadata to `EditTemplate` slots.

If semantic analysis is disabled, the pipeline skips it silently. If analysis is enabled but fails, the pipeline continues and records warnings instead of hard-failing by default.

## CLI

Synthetic semantic demo:

```bash
python -m ai_editor.semantic_edit.cli synthetic-demo --out tmp/semantic_demo --scenario chair_disappears
```

Analyze a video with the fallback backend:

```bash
python -m ai_editor.semantic_edit.cli analyze --video path/to/video.mp4 --out tmp/semantic_analysis --backend synthetic_color
```

Verify whether a target object changed:

```bash
python -m ai_editor.semantic_edit.cli verify --before tmp/before_graph.json --after tmp/after_graph.json --instruction "change the chair" --out tmp/verification.json
```

## Artifacts

- `semantic_video_graph.json`
- `semantic_ground_truth.json` for synthetic scenarios
- `verification.json` for verification runs

Stable pipeline artifact key:

- `semantic.video_graph`

Semantic metadata attached to each `EditTemplate` slot and propagated into canonical timeline segment metadata includes:

- `visible_objects`
- `visible_layers`
- `semantic_events`
- `semantic_metadata`
- `object_constraints`

## Limitations

- The current fallback detector is synthetic/color-based, not a production object detector.
- Object masks are bbox-derived in the default path.
- Action understanding is geometric and heuristic, not full video-language reasoning.
- Camera motion versus object motion can still be ambiguous.
- The semantic layer enriches templates and verification; it does not directly render edits on its own.

## Future Path

This module is structured so heavier backends can be added later without changing the surrounding contracts:

- Grounding DINO for open-vocabulary detection
- SAM 2 for better masks
- video matting for cleaner foreground/background separation
- stronger learned event classifiers
- object-aware editing and semantic preservation constraints during rendering
