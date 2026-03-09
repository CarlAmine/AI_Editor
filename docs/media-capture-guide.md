# Media Capture Guide

This guide tells you exactly what to record and capture for the repo's public-facing media assets.

---

## Asset Folder Structure

```
docs/assets/
├── demo/
│   └── demo.gif                      # Animated pipeline walkthrough
├── screenshots/
│   ├── screenshot-chat.png           # Chat / brief builder interface
│   ├── screenshot-job-status.png     # Job status / stage progress
│   ├── screenshot-timeline.png       # Edit plan / timeline output
│   └── screenshot-render.png         # Render result / export view
└── architecture/
    └── architecture.png              # Optional: exported diagram image
```

> **Note:** The README currently references `docs/assets/screenshot-*.png` (flat, not in subfolders). If you reorganize into subfolders, update the README image paths to match.

---

## Screenshot 1 — Chat Interface

**File:** `docs/assets/screenshots/screenshot-chat.png`  
**What to show:** The React frontend open on the chat/brief builder screen. Ideally with a real brief typed in, e.g. *"Create a 60-second highlight reel with energetic pacing and text overlays."*  
**What makes it good:** A clear, non-empty conversation visible. No personal API keys or tokens visible. Clean browser window, no other tabs showing.  
**Dimensions:** 1280×800 or 1440×900.

---

## Screenshot 2 — Job Status / Pipeline Progress

**File:** `docs/assets/screenshots/screenshot-job-status.png`  
**What to show:** The job status panel showing a job in progress or recently completed. Ideally with multiple stages visible (e.g. Analyzing → Planning → Rendering → Done).  
**What makes it good:** Stage names and status indicators clearly visible. A completed job is more impressive than a spinner.  
**Dimensions:** 1280×800.

---

## Screenshot 3 — Timeline / Edit Plan

**File:** `docs/assets/screenshots/screenshot-timeline.png`  
**What to show:** The edit plan output — either a JSON plan rendered in the UI, a timeline visualization, or the planning stage result.  
**What makes it good:** Shows that the system produces structured, machine-readable output, not just raw LLM text.  
**Dimensions:** 1280×800.

---

## Screenshot 4 — Render Result

**File:** `docs/assets/screenshots/screenshot-render.png`  
**What to show:** The render completion screen — ideally with a rendered video link/preview visible, or the Shotstack job result displayed in the UI.  
**What makes it good:** A completed render with a playable output is the strongest possible closing screenshot.  
**Dimensions:** 1280×800.

---

## Demo GIF

**File:** `docs/assets/demo/demo.gif`  
**Target size:** Under 5 MB (ideally 2–3 MB). Current compressed GIF is already in `docs/assets/`.

### Recommended Recording Flow

Record the following sequence in one continuous take (30–50 seconds total):

1. Open the React frontend (fresh load)
2. Type a brief into the chat interface (e.g. *"60-second highlight reel, upbeat pacing"*)
3. Submit the brief and show the pipeline starting
4. Skip/cut to the job status panel showing stages completing
5. Show the render result or completed job output
6. (Optional) Show the timeline/plan JSON if it looks clean

### GIF Tips

- Use [Kap](https://getkap.co/) (macOS) or [ScreenToGif](https://www.screentogif.com/) (Windows) to record directly to GIF
- Record at 10–15 fps — smooth enough, but keeps size down
- Crop to just the browser window, no desktop chrome
- Keep the window at 1280×800 for consistent sizing
- After recording, compress with [ezgif optimize](https://ezgif.com/optimize) (lossy, 60–80% quality) to reduce size
- A well-compressed 40-second demo GIF should be under 3 MB

---

## Architecture Diagram (Optional)

**File:** `docs/assets/architecture/architecture.png`  
**What to show:** The Mermaid diagram from the README, exported as a clean PNG for use in presentations or the social preview image.  
**How to export:** Open [mermaid.live](https://mermaid.live), paste the diagram source from the README, and download as PNG at 2x resolution.

---

## Social Preview Image

**Dimensions:** 1280×640px (GitHub requirement)  
**Suggested content:**
- Dark background (matches the project's technical tone)
- Project name: **AI Editor** in large, clean sans-serif type
- One-liner: *AI-assisted video editing pipeline*
- One or two UI screenshots composited in
- Optional: architecture diagram thumbnail in the corner

**Tools:** Figma (free), Canva, or even a screenshot of the UI cropped to 1280×640.
