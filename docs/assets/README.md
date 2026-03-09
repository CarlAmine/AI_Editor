# docs/assets

This folder holds all public-facing media for the repository README and documentation.

## Files to Add

| File | Description |
|---|---|
| `demo.gif` | Animated walkthrough of the full pipeline (30–60 seconds) |
| `demo.mp4` | Full demo video (link from README or YouTube) |
| `screenshot-chat.png` | Chat / conversational brief builder interface |
| `screenshot-job-status.png` | Job status panel showing pipeline stage progress |
| `screenshot-timeline.png` | Edit plan / timeline output view |
| `screenshot-render.png` | Shotstack render in progress |
| `screenshot-shorts.png` | Shorts (9:16) conversion output |
| `screenshot-upload.png` | YouTube publish confirmation screen |
| `architecture.png` | Exported architecture diagram image (optional, Mermaid in README is primary) |

## Tips for Capturing Screenshots

1. Use a clean browser window at 1280×800 or 1440×900.
2. Hide any personal API keys or credentials from the UI before capturing.
3. Use macOS Screenshot (⌘⇧4) or Windows Snipping Tool for clean crops.
4. Compress PNGs with [Squoosh](https://squoosh.app/) or `pngquant` before committing.
5. Keep individual files under 500 KB to avoid slowing down README load time.

## Updating the README

Once assets are in this folder, replace the placeholder rows in the README **Screenshots** section with:

```markdown
| ![Chat Interface](docs/assets/screenshot-chat.png) | ![Job Status](docs/assets/screenshot-job-status.png) | ![Timeline](docs/assets/screenshot-timeline.png) |
```
