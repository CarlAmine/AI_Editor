# 🎬 YouTube Clipper - Quick Reference Card

## 📦 Installation (3 Steps)

```bash
# 1. Install FFmpeg
# Windows: choco install ffmpeg
# macOS: brew install ffmpeg
# Linux: sudo apt-get install ffmpeg

# 2. Install Python packages
pip install -r requirements.txt

# 3. Verify installation
ffmpeg -version
yt-dlp --version
```

---

## 🚀 Start Using

### Option 1: Python API
```python
from ai_editor.youtube_clipper import YouTubeClipper

clipper = YouTubeClipper()
result = clipper.process_youtube_clip(
    yt_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    start_time="1:30",
    end_time="3:45",
    output_folder_id="1Kdu-CDI670WegvpFiK2ypPDtoqvlO0K8"
)
```

### Option 2: REST API
```bash
curl -X POST "http://localhost:8000/youtube-clip" \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=...",
    "start_time": "1:30",
    "end_time": "3:45"
  }'
```

### Option 3: Swagger UI
1. Start server: `python -m uvicorn app:app --reload`
2. Visit: http://localhost:8000/api/docs
3. Try the `/youtube-clip` endpoint

---

## ⏱️ Time Format Examples

| Format | Example | Result |
|--------|---------|--------|
| Seconds | `90` or `"90"` | 1m 30s |
| MM:SS | `"1:30"` | 1m 30s |
| HH:MM:SS | `"0:01:30"` | 1m 30s |

---

## 🔗 API Endpoints

### Single Clip
```
POST /youtube-clip

{
  "youtube_url": "https://www.youtube.com/watch?v=...",
  "start_time": "1:30",
  "end_time": "3:45",
  "clip_name": "optional.mp4"
}
```

### Batch Clips
```
POST /youtube-clip-batch

{
  "clips": [
    {"url": "...", "start_time": "1:30", "end_time": "3:45"},
    {"url": "...", "start_time": "2:00", "end_time": "4:15"}
  ]
}
```

---

## 📁 What Was Added

### Code (3 files)
- ✅ `ai_editor/youtube_clipper.py` - Core module
- ✅ `app.py` - Updated with 2 new endpoints
- ✅ `requirements.txt` - Added yt-dlp & ffmpeg-python

### Documentation (5 files)
- ✅ `README_YOUTUBE_CLIPPER.md` - Overview
- ✅ `YOUTUBE_CLIPPER_DOCS.md` - Full API docs
- ✅ `SETUP_GUIDE.md` - Installation guide
- ✅ `YOUTUBE_CLIPPER_EXAMPLES.py` - Code examples
- ✅ `youtube_clipper_test.py` - Test script

---

## 🧪 Quick Test

```bash
# Run time format parsing test
python youtube_clipper_test.py --test time

# Test with custom video
python youtube_clipper_test.py --url "..." --start "1:30" --end "3:45"

# Run all tests
python youtube_clipper_test.py
```

---

## 🔑 Key Features

✅ Download YouTube videos  
✅ Clip with second-level accuracy  
✅ Multi-format timestamp support  
✅ Auto-upload to Google Drive  
✅ Batch processing support  
✅ Comprehensive error handling  
✅ REST API ready  
✅ Production ready  

---

## 🆘 Troubleshooting

| Problem | Fix |
|---------|-----|
| "ffmpeg not found" | `choco install ffmpeg` (Windows) or `brew install ffmpeg` (Mac) |
| "yt-dlp not found" | `pip install yt-dlp` |
| "Google Drive failed" | Verify service-account.json exists and folder is shared |
| "Timestamp error" | Use format: seconds, MM:SS, or HH:MM:SS |

---

## 📚 Documentation Quick Links

- 📖 **Main Docs:** `README_YOUTUBE_CLIPPER.md`
- 🔌 **API Reference:** `YOUTUBE_CLIPPER_DOCS.md`
- 💻 **Setup Guide:** `SETUP_GUIDE.md`
- 📝 **Code Examples:** `YOUTUBE_CLIPPER_EXAMPLES.py`
- 🧪 **Testing:** `youtube_clipper_test.py`

---

## 🎯 Common Tasks

### Clip One Video
```python
clipper.process_youtube_clip(
    yt_url="VIDEO_URL",
    start_time="START_TIME",
    end_time="END_TIME",
    output_folder_id="FOLDER_ID"
)
```

### Batch Processing
```python
clips = [
    {"url": "url1", "start_time": "1:00", "end_time": "2:00"},
    {"url": "url2", "start_time": "0:30", "end_time": "1:30"}
]
clipper.process_batch_clips(clips, "FOLDER_ID")
```

### Extract Highlights
```python
highlights = [
    {"url": "video", "start_time": "0:15", "end_time": "1:00"},
    {"url": "video", "start_time": "5:30", "end_time": "7:45"},
    {"url": "video", "start_time": "15:00", "end_time": "16:30"}
]
```

---

## ✨ Default Settings

- **Output Folder:** `1Kdu-CDI670WegvpFiK2ypPDtoqvlO0K8`
- **Video Codec:** H.264
- **Audio Codec:** AAC
- **Format:** MP4
- **Quality:** Best available

---

## 🚀 Next Steps

1. Install FFmpeg
2. Run: `pip install -r requirements.txt`
3. Run: `python youtube_clipper_test.py`
4. Start server: `python -m uvicorn app:app --reload`
5. Try at: http://localhost:8000/api/docs

---

**Version:** 1.0 | **Status:** Ready to Use ✅ | **Date:** March 2026
