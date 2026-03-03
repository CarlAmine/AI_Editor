# Migration Guide: Old Workflow → New URL-Based Workflow

## Quick Reference

| Feature | Old | New |
|---------|-----|-----|
| Input | File upload (.mp4, .mov, etc.) | YouTube/TikTok URL |
| Storage | Google Drive folder | Local temp directory |
| Asset source | Google Drive links | URL downloads |
| Music | Separate music_url parameter | music_mode dropdown + custom_music_url |
| Cleanup | Manual | Automatic |

---

## Before: File Upload Workflow

```javascript
// Old frontend request
const formData = new FormData();
formData.append("prompt", "Make it energetic");
formData.append("video", videoFile);           // Local file
formData.append("folder_id", "gdrive_folder_id");
formData.append("music_url", "https://...");

fetch("/process-video", {
  method: "POST",
  body: formData
});
```

```python
# Old backend endpoint
@app.post("/process-video")
async def process_video(
    prompt: str = Form(...),
    video: UploadFile = File(...),
    folder_id: str = Form(None),
    music_url: str = Form(None),
    requirements_state: str = Form(None)
):
    # Save file to disk
    # Fetch clip URLs from Google Drive
    # Render with shared music_url
```

---

## After: URL-Based Workflow

```javascript
// New frontend request
const payload = {
  "primary_url": "https://youtube.com/watch?v=abc123",
  "sources": [
    {
      "label": 1,
      "url": "https://youtube.com/watch?v=abc123",
      "segments": [{"start": 10, "end": 30}]
    }
  ],
  "prompt": "Make it energetic",
  "music_mode": "original",
  "custom_music_url": null,
  "requirements_state": {}
};

fetch("/process-video-url", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(payload)
});
```

```python
# New backend endpoint
@app.post("/process-video-url")
async def process_video_url(request: ProcessVideoURLRequest):
    # Download primary URL
    # Download and clip sources
    # Render with music_mode handling
    # Cleanup temp files
```

---

## Step-by-Step Migration

### Frontend Changes

**Remove:**
- File input component
- Folder ID input
- Simple music URL input

**Add:**
- Primary URL input
- Source video manager
  - URL input field
  - Segment specification (MM:SS or seconds)
  - Add/remove/reorder buttons
  - Visual label for clip order
- Music mode dropdown
- Conditional custom music URL input

**Example:**
```tsx
// OLD
<input type="file" onChange={handleFileChange} />
<input placeholder="Folder ID" value={folderId} />
<input placeholder="Music URL" value={musicUrl} />

// NEW
<input placeholder="Primary URL for analysis" />
<SourceManager 
  sources={sources}
  onAdd={handleAddSource}
  onRemove={handleRemoveSource}
  onReorder={handleReorder}
/>
<select value={musicMode}>
  <option value="original">Use original audio</option>
  <option value="custom">Use custom music</option>
</select>
{musicMode === "custom" && (
  <input placeholder="Custom music URL" />
)}
```

### Backend Changes

**Remove:**
- Google Drive authentication code
- `get_drive_service()` function
- `get_drive_assets()` function
- File upload handling

**Add:**
- `downloader.py` module
- `download_video()` function
- `download_and_clip()` function
- `cleanup_directory()` function
- Job ID-based temp directory structure
- Cleanup in finally block

---

## Removed Environment Variables

These are **no longer needed**:

```env
# OLD (No longer used)
VIDEO_FOLDER=xxx
MUSIC_URL=xxx
GOOGLE_APPLICATION_CREDENTIALS=xxx
```

**Keep these:**
```env
SHOTSTACK_KEY=xxx
DEEPSEEK_KEY=xxx
GROQ=xxx
```

---

## Breaking Changes

1. **File upload endpoint deprecated**
   - `/process-video` now returns error with migration guide
   - Use `/process-video-url` instead

2. **Request format changed**
   - Old: `multipart/form-data` (file upload)
   - New: `application/json` (URL-based)

3. **No more Google Drive**
   - Can't specify arbitrary folders
   - All clips stored in local temp directory
   - Automatic cleanup after render

4. **Music handling changed**
   - Old: `music_url` parameter
   - New: `music_mode` ("original" | "custom") + optional `custom_music_url`

---

## Example: Adapting Your Code

### JavaScript/TypeScript

**Before:**
```javascript
async function submitRequest(videoFile, prompt, folderId, musicUrl) {
  const formData = new FormData();
  formData.append("video", videoFile);
  formData.append("prompt", prompt);
  formData.append("folder_id", folderId);
  formData.append("music_url", musicUrl);

  const response = await fetch("/process-video", {
    method: "POST",
    body: formData
  });
  
  return response.json();
}
```

**After:**
```javascript
async function submitRequest(primaryUrl, sources, prompt, musicMode, customMusicUrl) {
  const response = await fetch("/process-video-url", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      primary_url: primaryUrl,
      sources: sources.map((src, i) => ({
        label: i + 1,
        url: src.url,
        segments: src.segments
      })),
      prompt: prompt,
      music_mode: musicMode,
      custom_music_url: musicMode === "custom" ? customMusicUrl : null,
      requirements_state: {}
    })
  });
  
  return response.json();
}
```

### Python

**Before:**
```python
import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder

def process_video(video_path, prompt, folder_id, music_url):
    with open(video_path, 'rb') as f:
        response = requests.post(
            "http://localhost:8000/process-video",
            data={
                "prompt": prompt,
                "folder_id": folder_id,
                "music_url": music_url
            },
            files={"video": f}
        )
    return response.json()
```

**After:**
```python
import requests

def process_video(primary_url, sources, prompt, music_mode, custom_music_url=None):
    payload = {
        "primary_url": primary_url,
        "sources": sources,  # List of {label, url, segments}
        "prompt": prompt,
        "music_mode": music_mode,
        "custom_music_url": custom_music_url,
        "requirements_state": {}
    }
    
    response = requests.post(
        "http://localhost:8000/process-video-url",
        json=payload
    )
    return response.json()
```

---

## What About My Data?

### Google Drive Folder Contents
If you had clips organized in Google Drive:
1. Download them locally
2. Upload to YouTube as unlisted videos (to get shareable URLs)
3. Reference those URL in the new workflow

### Shotstack Assets
- No changes required
- Still use Shotstack API like before
- Rendering behavior unchanged

---

## Backwards Compatibility

**The old `/process-video` endpoint:**
- Still exists but returns error
- Provides migration hint
- Prevents silent failures

```json
{
  "success": false,
  "error": "File upload workflow has been deprecated. Please use /process-video-url with YouTube/TikTok URLs instead.",
  "migration_guide": "See API documentation for /process-video-url"
}
```

---

## Testing Your Migration

1. **Prepare test URLs**
   - Upload a test video to YouTube (unlisted is fine)
   - Get the shareable link

2. **Test new endpoint**
   ```bash
   curl -X POST http://localhost:8000/process-video-url \
     -H "Content-Type: application/json" \
     -d '{
       "primary_url": "https://youtube.com/watch?v=...",
       "sources": [{"label": 1, "url": "https://youtube.com/watch?v=...", "segments": null}],
       "prompt": "Test edit",
       "music_mode": "original"
     }'
   ```

3. **Verify cleanup**
   - Check that `./tmp/videos/` is cleaned up after render
   - No large temp files left behind

---

## Common Issues & Fixes

### Issue: "Module not found: downloader"
**Fix:** Ensure `ai_editor/downloader.py` exists

### Issue: "yt-dlp command not found"
**Fix:** Run `pip install -r requirements.txt`

### Issue: "Video unavailable" error
**Fix:** 
- Ensure video URL is public (not private/unlisted requires auth)
- Some videos have download restrictions

### Issue: "ffmpeg not found"
**Fix:** Install FFmpeg system-wide (see Prerequisites)

### Issue: Temp files not cleaning up
**Fix:** Check server logs for errors in cleanup_directory()

---

## Timeline: Running Old & New Together

**Phase 1: Testing (Week 1)**
- Deploy new endpoint alongside old
- Test with sample videos
- Update frontend in development

**Phase 2: Migration (Week 2-3)**
- Redirect frontend to use `/process-video-url`
- Keep old endpoint for backwards compatibility
- Monitor for issues

**Phase 3: Deprecation (Week 4+)**
- Old endpoint removed
- Full migration complete

---

## Questions?

See:
- [README_REFACTOR.md](./README_REFACTOR.md) – Full refactor details
- [API Docs](http://localhost:8000/api/docs) – Interactive endpoint docs
- `ai_editor/downloader.py` – Source code comments

---

**Last Updated:** March 2026  
**Refactor Status:** ✅ Complete
