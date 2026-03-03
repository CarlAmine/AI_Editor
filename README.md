# AI Editor

> An AI-powered video editing pipeline that downloads, analyzes, clips, and renders videos from YouTube and TikTok URLs — no file uploads required.

---

## Features

- **URL-based input** — Paste YouTube or TikTok links directly
- **Smart clipping** — Extract multiple segments per video with precise timestamps
- **AI analysis** — Automatically analyzes content to generate editing requirements
- **Text overlays** — AI-planned captions and overlays via Shotstack
- **Flexible audio** — Keep original audio or overlay custom music from a URL
- **Auto-cleanup** — Temporary files are deleted after every render
- **Chat interface** — Conversational UI for iterating on edits

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, FastAPI, Uvicorn |
| AI / LLM | DeepSeek, Groq |
| Video rendering | Shotstack SDK |
| Video download | yt-dlp, FFmpeg |
| Frontend | TypeScript, React, Vite |

---

## Project Structure

```
AI_Editor/
├── app.py                    # FastAPI entry point
├── requirements.txt          # Python dependencies
├── Dockerfile                # Container setup
├── .env.example              # Environment variable template
│
├── ai_editor/                # Core Python package
│   ├── analyzer.py           # Video content analysis
│   ├── chatbot_interface.py  # Chat/LLM interface
│   ├── downloader.py         # YouTube/TikTok download & clipping
│   ├── editor.py             # Shotstack rendering
│   ├── overlay_planner.py    # AI overlay/caption planning
│   └── pipeline.py           # Main orchestration pipeline
│
├── frontend/                 # React + TypeScript UI
│   └── src/
│       ├── App.tsx
│       └── components/
│           ├── VideoPipelinePanel.tsx
│           └── ChatPanel.tsx
│
├── docs/                     # Extended documentation
│   ├── API_EXAMPLES.md
│   ├── SETUP_GUIDE.md
│   ├── DEPLOYMENT_CHECKLIST.md
│   ├── TROUBLESHOOTING.md
│   ├── MIGRATION_GUIDE.md
│   └── YOUTUBE_CLIPPER_DOCS.md
│
└── tests/                    # Test scripts and examples
    ├── youtube_clipper_test.py
    └── YOUTUBE_CLIPPER_EXAMPLES.py
```

---

## Getting Started

### Prerequisites

- Python 3.8+
- Node.js 18+
- [FFmpeg](https://ffmpeg.org/download.html) installed and on your PATH

**Install FFmpeg:**
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Windows (Chocolatey)
choco install ffmpeg
```

### 1. Clone the repository

```bash
git clone https://github.com/CarlAmine/AI_Editor.git
cd AI_Editor
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in your keys:

```env
SHOTSTACK_KEY=your_shotstack_api_key
DEEPSEEK_KEY=your_deepseek_api_key
GROQ=your_groq_api_key
```

### 3. Start the backend

```bash
pip install -r requirements.txt
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

The app will be available at `http://localhost:5173`.  
Interactive API docs: `http://localhost:8000/api/docs`

---

## API Usage

### `POST /process-video-url`

```json
{
  "primary_url": "https://www.youtube.com/watch?v=abc123",
  "sources": [
    {
      "label": 1,
      "url": "https://www.youtube.com/watch?v=abc123",
      "segments": [
        { "start": 10.5, "end": 30.0 },
        { "start": 45.0, "end": 60.0 }
      ]
    },
    {
      "label": 2,
      "url": "https://www.tiktok.com/@user/video/123456",
      "segments": null
    }
  ],
  "prompt": "Fast-paced TikTok style edit with bold captions",
  "music_mode": "original",
  "custom_music_url": null,
  "requirements_state": {
    "tone": "energetic",
    "pacing": "fast",
    "aspect_ratio": "9:16"
  }
}
```

**Response:**
```json
{
  "success": true,
  "url": "https://shotstack-render-url.mp4",
  "render_id": "abc123def456"
}
```

> For more API examples, see [`docs/API_EXAMPLES.md`](docs/API_EXAMPLES.md).

---

## Pipeline Overview

```
User Input
  ├── Primary URL (analysis)
  ├── Sources (ordered clips with segments)
  ├── Editing prompt
  └── Audio mode
        ↓
Assemble_Pipeline()
  ├── [1] Download primary video
  ├── [2] Analyze content
  ├── [3] Generate editing requirements
  ├── [4] Plan text overlays
  ├── [5] Download & clip sources
  ├── [6] Handle audio
  ├── [7] Determine resolution
  ├── [8] Build final overlay
  ├── [9] Render via Shotstack
  └── [✓] Cleanup temp files
        ↓
Rendered video URL
```

---

## Docker

```bash
docker build -t ai-editor .
docker run -p 8000:8000 --env-file .env ai-editor
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [Setup Guide](docs/SETUP_GUIDE.md) | Detailed installation instructions |
| [API Examples](docs/API_EXAMPLES.md) | Full request/response examples |
| [Deployment Checklist](docs/DEPLOYMENT_CHECKLIST.md) | Production deployment steps |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | Common issues and fixes |
| [Migration Guide](docs/MIGRATION_GUIDE.md) | Migrating from the old file-upload workflow |
| [YouTube Clipper Docs](docs/YOUTUBE_CLIPPER_DOCS.md) | Deep-dive on the clipper module |

---

## License

This project is proprietary. All rights reserved.
