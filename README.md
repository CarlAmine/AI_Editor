# AI-Editor

AI-Editor is a FastAPI + React video editing pipeline built around Shotstack rendering.

It:

- analyzes a reference video
- builds a stage-based edit plan
- assembles source clips
- renders a master output
- optionally post-processes for Shorts (9:16)

## Project Layout

- `app.py` - API entrypoint
- `ai_editor/` - media utilities, downloaders, auth helpers, editor builders, and upload integrations
- `pipeline/` - stage runner, planners, state management, artifact handling, and render orchestration
- `frontend/` - React user interface
- `docs/` - setup, deployment, troubleshooting, and architecture notes
- `tests/` - unit tests for timing and overlay behavior

See `docs/PROJECT_STRUCTURE.md` for a more detailed map of the repository and `tmp/jobs/<job_id>/` runtime layout.

## Run Locally

1. Create a virtual environment and install dependencies:
   - `pip install -r requirements.txt`
2. Configure `.env` with the Shotstack key and any optional Google credentials.
3. Start the API:
   - `python app.py`
4. Start the frontend:
   - `cd frontend && npm install && npm run dev`

## Notes

- Per-job artifacts are written to `tmp/jobs/<job_id>/`.
- Local credentials and generated debug files are ignored via `.gitignore`.
- The UI supports reference-video analysis, source clip intake, Google Drive OAuth, and YouTube upload.
