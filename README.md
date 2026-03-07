# AI-Editor

AI-Editor is a FastAPI + Shotstack video pipeline that:

- analyzes a reference video
- builds a stage-based edit plan
- assembles source clips
- renders a master output
- optionally post-processes for Shorts (9:16)

## Core Structure

- `app.py` - API entrypoint
- `ai_editor/` - analyzers, downloader, render builder, legacy orchestration
- `pipeline/` - stage runner, plans, state machine, artifacts, storage adapters
- `frontend/` - React UI
- `docs/` - pipeline state and render docs
- `tests/` - unit tests for timing/overlay behavior

## Run Locally

1. Create a virtualenv and install deps:
   - `pip install -r requirements.txt`
2. Configure `.env` (Shotstack key and optional Google credentials)
3. Start API:
   - `python app.py`
4. Start frontend:
   - `cd frontend && npm install && npm run dev`

## Notes

- Per-job artifacts are under `tmp/jobs/<job_id>/`.
- Generated/debug files and secrets are ignored via `.gitignore`.
