# Troubleshooting Guide

Comprehensive guide to diagnosing and fixing common issues.

---

## General Diagnostics

### Step 1: Verify All Services Running
```bash
# Check backend (port 8000)
curl http://localhost:8000/docs
# Expected: Swagger UI loads

# Check frontend (port 5173)
curl http://localhost:5173
# Expected: HTML page loads

# Check FFmpeg
ffmpeg -version
# Expected: Version info printed

# Check yt-dlp
python -c "import yt_dlp; print('OK')"
# Expected: OK printed
```

### Step 2: Check Environment
```bash
# Verify .env exists
test -f .env && echo ".env exists" || echo "Missing .env"

# Verify API keys in .env
grep SHOTSTACK_API_KEY .env
grep DEEPSEEK_API_KEY .env
grep GROQ_API_KEY .env
```

### Step 3: Check Python Environment
```bash
# Verify Python version
python --version  # Should be 3.8+

# Verify dependencies
python -m pip list | grep -E "fastapi|yt-dlp|langchain"
# Should show all packages

# Test imports
python -c "import fastapi, yt_dlp, langchain; print('✓ All imports OK')"
```

---

## Backend Issues

### Error: "Cannot Bind to Port 8000"

**Symptom:**
```
OSError: [Errno 48] Address already in use
```

**Cause:** Another process using port 8000

**Fix:**
```bash
# Find process using port 8000
lsof -i :8000  # macOS/Linux
netstat -ano | findstr 8000  # Windows

# Kill the process
kill -9 <PID>  # macOS/Linux
taskkill /PID <PID> /F  # Windows

# Or use different port
python -m uvicorn app:app --port 8001
```

---

### Error: "ModuleNotFoundError"

**Symptom:**
```
ModuleNotFoundError: No module named 'yt_dlp'
```

**Cause:** Python package not installed

**Fix:**
```bash
# Install missing package
pip install yt-dlp

# Or reinstall all dependencies
pip install -r requirements.txt

# Verify
python -c "import yt_dlp"
```

---

### Error: "ffmpeg not found"

**Symptom:**
```
FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'
```

**Cause:** FFmpeg not installed or not in PATH

**Fix:**

**macOS:**
```bash
brew install ffmpeg
# Verify
ffmpeg -version
```

**Linux:**
```bash
sudo apt-get update
sudo apt-get install ffmpeg
ffmpeg -version
```

**Windows:**
```
1. Download from: https://ffmpeg.org/download.html
2. Extract to: C:\FFmpeg\
3. Add to PATH:
   a. Win + X → System → Advanced System Settings
   b. Environment Variables → Path
   c. Add: C:\FFmpeg\bin
4. Verify in PowerShell:
   ffmpeg -version
```

---

### Error: "Video Download Failed"

**Symptom:**
```
Error: Failed to download primary video: Connection timeout
```

**Causes & Fixes:**

1. **YouTube is blocking requests (too many/too fast)**
   ```bash
   # Solution: Wait 5 minutes before retrying
   # yt-dlp rate-limits automatically
   # Check logs for: [yt-dlp] Rate limit hit
   ```

2. **Network connectivity issue**
   ```bash
   # Test internet
   ping google.com
   # Or test YouTube directly
   python -c "import urllib.request; urllib.request.urlopen('https://www.youtube.com')"
   ```

3. **Invalid YouTube URL**
   ```bash
   # Verify URL format
   # Valid: https://www.youtube.com/watch?v=dQw4w9WgXcQ
   # Valid: https://youtu.be/dQw4w9WgXcQ
   # Invalid: https://youtube.com/watch?v=INVALID
   ```

4. **Video is age-restricted or private**
   ```
   Solution: Try a different public video
   Test with: https://www.youtube.com/watch?v=dQw4w9WgXcQ
   ```

---

### Error: "Invalid Segment Times"

**Symptom:**
```
Error: Start time (50) exceeds video duration (30)
```

**Cause:** Segment times outside video length

**Fix:**
```bash
# Check video duration first
# Use: https://www.youtube.com/watch?v=VIDEO_ID
# Note the duration displayed

# Set segments within duration
# If video is 60 seconds:
Segments: "0-30, 35-50" ✓
Segments: "0-100" ✗ (exceeds duration)
```

---

### Error: "Render Failed"

**Symptom:**
```
Error: Shotstack API returned 400: Invalid composition
```

**Causes:**

1. **Invalid Shotstack API Key**
   ```bash
   # Check .env
   grep SHOTSTACK_API_KEY .env
   
   # Verify key at: https://dashboard.shotstack.io
   # Key should be 40+ characters
   ```

2. **Video too long for stage**
   ```bash
   # Stage API has limits (~30 seconds)
   # Solution: Use production API
   # Edit .env: SHOTSTACK_HOST=https://api.shotstack.io/production
   ```

3. **Invalid audio format**
   ```bash
   # Solution: Try without custom music
   # Use music_mode: "original"
   ```

---

### Error: "Temp Files Not Cleaned Up"

**Symptom:**
```
ls ./tmp/videos/
# Shows old directories that weren't deleted
```

**Cause:** Cleanup failed (exception in pipeline)

**Fix:**
```bash
# Manual cleanup (safe - tmp is regenerated)
rm -rf ./tmp/videos/

# Check backend logs for the actual error
# Look for: "Error during cleanup" or "Exception"

# Most common: permission denied on deleting files
# Solution: Check file permissions
chmod 755 ./tmp/videos/
```

---

## Frontend Issues

### Error: "Cannot Connect to Backend"

**Symptom:**
```
Error: fetch failed
Error: Cannot connect to http://localhost:8000
```

**Cause:** Backend not running or CORS issue

**Fix:**
```bash
# Verify backend running
curl http://localhost:8000/docs
# If fails: Start backend
python -m uvicorn app:app --reload

# Check CORS headers (should be in app.py)
# app.add_middleware(CORSMiddleware, ...)

# If CORS error in console:
# Backend.app.py should have:
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

### Error: "Segment Parsing Failed"

**Symptom:**
```
Error: Invalid segment format
Expected format: "10-20, 30-40"
```

**Cause:** Wrong format or syntax

**Fix:**

```
❌ Bad:  "10-2030-40"    (no comma)
✓ Good: "10-20, 30-40"  (comma and space)

❌ Bad:  "10-20,30-40"   (no space after comma)
✓ Good: "10-20, 30-40"

❌ Bad:  "abc-def"       (not numbers)
✓ Good: "10-20"

❌ Bad:  "10-"           (incomplete)
✓ Good: "10-30"
```

---

### Error: "Form Not Submitting"

**Symptom:**
```
Click Submit → Nothing happens
No errors in console
```

**Cause:** Form validation failing silently

**Fix:**
```bash
# Open DevTools (F12)
# Go to Console tab
# Look for JavaScript errors

# Check Network tab:
# 1. Click Submit
# 2. Watch Network → should show POST to /process-video-url
# 3. Check Request payload JSON
# 4. Check Response status (200, 400, 500)

# Common issues:
# - Required field blank (primary_url, sources)
# - Invalid JSON in payload
# - Missing API key in backend
```

---

### Error: "Music Mode Not Working"

**Symptom:**
```
Select "Use custom music" but field doesn't appear
Or: Field appears but value not sent to backend
```

**Fix:**

**Field not appearing:**
```bash
# Check VideoPipelinePanel.tsx:
# Should have conditional render:
# {musicMode === "custom" && <input ... />}

# If missing, add:
{musicMode === "custom" && (
  <input
    type="url"
    placeholder="Music URL"
    value={customMusicUrl}
    onChange={(e) => setCustomMusicUrl(e.target.value)}
  />
)}
```

**Value not sent:**
```bash
# Check that payload includes customMusicUrl:
const payload = {
  ...
  custom_music_url: customMusicUrl,  // Note snake_case for backend
  ...
}
```

---

### Error: "Video Won't Play After Render"

**Symptom:**
```
Got video URL ✓
URL loads in browser ✓
Video controls visible ✓
But: Video won't play / loading forever
```

**Cause:** Video still uploading or S3 permissions

**Fix:**
```bash
# Wait 30-60 seconds after render completes
# Shotstack uploads to S3, takes time

# Test video URL:
# 1. Copy URL from response
# 2. Paste in new browser tab
# 3. Wait for player to load
# 4. Check browser console for CORS errors

# If CORS error:
# Video URL is correct but S3 has permission issues
# Contact Shotstack support
```

---

## Network Issues

### Issue: "Slow Performance"

**Symptom:**
```
Rendering takes 5+ minutes
Or: Video download takes forever
```

**Cause:** Network, server, or Shotstack overload

**Fix:**
```bash
# Monitor network:
watch 'netstat -s | grep TCP'  # Check active connections

# Check internet speed:
# Upload a test file to confirm
# 1 Mbps upload = ~7.5 MB/minute

# Reduce video complexity:
# - Shorter source videos
# - Fewer segments
# - Lower resolution

# For multiple concurrent requests:
# Add queue/rate limiting (see advanced docs)
```

---

### Issue: "Timeout on Large Files"

**Symptom:**
```
Error: Request timeout
Or: 504 Gateway Timeout
```

**Cause:** Large file > configured timeout

**Fix:**
```bash
# Increase uvicorn timeout:
python -m uvicorn app:app --timeout-keep-alive 600

# Or increase in code (app.py):
# When creating Shotstack client, set longer timeout

# For very large files:
# Break into smaller segments
# Or use async job system
```

---

## Deployment Issues

### Issue: "Works Locally, Not on Server"

**Symptom:**
```
Works on localhost ✓
Doesn't work on production URL ✗
```

**Causes & Fixes:**

1. **Wrong API keys for production**
   ```bash
   # Verify .env on server has production keys:
   SHOTSTACK_API_KEY=prod_key_not_stage_key
   SHOTSTACK_HOST=https://api.shotstack.io/production
   
   # Also check:
   DEEPSEEK_API_KEY=production_key
   GROQ_API_KEY=production_key
   ```

2. **FFmpeg not installed on server**
   ```bash
   # SSH into server and install:
   # Ubuntu: sudo apt-get install ffmpeg
   # CentOS: sudo yum install ffmpeg
   ```

3. **Folder permissions**
   ```bash
   # Temp directory needs write permissions
   mkdir -p ./tmp/videos
   chmod 755 ./tmp/videos
   chown www-data:www-data ./tmp/videos  # If using web server user
   ```

4. **CORS headers wrong in production**
   ```bash
   # If frontend is on different domain:
   # app.py should specify allowed origins:
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["https://yourdomain.com"],
       ...
   )
   ```

---

### Issue: "Out of Disk Space"

**Symptom:**
```
Error: No space left on device
```

**Cause:** Temp files filling disk after cleanup failed

**Fix:**
```bash
# Check disk usage
df -h

# Find largest directories
du -sh ./tmp/* | sort -h

# Clean temp directory
rm -rf ./tmp/videos/*

# Set up auto-cleanup cron job
# Add to crontab (runs every hour):
0 * * * * cd /path/to/AI-Editor && find ./tmp/videos -type d -mtime +1 -exec rm -rf {} \;
```

---

## Data Issues

### Issue: "Analysis Not Running"

**Symptom:**
```
Request submitted ✓
Download completed ✓
But: Hung at "Analyzing content"
Or: Analyzer returned empty response
```

**Cause:** LLM API not working

**Fix:**
```bash
# Check Deepseek API key
grep DEEPSEEK_API_KEY .env

# Test Deepseek directly:
python -c "
from langchain.llms import DeepseekLLM
llm = DeepseekLLM(model='deepseek-chat')
print(llm('say hello'))
"
# If error: Key invalid or API down

# Check logs:
# Look for: "[analyzer]" messages
# If missing: Analyzer not running
```

---

### Issue: "Wrong Video Segments"

**Symptom:**
```
Input: "10-20, 30-40"
Result: Different segments or missing segments
```

**Cause:** Segment parsing or clipping error

**Fix:**
```bash
# Test segment parsing:
python -c "
segments = '10-20, 30-40'
parsed = [
    {'start': int(s.split('-')[0]), 'end': int(s.split('-')[1])}
    for s in segments.split(', ')
]
print(parsed)
# Should output:
# [{'start': 10, 'end': 20}, {'start': 30, 'end': 40}]
"

# Verify in backend logs:
# "[downloader] Clipping segments: [... ]"
# Should show your segments correctly

# If wrong: Check VideoPipelinePanel.tsx segment parsing
```

---

## Performance Optimization

### For Faster Renders

```bash
# 1. Use stage API (faster) instead of production
SHOTSTACK_HOST=https://api.shotstack.io/stage

# 2. Lower output resolution (1080p → 720p)
# In editor.py: Change composition.resolution

# 3. Reduce number of text overlays
# In overlay_planner.py: Limit text items

# 4. Use shorter source videos
# Split long videos into segments

# 5. Enable backend caching
# Cache downloaded videos by URL (24 hours)
```

### For Handling More Requests

```bash
# 1. Add request queue
# Use: Redis + Celery for background jobs

# 2. Increase temp directory cleanup interval
# Clean old jobs: cron script

# 3. Use production-grade server
# Gunicorn + multiple workers:
gunicorn app:app --workers 4 --timeout 300

# 4. Monitor resource usage
# Check: CPU, memory, disk space regularly
```

---

## Debug Logging

### Enable Verbose Logging

**Backend:**
```bash
# Start with debug logging
python -m uvicorn app:app --log-level debug --reload

# Look for these patterns:
# [analyzer] Analyzing content
# [downloader] Downloading: https://...
# ✓ Downloaded ...
# ✓ Successfully clipped ...
# [editor] Using music_mode...
# Successfully rendered
```

**Frontend:**
```bash
# Open DevTools (F12) → Console
# Look for network errors (red text)

# Add custom logging to VideoPipelinePanel.tsx:
console.log("Form submitted:", {
  primaryUrl,
  sources,
  musicMode,
  customMusicUrl
});

// Check network request
// DevTools → Network tab → POST /process-video-url
```

---

## Getting Help

### Information to Provide

When reporting an issue, provide:

1. **Error message** (full text)
2. **Steps to reproduce** (exact sequence)
3. **System info** (OS, Python version)
4. **Relevant logs** (backend + frontend)
5. **What you tried** (debugging steps already taken)

**Example:**
```
Issue: Video download fails after 2 minutes

Error: "Connection timeout: Read timed out"

Steps:
1. Enter URL: https://www.youtube.com/watch?v=dQw4w9WgXcQ
2. Click Submit
3. Wait ~2 min → Error appears

System:
- macOS 12.6
- Python 3.10.8
- Node 18.12

Backend log:
[downloader] Downloading: https://www...
[downloader] Timeout after 120 seconds

Already tried:
- Restarted backend ✓
- Checked internet connection ✓
- Tried different video ✗ (same error)
```

---

## Resource Links

- **Shotstack Docs:** https://shotstack.io/docs/
- **yt-dlp Issues:** https://github.com/yt-dlp/yt-dlp/issues
- **FastAPI Docs:** https://fastapi.tiangolo.com/
- **FFmpeg Wiki:** https://trac.ffmpeg.org/wiki

---

**Last Updated:** March 2026
**Coverage:** 30+ common issues + solutions
