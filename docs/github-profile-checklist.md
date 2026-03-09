# GitHub Profile & Repository Checklist

This file contains the recommended GitHub metadata and the exact steps to configure them on GitHub.com.

---

## Minimum GitHub Metadata to Configure Immediately

These four items have the highest impact on first impression and should be done before sharing the repo link anywhere.

| Item | Recommended Value |
|---|---|
| **Description** | AI-assisted video editing pipeline — scene analysis, LLM edit planning, Shotstack rendering, and YouTube publishing |
| **Website** | *(see options below)* |
| **Topics** | *(see list below)* |
| **Social Preview** | Upload a 1280×640px banner image |

---

## Recommended Repository Description

```
AI-assisted video editing pipeline — scene analysis, LLM edit planning, Shotstack rendering, and YouTube publishing.
```

This description:
- fits in the 350 character GitHub limit
- communicates the full stack in one line
- uses the right keywords for discoverability
- works well on both the repo page and GitHub profile cards

---

## Recommended Website / Demo Link

Choose the most applicable option:

| Option | Use when |
|---|---|
| `https://github.com/CarlAmine/AI_Editor` | No live deployment yet (just leave blank or use this as fallback) |
| Your deployed URL | If you deploy to Railway, Render, Fly.io, or similar |
| A Loom / YouTube demo video URL | If you have a recorded walkthrough |

> **Tip:** Even a 2-minute Loom recording of the pipeline running counts as a demo link and significantly increases perceived credibility.

---

## Recommended GitHub Topics (15–20)

Copy and paste these into the Topics field:

```
ai-video-editing
video-pipeline
fastapi
react
python
shotstack
ocr
scene-detection
youtube-api
google-drive
media-pipeline
groq
llm
shorts
video-automation
computer-vision
full-stack
easyocr
scenedetect
vite
```

> GitHub allows up to 20 topics. These cover the key technologies, use cases, and search terms that recruiters, engineers, and AI enthusiasts are likely to search.

---

## How to Set Description, Website, and Topics on GitHub

1. Go to **https://github.com/CarlAmine/AI_Editor**
2. On the right side of the repo page, find the **About** section (top-right panel with a gear icon ⚙️)
3. Click the **⚙️ gear icon** next to "About"
4. A modal will open with fields for:
   - **Description** — paste the recommended description above
   - **Website** — paste your demo link or leave blank
   - **Topics** — type each topic and press Enter after each one
5. Click **Save changes**

---

## How to Upload a Social Preview Image

A social preview image appears when your repo link is shared on LinkedIn, Twitter/X, Slack, etc.

1. Go to **https://github.com/CarlAmine/AI_Editor/settings**
2. Scroll down to the **Social preview** section
3. Click **Edit** → **Upload an image**
4. Upload a 1280×640px PNG or JPG
5. Suggested content: a clean screenshot of the UI or the architecture diagram on a dark background with the project name overlaid

---

## How to Pin the Repo on Your Profile

1. Go to **https://github.com/CarlAmine**
2. Click **Customize your pins** (below the top profile section)
3. Check **AI_Editor** in the list
4. Click **Save pins**

---

## How to Create the First Release

See [docs/releases/v0.1.0-initial-release.md](releases/v0.1.0-initial-release.md) for the full release note draft.

Steps:
1. Go to **https://github.com/CarlAmine/AI_Editor/releases/new**
2. In **Choose a tag**, type `v0.1.0` and select **Create new tag: v0.1.0 on publish**
3. Set **Target** to `main`
4. **Release title**: `v0.1.0 — Initial Release`
5. Paste the content from `docs/releases/v0.1.0-initial-release.md` into the description box
6. Leave **Set as pre-release** checked for now (uncheck when you're ready for a stable public release)
7. Click **Publish release**
