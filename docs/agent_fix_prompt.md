# Agent Fix Prompt — AI Editor Bug Fixes

You are a senior Python engineer working on the `vision-model-v3` branch of this repository.
Your job is to fix four confirmed bugs. Each bug has a precise root cause, a specific file and
function to change, and a clear acceptance criterion. Do not refactor anything outside the
described scope. Do not rename functions, change signatures, or alter any other behavior.

---

## Bug 1 — Video lag and frozen/weird passages at clip boundaries

**File:** `pipeline/executor.py`
**Function:** `_probe_duration(path: str) -> float`

**Root cause:**
The current implementation reads duration from the OpenCV container header
(`CAP_PROP_FRAME_COUNT / CAP_PROP_FPS`). Container headers are frequently wrong — they report
a declared duration that does not match the actual number of decodable frames. When the renderer
tries to read past the real end of a clip, it stalls or emits frozen/black frames. This is the
direct cause of the lag and weird passages between clips.

**Fix:**
Replace the body of `_probe_duration` with an FFprobe-based primary path. Use the
`ffprobe -v error -show_entries format=duration` command via `subprocess.run`. Fall back to the
current OpenCV method only if FFprobe is not available or returns an invalid result. Never return
a value that is higher than the real decodable content length.

The fixed function must:
- Call `ffprobe` with `-show_entries format=duration -of default=noprint_wrappers=1:nokey=1`
- Parse the stdout result as a float
- Fall back to the OpenCV approach if `ffprobe` returns a non-zero exit code or non-numeric output
- Keep the same signature: `_probe_duration(path: str) -> float`
- Return `0.0` on any unrecoverable failure (same as current behavior)

Do not change `_probe_duration_any`. It already chains to `_probe_duration` and then FFprobe
as a secondary path — after this fix both paths will use FFprobe first, which is correct.

---

## Bug 2 — Text overlay only appears on first matching scene, not the whole video

**File:** `pipeline/executor.py`
**Function:** `_apply_confirmed_text_overlays_to_timeline`

**Root cause:**
The function contains a `break` statement after applying an overlay to the first matching scene
row. This means a text overlay that spans multiple consecutive scenes is only written to the
first one. All subsequent scenes that fall within the overlay's time window are skipped.

**Fix:**
Remove the `break` statement. The loop must continue iterating through all timeline rows after
a match and apply the text to every row whose time window overlaps the overlay's
`[overlay_start, overlay_end]` window. The overlap condition already present in the loop is
correct — only the early exit is wrong.

After the fix, a text overlay spanning t=0 to t=20s across four 5-second scenes must produce
four rows in the timeline that each carry the text, `text_start`, `text_end`, `position`, and
`text_style` fields.

Do not change any other logic in this function.

---

## Bug 3 — OCR reports spans that are too wide and does not detect when text changes

**File:** `ai_editor/analysis/ocr_analyzer.py`
**Class:** `OCRAnalyzer`
**Method:** `analyze`

**Root cause:**
The analyzer creates a new `OCRSpan` for every sampled frame independently, with no
deduplication or change-detection. Because only 12 frames are sampled across the whole video,
each sample covers a wide time window. Text that exists from t=5s to t=8s may only be sampled
at t=0s and t=10s, producing a span labeled 0→10s. The caller gets no signal about when the
text actually changed.

**Fix:**
After collecting all per-frame OCR results, post-process the `ocr_spans` list to merge
consecutive spans that carry the same text and emit change boundaries. Specifically:

1. Group `OCRSpan` entries by their `source` field (paddleocr / easyocr) independently.
2. Within each group, sort by `timestamp`.
3. Walk the sorted list and accumulate a running span: when the `text` field changes (case-
   insensitive, after stripping whitespace), close the current span at the previous frame's
   timestamp and open a new one at the current frame's timestamp.
4. The final output `ocr_spans` list must contain only change-boundary spans — one entry per
   unique text run, with `timestamp` set to the first frame where that text appeared.
5. Add a `span_end` field (float, seconds) to each output span representing the timestamp of
   the last frame where that text was observed before it changed or the video ended. This field
   does not exist today — add it to the `OCRSpan` dataclass in `analysis_schema.py` as an
   optional float defaulting to `None`.

The keyframes list must not be modified — it still contains one entry per sampled frame as
today. Only `ocr_spans` changes.

Do not change the sampling loop, the OCR backends, or the `_clean_text` helper.

---

## Bug 4 — Transition detection classifies by time gap, not actual pixel content

**File:** `ai_editor/analysis/scene_analyzer.py`
**Class:** `SceneAnalyzer`
**Method:** `detect_transitions`

**Root cause:**
The current implementation classifies transitions purely by measuring the time gap between
`scenes[i].end_time` and `scenes[i+1].start_time`. A gap of 0.05s is labeled "Hard Cut", a
gap of 0.4s is labeled "Standard Dissolve" — but these labels are meaningless because they
never look at actual frame data. A hard cut with a tiny gap gets mislabeled as a dissolve.

**Fix:**
Replace the gap-timing heuristic with pixel-level boundary analysis using OpenCV. For each
adjacent scene pair, sample the last 3 frames of scene N and the first 3 frames of scene N+1
from the video file. Compute the grayscale histogram of each frame using `cv2.calcHist` and
measure the correlation between the boundary frames using `cv2.compareHist` with
`cv2.HISTCMP_CORREL`.

Classification rules (apply in order):
- If histogram correlation between the last frame of scene N and the first frame of scene N+1
  is below `0.6`: label `"Hard Cut"` (high visual discontinuity)
- If correlation is between `0.6` and `0.85` and the intermediate frames show monotonically
  increasing correlation: label `"Dissolve"`
- If correlation is between `0.6` and `0.85` and intermediate frames do not show monotonic
  progression: label `"Wipe or Match Cut"`
- If correlation is above `0.85`: label `"Soft Cut"` (very similar frames, minimal visual jump)
- If the scene gap is above `1.0s` regardless of correlation: label `"Fade"` (enough time for
  a deliberate visual pause)

The method must still accept `scenes: List[Scene]` and return `List[Dict[str, Any]]` with the
same keys as today (`type`, `gap`). Add one new key: `correlation` (float, the histogram
correlation score, or `None` if frame sampling failed).

The method signature gains one new required parameter: `video_path: str`. Update the call site
in `SceneAnalyzer.analyze` accordingly. Also update the call in `VideoEditAnalyzer.detect_transitions`
in `analyzer.py` to pass `self.video_path`.

If OpenCV frame reading fails for any scene pair, fall back to the original gap-timing
heuristic for that pair only. Do not raise — log a warning and continue.

---

## Constraints

- All changes must be backward-compatible. No public function signatures removed.
- All changes must be on the `vision-model-v3` branch.
- Write no new tests. Do not touch any file in `tests/`.
- Do not touch `README.md`, `CHANGELOG.md`, or any file outside the four listed above plus
  `ai_editor/analysis/analysis_schema.py` (for the `OCRSpan.span_end` field addition).
- Each fix is independent. If one fix is blocked by an environment constraint (e.g. FFprobe
  not available), implement the fallback path correctly and document the constraint inline
  with a `# NOTE:` comment.
