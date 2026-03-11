# Project Structure

This project is split into a small number of top-level areas. The goal is to keep runtime code, UI code, pipeline state, and temporary job artifacts easy to locate.

## Top Level Folders

- `ai_editor/`
  - Media handling utilities and adapters.
  - Includes downloaders, editor payload builders, Google auth helpers, and YouTube upload logic.

- `pipeline/`
  - The stage-based execution pipeline.
  - Owns job context, planning, artifacts, validation, and render orchestration.

- `frontend/`
  - React user interface for briefing, source intake, rendering, and YouTube upload.

- `docs/`
  - Setup guides, deployment notes, troubleshooting, and pipeline documentation.

- `tests/`
  - Unit tests for timing rules, overlays, and pipeline behavior.

- `tmp/`
  - Per-job runtime artifacts.
  - Safe to inspect for debugging.
  - Not intended for source-controlled files.

## Key Root Files

- `app.py`
  - FastAPI entrypoint and HTTP API surface.

- `README.md`
  - Quick start and navigation.

- `requirements.txt`
  - Python dependencies.

- `.env.example`
  - Reference environment variables.

- `docs/OPERATIONS.md`
  - Day-to-day server operation manual and credential handling guide.

## Per-Job Layout

Each job is written to `tmp/jobs/<job_id>/`.

Typical structure:

- `debug/`
  - Request payloads, analyzer output, and debug snapshots.

- `media/`
  - Downloaded or prepared media assets used during processing.

- `plans/`
  - Intermediate planning files such as timeline plans, overlay plans, and Shotstack payloads.

- `outputs/`
  - Final rendered files and local post-processed exports.

- `state.json`
  - Serialized pipeline state for the job.

- `artifacts.json`
  - Artifact registry for assets produced or reused during the job.

## Recommended Conventions

- Keep persistent code in `ai_editor/`, `pipeline/`, `frontend/`, and `tests/`.
- Keep throwaway or diagnostic outputs in `tmp/`.
- Do not add ad-hoc debug JSON files to the project root.
- Keep UI wording plain and task-oriented.
- Prefer one responsibility per module over large mixed-purpose files.

## Current Runtime Secrets

Some local credential files may exist at the project root during development, such as:

- `drive-oauth-client-secret.json`
- `drive-token.json`
- `youtube-client-secret.json`
- `youtube-token.json`

These are local runtime files, not project assets. They should remain ignored by Git.
