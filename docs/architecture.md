# Architecture

This document describes the system architecture of AI Editor.

## System Diagram

```mermaid
graph TD
    User(["User / Browser"])
    FE["React Frontend\nVite + REST"]
    API["FastAPI Backend\napp.py"]
    CHAT["Chatbot Interface\nGroq LLM"]
    BRIEF["Edit Brief JSON"]
    ANA["Analyzer\nEasyOCR · PaddleOCR · SceneDetect"]
    PLAN["Edit Plan JSON"]
    RUNNER["Pipeline Runner\npipeline/runner.py"]
    DL["Downloader\nyt-dlp · Google Drive"]
    EDITOR["Editor Builder\nShotstack Timeline"]
    OVERLAY["Overlay Planner"]
    SHORTS["Shorts Converter"]
    SHOTSTACK["Shotstack Render API"]
    ARTIFACTS["Artifact Storage\ntmp/jobs/job_id/"]
    UPLOAD["YouTube Uploader\nGoogle OAuth"]
    GDRIVE["Google Drive"]

    User -->|"chat brief + clips"| FE
    FE -->|"REST calls"| API
    API --> CHAT
    CHAT --> BRIEF
    API --> ANA
    ANA --> PLAN
    BRIEF --> RUNNER
    PLAN --> RUNNER
    API --> RUNNER
    RUNNER --> DL
    RUNNER --> EDITOR
    RUNNER --> OVERLAY
    RUNNER --> SHORTS
    DL --> GDRIVE
    EDITOR -->|"render job"| SHOTSTACK
    SHOTSTACK -->|"video URL"| ARTIFACTS
    SHORTS --> UPLOAD
    ARTIFACTS --> FE
    UPLOAD --> FE
```

## Request Flow

1. **Brief submission** — The user types a natural language brief in the React chat interface. The Groq LLM refines it into a structured edit plan JSON.
2. **Video analysis** — The reference video is processed by the Analyzer: SceneDetect identifies shot boundaries, EasyOCR/PaddleOCR extract text from key frames.
3. **Pipeline execution** — The Pipeline Runner receives the edit plan and executes ordered stages: asset download, timeline assembly, overlay planning, render submission.
4. **Rendering** — The Editor Builder constructs a Shotstack render spec from clip metadata and timing data. Shotstack renders the timeline in the cloud and returns a video URL.
5. **Artifact storage** — All outputs (plans, logs, render URLs) are written to `tmp/jobs/<job_id>/` for per-job isolation.
6. **Export** — Optionally, the Shorts Converter reframes the output to 9:16 and the YouTube Uploader publishes it via Google OAuth.

## Module Responsibilities

| Module | File | Responsibility |
|---|---|---|
| API entrypoint | `app.py` | All HTTP routes, request validation |
| Analyzer | `ai_editor/analyzer.py` | Scene detection, OCR, frame analysis |
| Chatbot | `ai_editor/chatbot_interface.py` | LLM-powered brief refinement |
| Downloader | `ai_editor/downloader.py` | yt-dlp, Google Drive asset fetch |
| Editor | `ai_editor/editor.py` | Shotstack timeline construction |
| Overlay Planner | `ai_editor/overlay_planner.py` | Text/graphic element scheduling |
| YouTube Uploader | `ai_editor/youtube_uploader.py` | OAuth 2.0 publish flow |
| Pipeline Runner | `pipeline/runner.py` | Stage orchestration (~60 KB) |
| State | `pipeline/state.py` | Per-job state machine |
| Artifacts | `pipeline/artifacts.py` | Job artifact path resolution |
