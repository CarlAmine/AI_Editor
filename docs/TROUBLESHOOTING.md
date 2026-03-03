# Troubleshooting Guide

---

## Quick Diagnostics

```bash
# Backend running?
curl http://localhost:8000/docs

# FFmpeg installed?
ffmpeg -version

# Python deps installed?
python -c "import fastapi, yt_dlp, langchain; print('OK')"

# .env file exists?
cat .env | grep SHOTSTACK_KEY
```

---

## Backend Issues

### Port already in use
```bash
lsof -i :8000         # macOS/Linux
netstat -ano | findstr 8000  # Windows
kill -9 <PID>
```

### ModuleNotFoundError
```bash
pip install -r requirements.txt
```

### ffmpeg not found
```bash
# macOS: brew install ffmpeg
# Linux: sudo apt-get install ffmpeg
# Windows: Download from https://ffmpeg.org and add to PATH
```

### Video download fails
- Confirm the video URL is public and not age-restricted
- Test with: `https://www.youtube.com/watch?v=dQw4w9WgXcQ`
- Check your internet connection

### Render fails (Shotstack)
- Verify `SHOTSTACK_KEY` in `.env`
- For longer videos, switch to production: `SHOTSTACK_HOST=https://api.shotstack.io/production`

### Temp files not cleaned up
```bash
rm -rf ./tmp/videos/
```

---

## Frontend Issues

### Cannot connect to backend
- Ensure backend is running on port 8000
- Check CORS is configured in `app.py`

### Segment format error
```
✓ Correct:  "10-20, 30-40"
✗ Wrong:    "10-2030-40"   (missing comma)
✗ Wrong:    "10-20,30-40"  (missing space)
```

---

## Deployment Issues

### Works locally, fails on server
1. Confirm production `.env` has correct API keys
2. Confirm FFmpeg is installed on the server
3. Confirm `./tmp/videos/` has write permissions

### Disk space exhaustion
```bash
df -h
rm -rf ./tmp/videos/*
# Add cron: 0 * * * * rm -rf /path/to/tmp/videos/*
```

---

## Resource Links

- Shotstack Docs: https://shotstack.io/docs/
- yt-dlp Issues: https://github.com/yt-dlp/yt-dlp/issues
- FastAPI Docs: https://fastapi.tiangolo.com/
- FFmpeg Wiki: https://trac.ffmpeg.org/wiki

---

**Last Updated:** March 2026
