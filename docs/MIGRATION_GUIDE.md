# Migration Guide: File Upload → URL-Based Workflow

---

## What Changed

| Feature | Old | New |
|---------|-----|-----|
| Input | File upload (.mp4) | YouTube/TikTok URL |
| Storage | Google Drive folder | Local temp directory |
| Music | `music_url` param | `music_mode` + `custom_music_url` |
| Cleanup | Manual | Automatic |

---

## Endpoint Change

| | Old | New |
|-|-----|-----|
| Endpoint | `POST /process-video` | `POST /process-video-url` |
| Format | `multipart/form-data` | `application/json` |

---

## Request Format

**Before:**
```javascript
const formData = new FormData();
formData.append("video", file);
formData.append("prompt", "...");
formData.append("music_url", "https://...");
fetch("/process-video", { method: "POST", body: formData });
```

**After:**
```javascript
fetch("/process-video-url", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    primary_url: "https://youtube.com/watch?v=...",
    sources: [{ label: 1, url: "https://youtube.com/watch?v=...", segments: null }],
    prompt: "...",
    music_mode: "original",   // or "custom"
    custom_music_url: null
  })
});
```

---

## Environment Variables

**Remove (no longer needed):**
```env
VIDEO_FOLDER=xxx
MUSIC_URL=xxx
GOOGLE_APPLICATION_CREDENTIALS=xxx
```

**Keep:**
```env
SHOTSTACK_KEY=xxx
DEEPSEEK_KEY=xxx
GROQ=xxx
```

---

## Migrating Existing Content

If you had videos in Google Drive:
1. Download them locally
2. Upload to YouTube as unlisted
3. Reference the YouTube URL in the new workflow

---

**Last Updated:** March 2026
