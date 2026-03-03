# Quick Start Guide

Get the AI-Editor running in 15 minutes.

---

## Prerequisites

- **Python:** 3.8+ (check: `python --version`)
- **Node.js:** 16+ (check: `node --version`)
- **FFmpeg:** Installed system-wide (check: `ffmpeg -version`)
- **Git:** Optional, for cloning
- **API Keys:** Shotstack, Deepseek, Groq (see Environment Setup)

---

## 1. Environment Setup (5 min)

### Install System Dependencies

**macOS:**
```bash
brew install ffmpeg python3 node
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install ffmpeg python3 python3-pip nodejs npm
```

**Windows (with Chocolatey):**
```powershell
choco install ffmpeg python nodejs
```

**Windows (Manual):**
- Download FFmpeg from https://ffmpeg.org/download.html
- Add to PATH: `C:\FFmpeg\bin`
- Verify: `ffmpeg -version`

### Create .env File

In project root (`AI-Editor/`), create `.env`:

```env
# Shotstack API Key (from https://shotstack.io)
SHOTSTACK_API_KEY=your_shotstack_key_here
SHOTSTACK_HOST=https://api.shotstack.io/stage

# LLM Keys
DEEPSEEK_API_KEY=your_deepseek_key_here
GROQ_API_KEY=your_groq_key_here

# Optional
ENV=development
```

---

## 2. Backend Setup (5 min)

### Navigate to Project
```bash
cd AI-Editor
```

### Install Python Dependencies
```bash
pip install -r requirements.txt
```

**Expected packages:**
- FastAPI, uvicorn
- yt-dlp (for YouTube/TikTok downloads)
- FFmpeg (subprocess calls)
- LangChain (LLM integration)
- Requests (HTTP calls)

**Check installation:**
```bash
python -c "import fastapi; import yt_dlp; print('✓ All dependencies installed')"
```

### Start Backend Server
```bash
python -m uvicorn app:app --reload --port 8000
```

**Expected output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
```

**Verify it works:**
```bash
# In another terminal
curl http://localhost:8000/docs
# Should open Swagger UI with all endpoints
```

---

## 3. Frontend Setup (3 min)

### Navigate to Frontend
```bash
cd frontend
```

### Install Dependencies
```bash
npm install
```

### Start Development Server
```bash
npm run dev
```

**Expected output:**
```
VITE v4.x.x  ready in XXX ms

➜  Local:   http://localhost:5173/
```

**Verify it works:**
- Open `http://localhost:5173` in browser
- Should see AI-Editor interface
- No red errors in console

---

## 4. First Test (2 min)

### Option A: Use UI
1. Open `http://localhost:5173` in browser
2. Scroll to **Video Pipeline**
3. Enter:
   - **Primary URL:** `https://www.youtube.com/watch?v=dQw4w9WgXcQ`
   - **Source URL:** `https://www.youtube.com/watch?v=dQw4w9WgXcQ`
   - **Segments:** (leave blank)
   - **Music Mode:** "Use original audio"
   - **Prompt:** "Make a fun clip"
4. Click **Submit**
5. Wait 2-5 minutes for rendering
6. See result video URL

### Option B: Use API (cURL)
```bash
curl -X POST http://localhost:8000/process-video-url \
  -H "Content-Type: application/json" \
  -d '{
    "primary_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "sources": [
      {
        "label": 1,
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "segments": null
      }
    ],
    "prompt": "Make a fun clip",
    "music_mode": "original"
  }'
```

**Expected response:**
```json
{
  "success": true,
  "url": "https://shotstack-api.s3.amazonaws.com/renders/xxx.mp4"
}
```

---

## 5. Verify Installation

Run this checklist:

```bash
# Backend checks
✓ Backend running on port 8000
✓ http://localhost:8000/docs accessible (Swagger UI)
✓ No import errors in console

# Frontend checks
✓ Frontend running on port 5173
✓ http://localhost:5173 loads
✓ VideoPipelinePanel visible
✓ No console errors

# System checks
✓ FFmpeg installed: ffmpeg -version
✓ yt-dlp available: python -c "import yt_dlp"
✓ .env file exists with API keys

# Functionality checks
✓ Can download YouTube video (test with sample URL)
✓ Can clip video segments
✓ Can render with Shotstack
✓ Temp files cleaned up after render
```

---

## Workflow

### Basic Workflow: Single Video
```
1. Frontend UI displays
2. User enters YouTube URL + prompt
3. User clicks Submit
4. Backend downloads video
5. Analyzes content
6. Renders with Shotstack
7. Returns video URL
8. Cleanup happens automatically
```

### Advanced Workflow: Multi-Clip Edit
```
1. User adds multiple sources
2. Specifies segments per source: "0-10, 20-30"
3. Selects music mode (original or custom)
4. Backend downloads all sources
5. Clips each into segments
6. Orders them correctly
7. Renders complete video
8. Returns final URL
```

---

## File Structure Reference

```
AI-Editor/
├── app.py                    # FastAPI app (main entry point)
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables (create this!)
│
├── ai_editor/
│   ├── analyzer.py           # Video analysis (LLM)
│   ├── downloader.py         # YouTube/TikTok download + clip
│   ├── editor.py             # Shotstack rendering
│   ├── overlay_planner.py    # Overlay text planning
│   ├── chatbot_interface.py  # Chat endpoint
│   └── pipeline.py           # Main orchestration
│
├── frontend/
│   ├── package.json          # Node dependencies
│   ├── vite.config.ts        # Vite config
│   └── src/
│       ├── App.tsx           # Main app component
│       ├── main.tsx          # Entry point
│       ├── styles.css        # Global styles
│       └── components/
│           ├── VideoPipelinePanel.tsx  # Video editor UI
│           └── ChatPanel.tsx           # Chat UI
│
└── docs/ (created during setup)
    ├── API_EXAMPLES.md           # API usage examples
    ├── README_REFACTOR.md        # Architecture overview
    ├── MIGRATION_GUIDE.md        # How to upgrade
    └── FRONTEND_TESTING_GUIDE.md # Testing procedures
```

---

## Common Issues & Quick Fixes

### "Cannot connect to backend"
```bash
# Check if backend is running
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Restart backend
python -m uvicorn app:app --reload
```

### "ModuleNotFoundError: No module named 'yt_dlp'"
```bash
pip install yt-dlp
# Verify
python -c "import yt_dlp; print(yt_dlp.__version__)"
```

### "ffmpeg: command not found"
```bash
# Verify FFmpeg installation
ffmpeg -version

# If not found:
# macOS: brew install ffmpeg
# Ubuntu: sudo apt-get install ffmpeg
# Windows: Download from https://ffmpeg.org/download.html
```

### "API Key errors"
```bash
# Check .env file exists
cat .env

# Verify keys in:
# - Shotstack Dashboard
# - Deepseek Console
# - Groq Console

# Restart backend after changing .env
```

### "Segment parsing error"
```
Format: "10-20, 30-40" ✓
Format: "10-20,30-40" ✗ (missing space)
Format: "10-2030-40" ✗ (missing comma)
```

---

## Next Steps

1. **Read documentation:** See [README_REFACTOR.md](docs/README_REFACTOR.md)
2. **Test thoroughly:** See [FRONTEND_TESTING_GUIDE.md](docs/FRONTEND_TESTING_GUIDE.md)
3. **Explore API:** Visit `http://localhost:8000/docs` (Swagger UI)
4. **API examples:** See [API_EXAMPLES.md](docs/API_EXAMPLES.md)
5. **Deploy:** Follow [DEPLOYMENT_CHECKLIST.md](docs/DEPLOYMENT_CHECKLIST.md)

---

## Support

If something doesn't work:

1. Check **Backend Logs:**
   ```
   Look for errors in terminal running uvicorn
   ```

2. Check **Frontend Logs:**
   ```
   Open DevTools (F12) → Console tab
   Look for red errors
   ```

3. Check **Network:**
   ```
   DevTools → Network tab
   Submit a request
   Check Request + Response
   ```

4. Check **System:**
   ```
   FFmpeg: ffmpeg -version
   yt-dlp: python -c "import yt_dlp"
   Python: python --version
   Node: node --version
   ```

---

## Deployment

When ready for production:

1. Install system dependencies (FFmpeg, Python, Node)
2. Set up `.env` with production API keys
3. Install Python: `pip install -r requirements.txt`
4. Install frontend: `npm install`
5. Build frontend: `npm run build`
6. Start backend: `python -m uvicorn app:app --port 8000`
7. Serve frontend from `frontend/dist/`

For detailed deployment steps, see [DEPLOYMENT_CHECKLIST.md](docs/DEPLOYMENT_CHECKLIST.md).

---

**Quick Links:**
- 📖 Full README: [README_REFACTOR.md](docs/README_REFACTOR.md)
- 🧪 Test Guide: [FRONTEND_TESTING_GUIDE.md](docs/FRONTEND_TESTING_GUIDE.md)
- 🚀 Deployment: [DEPLOYMENT_CHECKLIST.md](docs/DEPLOYMENT_CHECKLIST.md)
- 💻 API Docs: http://localhost:8000/docs (when backend running)
- 🎯 API Examples: [API_EXAMPLES.md](docs/API_EXAMPLES.md)

**Status:** ✅ Ready to deploy
