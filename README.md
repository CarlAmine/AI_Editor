# AI Editor

AI Editor is a full-stack video editing service that analyzes a reference video, builds an edit plan, assembles a render through Shotstack, and exposes the workflow through a React frontend and FastAPI backend.

The repository is set up so the whole app can run from a single Docker container:

- FastAPI serves the API and the built frontend
- React is built during the image build
- Docker health checks target `/healthz`
- Sensitive `.env` and JSON credential files stay outside the image

## What You Get

- Reference video analysis with OCR and scene detection
- Prompt-driven edit planning
- Shotstack timeline assembly and rendering
- Optional Google Drive ingestion
- Optional YouTube upload flow
- A browser UI at `/`
- OpenAPI docs at `/api/docs`

## Quick Start With Docker

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Fill in at least:

- `SHOTSTACK_KEY`
- `GROQ` if you want the chat brief builder

3. Build and run the app:

```bash
docker compose up --build
```

Or with plain Docker:

```bash
docker build -t ai-editor .
docker run --rm -p 10000:10000 --env-file .env ai-editor
```

4. Open:

- UI: `http://localhost:10000/`
- API docs: `http://localhost:10000/api/docs`
- Health check: `http://localhost:10000/healthz`

## Credentials In Docker

Credential JSON files are intentionally excluded from the Docker image. If you use Google Drive or YouTube integrations, mount them at runtime and point the matching env vars at the mounted paths.

Example:

```bash
docker run --rm -p 10000:10000 --env-file .env \
  -v "$(pwd)/secrets:/app/secrets:ro" \
  ai-editor
```

Then set values such as:

- `DRIVE_CLIENT_SECRET_FILE=/app/secrets/drive-oauth-client-secret.json`
- `DRIVE_TOKEN_FILE=/app/secrets/drive-token.json`
- `GOOGLE_APPLICATION_CREDENTIALS=/app/secrets/service-account.json`
- `YOUTUBE_CLIENT_SECRET_FILE=/app/secrets/youtube-client-secret.json`
- `YOUTUBE_TOKEN_FILE=/app/secrets/youtube-token.json`

## Local Development

Backend:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 10000 --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Default local URLs:

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:10000`
- API docs: `http://localhost:10000/api/docs`

## Project Layout

```text
AI-Editor/
|-- app.py
|-- Dockerfile
|-- docker-compose.yml
|-- ai_editor/
|-- pipeline/
|-- frontend/
|-- docs/
`-- tests/
```

## Notes

- Runtime job artifacts are written under `tmp/jobs/`
- Built frontend assets are served automatically when `frontend/dist/` is present
- The container runs as a non-root user

## License

MIT. See [LICENSE](LICENSE).
