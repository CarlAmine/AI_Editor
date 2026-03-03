# Frontend Testing Guide

Complete guide to testing the VideoPipelinePanel component and full frontend workflow.

---

## Prerequisites

- Backend running: `python -m uvicorn app:app --reload`
- Frontend running: `npm run dev` (from `frontend/` directory)
- Valid environment variables in backend `.env`
- Working internet (for YouTube/TikTok downloads)

---

## Test Scenarios

### Test 1: Single Video, No Clipping

**Objective:** Verify basic single-video workflow works

**Steps:**
1. Browser: `http://localhost:5173`
2. Clear all fields
3. **Primary URL:** "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
4. **Source:**
   - URL: "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
   - Segments: Leave blank (empty = whole video)
5. **Prompt:** "Make a fun 15-second clip"
6. **Music Mode:** "Use original audio"
7. Click "Submit"

**Expected Result:**
- ✅ Request submitted
- ✅ Video processes (watch network tab / backend logs)
- ✅ Rendering completes
- ✅ Video URL returned on page
- ✅ Temp directory cleaned up

**Failure Scenarios:**
- ❌ "Cannot connect to backend" → Check backend is running on port 8000
- ❌ "Video unavailable" → Try different YouTube URL
- ❌ "Invalid segment times" → Don't happen in this test
- ❌ Files remain in `./tmp/videos/` → Cleanup failed, check logs

---

### Test 2: Multiple Clips with Segments

**Objective:** Verify segment clipping and source ordering

**Steps:**
1. Clear all fields
2. **Primary URL:** "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
3. **Add Source 1:**
   - URL: "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
   - Segments: "0-10, 20-30, 50-60"
   - (Adds 3 clips: 0→10s, 20→30s, 50→60s)
4. **Add Source 2:**
   - URL: "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
   - Segments: "35-45"
   - (Adds 1 clip: 35→45s)
5. Label should show: 1, 2 (in order)
6. **Prompt:** "Make a highlight reel"
7. **Music Mode:** "Use original audio"
8. Click "Submit"

**Expected Result:**
- ✅ Both sources display with correct labels
- ✅ Segments parse correctly ("0-10, 20-30, 50-60")
- ✅ Correct order maintained
- ✅ Final video contains all 4 clips in correct order

**Verification:**
- Check backend logs show: "Downloaded and clipped 2 sources, total 4 clips"
- Video should be ~80 seconds (10+10+10+40 = 70, plus transitions)

---

### Test 3: Reordering Sources

**Objective:** Verify up/down buttons work and labels update

**Steps:**
1. Clear fields
2. **Add Source 1:** "https://www.youtube.com/watch?v=video1"
3. Label should be "1"
4. **Add Source 2:** "https://www.youtube.com/watch?v=video2"
5. Label should be "2" (below Source 1)
6. **Add Source 3:** "https://www.youtube.com/watch?v=video3"
7. Labels: 1, 2, 3
8. Click **↓ DOWN** button on Source 1
9. New order: 2, 1, 3
10. Check labels updated: 1, 2, 3 (source 2 is now first)
11. Click **↑ UP** button on Source 3
12. New order: 2, 3, 1
13. Labels: 1, 2, 3 ✓

**Expected Result:**
- ✅ Sources reorder correctly
- ✅ Labels automatically renumber
- ✅ UP button disabled on first source
- ✅ DOWN button disabled on last source

---

### Test 4: Music Mode - Original Audio

**Objective:** Verify "Use original audio" mode works

**Steps:**
1. Clear fields
2. **Add Source:** "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
3. **Music Mode:** Select dropdown → "Use original audio"
4. **Custom Music URL field:** Should disappear/hide
5. **Prompt:** "Keep the original music"
6. Click "Submit"

**Expected Result:**
- ✅ Custom Music URL field not visible
- ✅ Pipeline receives `music_mode: "original"`
- ✅ In backend logs: "Using music_mode: original"
- ✅ Final video preserves original clip audio
- ✅ No overlay music is applied

---

### Test 5: Music Mode - Custom Music

**Objective:** Verify "Use custom music" mode works

**Steps:**
1. Clear fields
2. **Add Source:** "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
3. **Music Mode:** Select dropdown → "Use custom music"
4. **Custom Music URL field:** Should appear/show
5. Enter: "https://www.youtube.com/watch?v=upbeat_music"
6. **Prompt:** "Add this music as overlay"
7. Click "Submit"

**Expected Result:**
- ✅ Custom Music URL field is visible when "custom" selected
- ✅ Field is hidden when "original" selected
- ✅ Pipeline receives `music_mode: "custom"` and URL
- ✅ In backend logs: "Using music_mode: custom"
- ✅ Final video has custom music overlay
- ✅ Original clip audio still audible underneath

---

### Test 6: Invalid Segment Format

**Objective:** Verify error handling for malformed segments

**Steps:**
1. Clear fields
2. **Add Source:**
   - URL: "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
   - Segments: "10-2050-60" (missing comma)
   - Try to Submit

**Expected Result:**
- ✅ Error message shown in UI
- ✅ Backend logs show parsing error
- ✅ Request not sent (or fails gracefully)

**Other invalid formats to test:**
- "bad" (not numbers)
- "10-" (incomplete)
- "10-20-30" (two dashes, unclear)
- "abc-def" (letters)

---

### Test 7: Empty Segments (Whole Video)

**Objective:** Verify segments: null means "use whole video"

**Steps:**
1. Clear fields
2. **Add Source:**
   - URL: "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
   - Segments: Leave completely blank (don't type anything)
3. **Prompt:** "Use the whole video"
4. Click "Submit"

**Expected Result:**
- ✅ Source shows with empty segments field
- ✅ Backend receives `"segments": null` for this source
- ✅ Whole video used (no clipping)

---

### Test 8: TikTok URL Support

**Objective:** Verify TikTok videos work

**Steps:**
1. Clear fields
2. **Add Source:** (TikTok URL - format: "https://www.tiktok.com/@user/video/12345")
3. **Segments:** "0-15" (15 second TikTok clip)
4. **Prompt:** "Use TikTok audio"
5. Click "Submit"

**Expected Result:**
- ✅ Backend recognizes TikTok URL
- ✅ yt-dlp successfully downloads
- ✅ Video clips correctly
- ✅ Audio preserved if "original" mode

**Note:** May take longer due to TikTok rate limiting

---

### Test 9: Cleanup Verification

**Objective:** Verify temp files are deleted after render

**Steps:**
1. Open terminal/cmd
2. Watch the temp directory:
   ```bash
   # macOS/Linux
   watch 'ls -la ./tmp/videos/'
   
   # Windows PowerShell
   Get-ChildItem ./tmp/videos/ -Recurse
   ```
3. Submit a render job via UI
4. Watch as:
   - New job_id folder appears
   - Files accumulate (video1.mp4, video2.mp4, clipped_*.mp4, etc.)
   - Rendering starts
   - **IMPORTANT:** After render completes, folder should DELETE

**Expected Result:**
- ✅ Job folder appears during processing
- ✅ All temp files cleaned up after success
- ✅ Folder removed even if render fails
- ✅ Fresh job_id for next request

**Verification:**
```bash
ls ./tmp/videos/
# Should be empty or not exist
```

---

### Test 10: Long Render with Status Check

**Objective:** Verify backend handles long-running renders

**Steps:**
1. Submit request with:
   - Multiple sources
   - Complex segments
   - High resolution (1080p)
2. Open browser DevTools → Network tab
3. Watch request → Should not timeout
4. Rendering may take 2-5 minutes
5. Eventually: response with success=true and URL

**Expected Result:**
- ✅ Request doesn't timeout (backend still working)
- ✅ Response completes eventually
- ✅ Video URL is valid (cloud storage)

**Performance Notes:**
- Expect 1-2 min for simple edits
- 2-5 min for complex multi-clip edits
- Check backend logs for progress: `[step X/9]`

---

### Test 11: Error Handling - Bad Video URL

**Objective:** Verify graceful error for invalid URLs

**Steps:**
1. **Primary URL:** "https://www.youtube.com/watch?v=invalid_id_xyz"
2. **Add Source:** "https://www.youtube.com/watch?v=invalid_id_xyz"
3. Click "Submit"

**Expected Result:**
- ✅ Request sent
- ✅ Error returned: "Failed to download... Video not found"
- ✅ User-friendly error shown in UI
- ✅ Temp files cleaned up

---

### Test 12: Error Handling - Network Disconnection

**Objective:** Verify handling of network failures

**Steps:**
1. Start a render
2. Before completion, disconnect internet
3. Wait for timeout or error

**Expected Result:**
- ✅ Error shown in UI
- ✅ Backend logs show error
- ✅ Temp files cleaned up in finally block
- ✅ Can reconnect and try again

---

## UI Regression Tests

### Component Rendering
- [ ] VideoPipelinePanel renders without errors
- [ ] All form fields visible
- [ ] Buttons have correct labels
- [ ] Styling looks good (no broken CSS)

### Responsive Design
- [ ] Desktop (1920x1080): All fields visible
- [ ] Tablet (768x1024): Fields stack or collapse properly
- [ ] Mobile (375x667): Usable on small screen

### Accessibility
- [ ] Tab through form: Correct order
- [ ] All inputs have labels
- [ ] Error messages clearly visible
- [ ] Color not sole indicator (icons/text too)

---

## Performance Tests

### Test: Multi-Source Performance
```javascript
// Generate 5 sources
for (let i = 0; i < 5; i++) {
  addSource({
    label: i + 1,
    url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    segments: [{ start: 0, end: 30 }]
  });
}
```

**Measure:**
- [ ] No UI lag when adding sources
- [ ] No lag when reordering
- [ ] Form submits quickly

### Test: Large Segment List
```
Segments: "0-5, 5-10, 10-15, 15-20, 20-25, 25-30, 30-35, 35-40"
```

**Measure:**
- [ ] Parse completes in <100ms
- [ ] No console errors
- [ ] Correct 8 segments extracted

---

## Browser Compatibility

Test on:
- [ ] Chrome/Chromium
- [ ] Firefox
- [ ] Safari
- [ ] Edge

For each:
- [ ] Form renders correctly
- [ ] Video plays in result
- [ ] No console errors

---

## Testing Checklist

### Before Deployment
- [ ] All 12 test scenarios pass
- [ ] No console errors (DevTools)
- [ ] No network 500 errors
- [ ] Temp cleanup verified
- [ ] Responsive design works
- [ ] Error messages are clear
- [ ] Performance acceptable

### After Deployment
- [ ] Real YouTube video test
- [ ] Real TikTok video test
- [ ] Multi-user concurrent requests
- [ ] Production Shotstack API works
- [ ] Video URLs are publicly accessible

---

## Common Issues & Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| "Cannot connect to backend" | Backend not running | `python -m uvicorn app:app --reload` |
| Segment parsing fails | Missing commas | Format: "10-20, 30-40" (note space) |
| Music URL not saved | Not visible in form | Check if music_mode is "custom" |
| Temp files not deleted | Cleanup not running | Check finally block in pipeline.py |
| Rendering timeouts | Server too slow | Wait longer or reduce video quality |
| Empty response | CORS issue | Check backend CORS headers |

---

## Debugging Tools

### Browser DevTools
```javascript
// In console, check Last Request
console.log(JSON.stringify(lastPayload, null, 2));

// Watch temp directory while rendering
setInterval(() => {
  fetch('http://localhost:8000/temp-status')
    .then(r => r.json())
    .then(console.log);
}, 5000);
```

### Backend Console
```bash
# Look for these patterns:
# [downloader] Downloading: ...
# ✓ Downloaded ...
# [Step 1/9] ...
# [editor] Using music_mode: original
# Successfully created
# Cleaning up temp directory
```

### Network Tab
1. Open DevTools → Network
2. Filter by: `/process-video-url`
3. Check:
   - Request payload (JSON)
   - Response status (200)
   - Response body (success: true/false)
   - Duration (2-5 min for complex)

---

**Last Updated:** March 2026
**Test Coverage:** All critical paths + error cases
