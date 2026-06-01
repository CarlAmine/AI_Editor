# Reference Edit Agent

## Overview

`reference_edit_agent` is an additive pipeline mode that uses a real LLM edit agent to turn:

- `reference_edit_template.json`
- `user_patched_plan.json`
- `source_inventory.json`
- request requirements and prompt

into a structured `executable_edit_graph.json`.

That graph is then validated, optionally repaired once by the LLM, compiled into
`render_spec.json` and `canonical_timeline`, and passed into the existing renderer path.

This mode does not generate FFmpeg commands, Python scripts, or rendered media directly.
The LLM only produces structured `edit_graph_v1` JSON.

Existing modes remain separate and unchanged:

- `free_generation_mode`
- `reference_style_transfer`
- `vision_template_learning`

## Production Behavior

`reference_edit_agent` uses a real LLM JSON backend in production.

- The intended default backend is `llm_json`.
- A mock edit planner is not the production execution path.
- Tests may monkeypatch the provider call and return synthetic JSON.
- Invalid LLM output is validated before compilation.
- Invalid output gets one repair attempt by default.
- If repair still fails, the job fails clearly.
- No silent fallback mock graph is generated.

## Architecture

```text
reference video
  -> analyzer output
  -> reference_edit_template.json

user prompt + explicit patch instructions
  -> user_patched_plan.json

replacement clips
  -> source_inventory.json

reference_edit_template
+ user_patched_plan
+ source_inventory
  -> real LLM edit agent
  -> executable_edit_graph.json

executable_edit_graph
  -> validator
  -> repair once if needed
  -> compiler
  -> render_spec.json / canonical_timeline
  -> existing renderer
  -> final video
```

## Configuration

Environment variables:

```dotenv
EDIT_AGENT_BACKEND=llm_json
EDIT_AGENT_MODEL=<model name>
EDIT_AGENT_TEMPERATURE=0.2
EDIT_AGENT_MAX_REPAIR_ATTEMPTS=1
```

If provider configuration is missing, the mode fails with:

- `REFERENCE_EDIT_AGENT_LLM_UNAVAILABLE`

## Request Example

```json
{
  "primary_url": "REFERENCE_VIDEO_URL",
  "sources": [
    {
      "label": 1,
      "url": "REPLACEMENT_CLIP_URL"
    }
  ],
  "prompt": "Use the reference edit but replace the clip and text.",
  "requirements_state": {
    "generation_mode": "reference_edit_agent",
    "slot_replacements": [
      {
        "slot_id": 1,
        "source_index": 1,
        "replacement_text": "Look at this"
      }
    ]
  }
}
```

## LLM Contract

The LLM must return only `executable_edit_graph_v1` JSON with this top-level shape:

```json
{
  "version": "edit_graph_v1",
  "timeline": [],
  "global_style_ops": [],
  "audio": {},
  "warnings": [],
  "model_metadata": {}
}
```

Each timeline item must be structured like:

```json
{
  "slot_id": 1,
  "clip_id": "string",
  "source_index": 1,
  "video_src": null,
  "source_start": 0.0,
  "duration": 1.0,
  "crop": {},
  "motion_effects": [],
  "transition_out": null,
  "text": null,
  "style_ops": [],
  "metadata": {}
}
```

The LLM is instructed to:

- use only clip IDs present in `source_inventory`
- preserve reference slot timing unless the user changed it
- choose `source_start` from candidate segments when possible
- avoid source overruns
- preserve transitions and motion as structured metadata
- avoid arbitrary commands or unsupported imperative instructions

## Validation And Repair

The returned graph is validated before compilation.

Validation rejects:

- missing or malformed `timeline`
- wrong graph version
- invented `clip_id` values
- negative `source_start`
- non-positive `duration`
- source segment overruns
- invalid slot references

If the first graph is invalid:

1. validation errors and the invalid graph are sent back to the LLM
2. the LLM gets one repair attempt by default
3. the repaired graph is validated again

If the repaired graph is still invalid:

- the job fails
- `edit_agent_error.json` is written
- no compiled render spec is produced
- rendering does not proceed

## Generated Artifacts

Plans:

- `reference_edit_template.json`
- `source_inventory.json`
- `user_patched_plan.json`
- `executable_edit_graph.json`
- `edit_graph_validation.json`
- `compiled_render_spec.json`
- `render_spec.json`
- `edit_agent_error.json` on failure

Training:

- `edit_agent_sample.json`
- `edit_agent_sample.jsonl`

Training samples are written only after a valid graph is compiled successfully.

## Compiler And Renderer

The compiler remains deterministic.

It converts a validated `executable_edit_graph` into FFmpeg-compatible canonical timeline rows like:

```json
{
  "index": 1,
  "scene_id": 1,
  "label": "slot_001",
  "start": 0.0,
  "end": 1.4,
  "duration": 1.4,
  "length": 1.4,
  "video_src": "/src/c1.mp4",
  "videoSrc": "/src/c1.mp4",
  "trim": 2.0,
  "text": "Look at this",
  "text_start": 0.0,
  "text_end": 1.4,
  "metadata": {}
}
```

Unsupported rich effects may still be preserved in structured fields:

- `transition_out`
- `motion_effects`
- `style_ops`
- `metadata`

The current renderer may ignore some of those, but they are preserved for future expansion.

## Future Training Path

The architecture is designed for later model training and fine-tuning.

Each successful run logs:

- reference template
- user patched plan
- source inventory
- executable edit graph
- compiled render spec
- requirements and result metadata

That gives the repo a stable dataset format for future supervised training without changing the
validator or compiler boundary.
