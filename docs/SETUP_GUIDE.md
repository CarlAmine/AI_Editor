# Setup Guide

Get the AI Editor running in under 15 minutes.

---

## Prerequisites

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

---

## 1. Clone the repository

```bash
git clone https://github.com/CarlAmine/AI_Editor.git
cd AI_Editor
```

## 2. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in your keys:

```env
SHOTSTACK_KEY=your_shotstack_api_key
DEEPSEEK_KEY=your_deepseek_api_key
GROQ=your_groq_api_key
```

## 3. Start the backend

```bash
pip install -r requirements.txt
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

## 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

The app will be available at `http://localhost:5173`.  
Interactive API docs: `http://localhost:8000/api/docs`

---

## Verification Checklist

```bash
# System
ffmpeg -version        # ✓ FFmpeg installed
python --version       # ✓ Python 3.8+
node --version         # ✓ Node 18+

# Python deps
python -c "import fastapi, yt_dlp; print('OK')"

# Services running
curl http://localhost:8000/docs   # ✓ Swagger UI
curl http://localhost:5173        # ✓ Frontend
```

---

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues and fixes.
