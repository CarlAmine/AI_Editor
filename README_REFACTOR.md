# AI-Editor: Complete Refactor – URL-Based Video Workflow

## Overview

The AI-Editor has been completely refactored to replace the file upload + Google Drive workflow with a modern **URL-based video processing system**. Users now provide YouTube/TikTok URLs, specify segments to extract, and the backend downloads, analyzes, clips, and renders their edited video.

## 🔄 What Changed?

### Before
- Upload local video file
- Backend references clips from Google Drive folder
- Music uploaded separately via URL

### After
- Provide YouTube/TikTok URLs
- Specify segments/timestamps for clipping
- Backend downloads videos, clips them locally, renders with original or custom audio
- All local files cleaned up after rendering

---

## 📋 Key Features

✅ **URL-based input** - YouTube and TikTok links  
✅ **Flexible clipping** - Extract multiple segments from each video  
✅ **Reorderable clips** - Drag/reorder in UI with labeled positions (1, 2, 3,...)  
✅ **Audio options** - Use original audio from clips OR overlay custom music  
✅ **Clean renders** - Automatic cleanup of temporary files after completion  
✅ **Robust error handling** - Clear user-facing messages  
✅ **Deployment-ready** - No external storage dependencies  

---

## 🚀 Installation & Setup

### Prerequisites

1. **FFmpeg** (system-level)
   - Windows: `choco install ffmpeg`
   - macOS: `brew install ffmpeg`
   - Linux: `sudo apt-get install ffmpeg`

2. **Python 3.8+**

### Backend Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Create .env file (template provided)
cp .env.example .env

# 3. Fill in required keys in .env:
SHOTSTACK_KEY=your_shotstack_api_key
DEEPSEEK_KEY=your_deepseek_api_key
GROQ=your_groq_api_key

# 4. Start the backend
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup

```bash
cd frontend

# 1. Install dependencies
npm install

# 2. Build and run
npm run dev

# Frontend available at: http://localhost:5173
```

---

## 📡 API Endpoints

### New: `/process-video-url` (POST)

**Request Body:**
```json
{
  "primary_url": "https://www.youtube.com/watch?v=...",
  "sources": [
    {
      "label": 1,
      "url": "https://www.youtube.com/watch?v=abc123",
      "segments": [
        {"start": 10.5, "end": 30.0},
        {"start": 45.0, "end": 60.0}
      ]
    },
    {
      "label": 2,
      "url": "https://www.tiktok.com/@user/video/123456",
      "segments": null
    }
  ],
  "prompt": "Create a fast-paced 30-second highlight reel with bold captions",
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
  "url": "https://shotstack-render-url-here.mp4",
  "render_id": "abc123def456"
}
```

---

## 📝 Backend Architecture

### New Modules

#### `ai_editor/downloader.py`
Handles YouTube/TikTok downloads and clipping:
- `download_video(url, output_dir)` → str (file path)
- `download_and_clip(sources, output_dir)` → List[Dict]
- `extract_audio(video_path, output_dir)` → str
- `cleanup_directory(path)` → bool

#### `ai_editor/pipeline.py` (Refactored)
New URL-based pipeline:
- `Assemble_Pipeline(primary_url, sources, prompt, music_mode, custom_music_url, requirements_state)` → Dict
- Removed: Google Drive functions
- Removed: File upload handling
- Added: Cleanup in finally block

#### `app.py` (Updated)
- **New:** `/process-video-url` endpoint
- **Deprecated:** `/process-video` (file upload, returns error with migration guide)
- Pydantic models: `VideoSegment`, `VideoSource`, `ProcessVideoURLRequest`

---

## 🎨 Frontend Changes

### VideoPipelinePanel.tsx

**New Components:**
- Primary URL input (for video analysis)
- Source video manager with:
  - URL input
  - Segment specification (format: `10-20, 30-45`)
  - Add/remove/reorder buttons
  - Visual labels showing clip order (1, 2, 3,...)
- Audio/Music dropdown:
  - "Use original audio from clips"
  - "Use custom music from URL"
- Conditional custom music URL input

---

## 🔄 Workflow

```
User Input (Frontend)
    ├─ Primary URL (for analysis)
    ├─ Sources (ordered list with segments)
    ├─ Editing prompt
    └─ Audio mode (original/custom)
    ↓
Backend: Assemble_Pipeline()
    ├─ [Step 1] Download primary URL
    ├─ [Step 2] Analyze content
    ├─ [Step 3] Generate requirements
    ├─ [Step 4] Create overlay plan
    ├─ [Step 5] Download + clip sources
    ├─ [Step 6] Handle audio (extract if custom)
    ├─ [Step 7] Determine resolution
    ├─ [Step 8] Build final overlay
    ├─ [Step 9] Render with Shotstack
    └─ [Cleanup] Delete local files
    ↓
Response to User
    └─ Render URL (or error message)
```

---

## 🗂️ File Structure

```
AI-Editor/
├── app.py                           # FastAPI main app (UPDATED)
├── requirements.txt                 # Dependencies (yt-dlp added)
├── ai_editor/
│   ├── analyzer.py                  # Video analysis (unchanged)
│   ├── chatbot_interface.py          # Chat logic (unchanged)
│   ├── downloader.py                # NEW: Download & clip module
│   ├── editor.py                    # Shotstack rendering (UPDATED)
│   ├── overlay_planner.py           # Overlay text (unchanged)
│   └── pipeline.py                  # Main pipeline (REFACTORED)
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx                  # Main app (unchanged)
│   │   ├── components/
│   │   │   ├── VideoPipelinePanel.tsx  # REFACTORED
│   │   │   └── ChatPanel.tsx           # Unchanged
│   │   └── styles.css               # Updated with new styles
│   └── package.json
│
└── tmp/videos/                       # Working directory (auto-created)
    ├── job_id_1/                    # Created per job
    │   ├── primary.mp4
    │   ├── clip_001.mp4
    │   ├── clip_002.mp4
    │   └── ...
    └── job_id_2/
        └── ...                      # Auto-cleaned after render
```

---

## 🔐 Environment Variables

```env
# Required
SHOTSTACK_KEY=your_shotstack_stage_key
DEEPSEEK_KEY=your_deepseek_api_key      # For overlay planning
GROQ=your_groq_api_key                   # For chat

# Optional (legacy, no longer used)
# VIDEO_FOLDER=xxx         # Removed
# MUSIC_URL=xxx            # Removed
# GOOGLE_APPLICATION_CREDENTIALS=xxx  # Removed
```

---

## ✨ Example Usage

### Single Video, No Clipping
```json
{
  "primary_url": "https://www.youtube.com/watch?v=abc123",
  "sources": [
    {
      "label": 1,
      "url": "https://www.youtube.com/watch?v=abc123"
    }
  ],
  "prompt": "Make it more energetic",
  "music_mode": "original"
}
```

### Multiple Videos with Segments
```json
{
  "primary_url": "https://www.youtube.com/watch?v=highlight",
  "sources": [
    {
      "label": 1,
      "url": "https://www.youtube.com/watch?v=intro",
      "segments": [{"start": 0, "end": 5}]
    },
    {
      "label": 2,
      "url": "https://www.youtube.com/watch?v=main",
      "segments": [
        {"start": 15, "end": 45},
        {"start": 60, "end": 75}
      ]
    },
    {
      "label": 3,
      "url": "https://www.youtube.com/watch?v=outro",
      "segments": [{"start": 0, "end": 8}]
    }
  ],
  "prompt": "Fast-paced tiktok style edit with text overlays",
  "music_mode": "custom",
  "custom_music_url": "https://www.youtube.com/watch?v=upbeat_music"
}
```

---

## 🧹 Cleanup & Storage

- **Working directory:** `./tmp/videos/{job_id}/`
  - Created per request
  - Contains: primary video, all clips, extracted audio
  - **Automatically deleted** after render completes
  
- **Cleanup happens in:** `pipeline.py` finally block
  - Even if render fails
  - Even if errors occur

---

## 🚨 Error Handling

### Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| "yt-dlp not found" | Library not installed | `pip install yt-dlp` |
| "ffmpeg not found" | System dependency missing | Install FFmpeg (see Prerequisites) |
| "Video unavailable" | URL invalid or restricted | Check URL, ensure public video |
| "Segment invalid" | start >= end | Fix start/end times |
| "Failed to clip" | ffmpeg error | Check segment times within video length |
| "Render failed" | Shotstack API issue | Check API key, quotas |

### User-Facing Messages

All errors returned to frontend include:
- Clear description of what failed
- Actionable steps to fix
- Server logs for debugging

---

## 📊 Performance

- **Video download:** 10s - 5min (depends on length/connection)
- **Analysis:** 5-15s
- **Clipping:** 5-30s per clip
- **Rendering:** 10-60s (depends on final duration)
- **Total end-to-end:** ~1-3 minutes

---

## 🔄 Migration Notes

### For Existing Users

**Old Flow (No Longer Works):**
```
POST /process-video (multipart/form-data)
  - video file upload ❌
  - folder_id parameter ❌
  - music_url parameter ❌
```

**New Flow (Required):**
```
POST /process-video-url (application/json)
  - primary_url ✅
  - sources array ✅
  - music_mode + custom_music_url ✅
```

---

## 🛠️ Development Notes

### Adding Features

1. **New download source?**
   - Update `downloader.py`
   - Add URL pattern handling

2. **Change clipping behavior?**
   - Modify `download_and_clip()`
   - Update segment parsing

3. **New music modes?**
   - Add to `music_mode` options
   - Handle in `editor.py` soundtrack logic

4. **Modify pipeline steps?**
   - Edit `Assemble_Pipeline()` in `pipeline.py`
   - Add cleanup for new artifacts

---

## 📚 API Documentation

Full interactive API docs available at:
- **Swagger UI:** `http://localhost:8000/api/docs`
- **ReDoc:** `http://localhost:8000/api/redoc`

---

## 🤝 Deployment

### Local Testing
```bash
# Terminal 1: Backend
python -m uvicorn app:app --reload

# Terminal 2: Frontend
cd frontend && npm run dev
```

### Production Deployment

**Backend:**
```bash
# Use Gunicorn + Uvicorn
gunicorn app:app --workers 2 --worker-class uvicorn.workers.UvicornWorker
```

**Frontend:**
```bash
cd frontend && npm run build
# Serve ./frontend/dist/ as static files
```

---

## ✅ Testing Checklist

- [ ] FFmpeg installed and in PATH
- [ ] yt-dlp installed (`pip list | grep yt-dlp`)
- [ ] .env file configured
- [ ] Backend starts: `python -m uvicorn app:app`
- [ ] Frontend starts: `npm run dev`
- [ ] Test `/process-video-url` via Swagger UI
- [ ] Verify tmp/videos/ cleanup after render
- [ ] Check console logs for warning-free startup

---

## 📞 Support

For issues:
1. Check console/server logs
2. Verify FFmpeg and yt-dlp installed
3. Review API response error message
4. Check .env variables are set
5. Inspect `./tmp/videos/` for debugging artifacts

---

## 📄 License

Part of the AI-Editor project.

---

## 🎯 Summary

The refactored AI-Editor provides:
- ✅ **No file uploads** – simpler UX
- ✅ **No Google Drive dependency** – more portable
- ✅ **URL-based workflow** – works with any YouTube/TikTok
- ✅ **Flexible clipping** – multiple segments per source
- ✅ **Reorderable clips** – visual editor
- ✅ **Clean code** – no temp files left behind
- ✅ **Better errors** – user-friendly messages

**Ready to use!** Start the backend and frontend, and begin creating.
