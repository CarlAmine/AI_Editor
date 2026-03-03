# YouTube Clipper Tool - Installation & Setup Guide

## 🚀 Quick Start Checklist

- [ ] Install FFmpeg on your system
- [ ] Ensure `python-dotenv` is configured (should be automatic)
- [ ] Verify `requirements.txt` is up to date
- [ ] Test the tool with the test script
- [ ] Start the FastAPI server
- [ ] Test API endpoints

---

## 📋 Prerequisites

### Python Version
- Python 3.8 or higher

### System Dependencies

You need **FFmpeg** installed on your system. This is required for video processing.

#### Windows Installation

**Option 1: Using Chocolatey (Recommended)**
```powershell
# If you don't have Chocolatey, install it first
# https://chocolatey.org/install

choco install ffmpeg
```

**Option 2: Manual Installation**
1. Download from: https://ffmpeg.org/download.html
2. Extract to a folder (e.g., `C:\ffmpeg`)
3. Add to system PATH:
   - Open "Environment Variables" (search in Windows)
   - Add `C:\ffmpeg\bin` to the PATH variable
4. Verify installation:
   ```powershell
   ffmpeg -version
   ```

**Option 3: Using Windows Package Manager**
```powershell
winget install ffmpeg
```

#### macOS Installation

```bash
# Using Homebrew
brew install ffmpeg

# Verify installation
ffmpeg -version
```

#### Linux Installation

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install ffmpeg

# Verify installation
ffmpeg -version
```

**Fedora/CentOS:**
```bash
sudo dnf install ffmpeg

# Verify installation
ffmpeg -version
```

### Google Drive Setup

The tool uses an existing service account for Google Drive authentication:

1. **Verify service-account.json exists** in the project root
2. **Grant access to the service account** for the target Google Drive folder:
   - Right-click the folder in Google Drive
   - Share with the service account email (found in service-account.json)
   - Give "Editor" or "Contributor" permissions
3. **Default folder ID**: `1Kdu-CDI670WegvpFiK2ypPDtoqvlO0K8`
   - Verify you have access to this folder, or update the folder ID

---

## 📦 Installation Steps

### Step 1: Install Python Dependencies

```bash
cd path/to/AI-Editor
pip install -r requirements.txt
```

Key packages that will be installed:
```
yt-dlp          # YouTube video downloader
ffmpeg-python   # FFmpeg Python wrapper
google-api-python-client  # Google Drive API
```

### Step 2: Verify FFmpeg Installation

```bash
# Test FFmpeg
ffmpeg -version

# Test yt-dlp
yt-dlp --version
```

### Step 3: Test the Tool (Optional but Recommended)

Run the test script to verify everything is working:

```bash
cd path/to/AI-Editor
python youtube_clipper_test.py
```

**Expected Output:**
```
🎬🎬🎬🎬🎬🎬🎬🎬🎬🎬🎬🎬🎬🎬🎬...

   YOUTUBE CLIPPER - TEST SUITE

🎬🎬🎬🎬🎬🎬🎬🎬🎬🎬🎬🎬🎬🎬🎬...

============================================================
  TEST 1: Time Format Parsing
============================================================

✅ PASS | Seconds as string
✅ PASS | MM:SS format
✅ PASS | HH:MM:SS format
...
```

---

## 🏃 Running the Server

### Start the FastAPI Server

```bash
cd path/to/AI-Editor

# Simple start
python -m uvicorn app:app --reload

# With custom host/port
python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

**Expected Output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
```

### Access the API Documentation

Once the server is running, open your browser and go to:

- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc

You can test the endpoints directly from these interfaces!

---

## 🧪 Testing the Tool

### Method 1: Using the Test Script

```bash
# Test with default parameters
python youtube_clipper_test.py

# Test with custom video
python youtube_clipper_test.py --url "https://www.youtube.com/watch?v=..." \
                                --start "1:30" --end "3:45"

# Test only time format parsing
python youtube_clipper_test.py --test time

# Skip video downloads
python youtube_clipper_test.py --skip-downloads
```

### Method 2: Using Swagger UI

1. Go to http://localhost:8000/api/docs
2. Find the "YouTube Clipper" section
3. Click on `/youtube-clip` endpoint
4. Click "Try it out"
5. Fill in the parameters:
   ```json
   {
     "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
     "start_time": "1:30",
     "end_time": "3:45",
     "clip_name": "test_clip.mp4"
   }
   ```
6. Click "Execute"

### Method 3: Using cURL

```bash
curl -X POST "http://localhost:8000/youtube-clip" \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "start_time": "1:30",
    "end_time": "3:45",
    "clip_name": "test_clip.mp4"
  }'
```

### Method 4: Using Python

```python
import requests

response = requests.post(
    "http://localhost:8000/youtube-clip",
    json={
        "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "start_time": "1:30",
        "end_time": "3:45",
        "clip_name": "test_clip.mp4"
    }
)

print(response.json())
```

---

## ✅ Verification Checklist

After installation, verify everything works:

- [ ] `ffmpeg --version` runs without error
- [ ] `yt-dlp --version` runs without error
- [ ] `python youtube_clipper_test.py` passes (at least time format test)
- [ ] FastAPI server starts (`python -m uvicorn app:app`)
- [ ] API docs load at http://localhost:8000/api/docs
- [ ] Test API endpoint with sample request
- [ ] Check Google Drive for uploaded clip in the specified folder

---

## 🔧 Troubleshooting

### Issue: "ffmpeg: command not found"

**Solution:**
```bash
# Verify FFmpeg is installed
ffmpeg -version

# If not installed:
# Windows: choco install ffmpeg
# macOS: brew install ffmpeg
# Linux: sudo apt-get install ffmpeg
```

### Issue: "yt-dlp: command not found"

**Solution:**
```bash
# Reinstall yt-dlp
pip install --upgrade yt-dlp

# Verify
yt-dlp --version
```

### Issue: "Google Drive authentication failed"

**Solution:**
1. Verify `service-account.json` exists in project root
2. Check that the service account has access to the target folder
3. Verify folder ID is correct (default: `1Kdu-CDI670WegvpFiK2ypPDtoqvlO0K8`)
4. Try sharing the folder with the service account email again

### Issue: "Video download hangs or times out"

**Solution:**
- The video might be very large or your connection is slow
- Try a shorter video first
- Check your internet connection
- Some videos may have geographic restrictions

### Issue: "API returns 422 Unprocessable Entity"

**Solution:**
- Verify request body JSON is valid
- Check that timestamp formats are correct (MM:SS, HH:MM:SS, or seconds)
- Ensure start_time < end_time

### Issue: "ModuleNotFoundError: No module named 'youtube_clipper'"

**Solution:**
```bash
# Make sure you're in the correct directory
cd path/to/AI-Editor

# Reinstall dependencies
pip install -r requirements.txt
```

---

## 📁 File Structure

After installation, your project should have:

```
AI-Editor/
├── app.py                              # Main FastAPI application
├── requirements.txt                    # Updated with new dependencies
├── service-account.json                # Google Drive credentials
│
├── ai_editor/
│   ├── __init__.py
│   ├── youtube_clipper.py             # ✨ NEW: YouTube clipper module
│   ├── analyzer.py
│   ├── chatbot_interface.py
│   ├── editor.py
│   ├── overlay_planner.py
│   └── pipeline.py
│
├── YOUTUBE_CLIPPER_DOCS.md            # ✨ NEW: Full documentation
├── YOUTUBE_CLIPPER_EXAMPLES.py        # ✨ NEW: Code examples
└── youtube_clipper_test.py            # ✨ NEW: Test script
```

---

## 🚀 Next Steps

1. Install all dependencies (see Step 1)
2. Verify FFmpeg is installed (see Prerequisites)
3. Run the test script (see Testing)
4. Start the FastAPI server
5. Test the API endpoints using Swagger UI or cURL
6. Check your Google Drive folder for uploaded clips
7. Integrate with your frontend application

---

## 📚 Documentation Files

- **[YOUTUBE_CLIPPER_DOCS.md](YOUTUBE_CLIPPER_DOCS.md)** - Complete API documentation
- **[YOUTUBE_CLIPPER_EXAMPLES.py](YOUTUBE_CLIPPER_EXAMPLES.py)** - Code examples and recipes
- **[youtube_clipper_test.py](youtube_clipper_test.py)** - Test script with examples

---

## 💡 Tips & Best Practices

### Performance
- Process videos sequentially for best results
- Keep clips under 15 minutes for faster processing
- Use batch endpoint for multiple clips

### Quality
- Videos are automatically encoded with H.264 codec (widely compatible)
- Output is MP4 format with AAC audio
- Default resolution matches source video

### Organization
- Use meaningful names for clips to identify them in Google Drive
- Consider creating subfolders in Google Drive for different projects
- Save a copy of successful clipping results locally

### Debugging
- Use the test script to verify your setup
- Check FastAPI logs for error messages
- Enable verbose logging if needed

---

## 🆘 Getting Help

If you encounter issues:

1. **Check the troubleshooting section** above
2. **Review the documentation** in YOUTUBE_CLIPPER_DOCS.md
3. **Run the test script** to isolate the problem
4. **Check FastAPI logs** for detailed error messages
5. **Verify each prerequisite** is installed correctly

---

## 🔐 Security Notes

⚠️ **Important:**
- Never commit `service-account.json` to version control
- Keep your Google Drive folder ID private
- Validate and sanitize YouTube URLs in production
- Consider implementing authentication for API endpoints
- Use HTTPS in production environments

---

## 📝 License & Attribution

This YouTube Clipper tool is part of the AI-Editor project.

---

**Installation Guide Version:** 1.0  
**Last Updated:** March 2026  
**Compatible with:** Python 3.8+, FastAPI 0.9+
