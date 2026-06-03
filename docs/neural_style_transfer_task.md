# Neural Style Transfer — Claude Code Implementation Task

## Context

This repository is a video editing pipeline. The goal of this task is to add a
complete **video-to-video neural style transfer system** that:

1. Takes a **donor video** (style source) and overfits a small neural network on it
2. Takes a **content video** (footage to restyle) and runs that trained network over
   every frame
3. Additionally extracts graphic/text overlays from the donor video and replaces
   them over the content video
4. Reassembles the processed frames into a final video using **OpenCV VideoWriter
   only — no FFmpeg, no Shotstack, no LLM in the loop**

The system must run on **CPU only** (Lenovo i7, no dedicated GPU). All processing
must be feasible within reasonable time for short-form video (up to 3 minutes,
480p–1080p). Internal processing runs at 360p and is upscaled back to the
original resolution at the end.

---

## Architecture overview

Two independent tracks, composed at the end:

```
Donor video ──┬── StyleRenderer training (U-Net overfit) ──► style_renderer.pt
              └── OverlayReplicator extraction ──────────► overlay_manifest.json

Content video ─┬── StyleRenderer inference (frame by frame) ──► styled frames
               └── OverlayReplicator application ────────────► overlay frames
                                                                     │
                                              OpenCV VideoWriter ◄───┘
                                                      │
                                               final_output.mp4
```

---

## Files to create

All new files go inside `ai_editor/vision_template/`. Do not modify any existing
file except where explicitly stated below.

---

### File 1: `ai_editor/vision_template/style_renderer.py`

This is the core neural renderer.

#### Class: `StyleUNet(nn.Module)`

A small U-Net image-to-image network.

Architecture (hardcoded, no config needed):
- Input: RGB frame tensor `[1, 3, H, W]` normalised to `[-1, 1]`
- Encoder: 3 downsampling blocks. Each block = Conv2d(in, out, 3, padding=1) +
  BatchNorm2d + LeakyReLU(0.2) + MaxPool2d(2). Channel sizes: 3→32→64→128
- Bottleneck: Conv2d(128, 128, 3, padding=1) + BatchNorm2d + LeakyReLU(0.2)
- Decoder: 3 upsampling blocks with skip connections from encoder.
  Each block = Upsample(scale_factor=2) + Conv2d + BatchNorm2d + ReLU.
  Channel sizes mirror encoder in reverse: 128→64→32→3
- Output activation: Tanh (output range [-1, 1], convert back to [0, 255] uint8
  after inference)
- Skip connections: concatenate encoder feature maps to decoder input at each
  level (standard U-Net skip)

#### Function: `train_style_renderer(donor_video_path, out_dir, epochs=80,
  process_size=360, device='cpu') -> str`

Trains `StyleUNet` on the donor video and returns the path to the saved model.

Training procedure:
1. Extract frames from donor video using OpenCV at `process_size` (height=360,
   maintain aspect ratio). Sample every 3rd frame to limit memory. Cap at 300
   frames maximum.
2. Build a `torch.utils.data.Dataset` where each item is:
   - `input`: the original frame with random augmentation applied (random
     brightness ±0.15, random contrast ±0.15, random horizontal flip with
     p=0.3, Gaussian noise std=0.02). Normalise to [-1,1].
   - `target`: the original frame (no augmentation). Normalise to [-1,1].
   The training signal is: given a perturbed donor frame, reconstruct the
   original. This forces the network to learn the donor's exact pixel
   distribution as an attractor.
3. Loss function: `0.7 * L1Loss + 0.3 * PerceptualLoss`
   PerceptualLoss: use a frozen VGG16 (torchvision, pretrained=True) and
   compare `relu2_2` feature maps between output and target. If torchvision
   is not available or VGG16 cannot be loaded, fall back to `L1Loss` only and
   log a warning.
4. Optimizer: Adam, lr=1e-3, weight_decay=1e-5
5. Training loop: `epochs` iterations, batch_size=4, DataLoader with
   shuffle=True. Log loss every 10 epochs to stdout.
6. After training, save the model state_dict to
   `{out_dir}/style_renderer.pt` using `torch.save`.
7. Return the path `{out_dir}/style_renderer.pt`.

#### Function: `apply_style_renderer(content_video_path, renderer_path,
  out_path, process_size=360, temporal_blend=0.35, device='cpu') -> str`

Applies the trained renderer to a content video and writes the output.

Procedure:
1. Load `StyleUNet` from `renderer_path` using `torch.load` +
   `model.load_state_dict`. Set `model.eval()`.
2. Open content video with `cv2.VideoCapture`. Read original width, height,
   fps, total frame count.
3. Open output writer: `cv2.VideoWriter(out_path,
   cv2.VideoWriter_fourcc(*'mp4v'), fps, (orig_width, orig_height))`
4. For each frame:
   a. Resize to `process_size` height maintaining aspect ratio.
   b. Normalise to [-1,1] tensor.
   c. Run through model (no_grad).
   d. Convert output back to uint8 [0,255].
   e. **Temporal blending**: blend current stylized frame with the
      previous stylized frame using
      `blended = (1 - temporal_blend) * current + temporal_blend * previous`
      (for the first frame, previous = current). This reduces flickering.
   f. Resize blended frame back to `(orig_width, orig_height)` using
      `cv2.INTER_LANCZOS4`.
   g. Write to VideoWriter.
5. Release capture and writer.
6. Return `out_path`.

---

### File 2: `ai_editor/vision_template/overlay_replicator.py`

Extracts graphic and text overlays from the donor video and applies them to
the styled content video.

#### Class: `OverlayManifest` (dataclass)

Fields:
- `entries: List[OverlayEntry]` — list of detected overlay events
- `donor_fps: float`
- `donor_width: int`
- `donor_height: int`

Method `to_json(path: str)` — serialise to JSON file.
Classmethod `from_json(path: str)` — deserialise from JSON file.

#### Class: `OverlayEntry` (dataclass)

Fields:
- `start_frame: int` — first donor frame where overlay appears
- `end_frame: int` — last donor frame where overlay appears
- `start_sec: float`
- `end_sec: float`
- `region: dict` — `{x, y, w, h}` bounding box in donor pixel coords
- `frames: List[np.ndarray]` — NOT serialised to JSON; used in memory only
- `overlay_type: str` — `'graphic'` or `'text'`
- `thumbnail_b64: str` — base64 PNG of first frame of overlay, for debugging

#### Function: `extract_overlays(donor_video_path, out_dir,
  process_size=360) -> OverlayManifest`

Detects graphic and text overlay regions in the donor video.

Procedure:
1. Extract frames at process_size using OpenCV.
2. Build a **background model** using the median of the first 30 frames
   (or all frames if fewer). This represents the "clean" background.
3. For each frame, compute the absolute difference from the background median.
   Convert to grayscale. Threshold at 30. Find contours with area > 200px.
4. Any contour that persists across 5+ consecutive frames (same region,
   IoU > 0.4 with previous frame's contour) is classified as an overlay.
5. Overlays with high edge density in the region (Canny edge count > 20% of
   region area) are classified as `'graphic'`. Others as `'text'`.
6. For each detected overlay event, store the cropped region pixels for every
   frame in the event (these are the actual overlay pixels to replay).
7. Save manifest (without frame pixel data) to
   `{out_dir}/overlay_manifest.json`.
8. Return the manifest with frame data in memory.

#### Function: `apply_overlays(content_video_path, manifest,
  styled_video_path, out_path) -> str`

Composites the overlay events from the manifest onto the styled video.

Procedure:
1. Open `styled_video_path` for reading (this is the output of
   `apply_style_renderer`).
2. Open `content_video_path` for reading (to get original timing/fps).
3. Open output writer at original resolution.
4. For each frame index:
   a. Read the frame from the styled video.
   b. Check if any `OverlayEntry` is active at this frame index (map donor
      frame index to content frame index by proportional timing:
      `content_frame / content_fps == donor_frame / donor_fps`).
   c. If an overlay is active, composite its pixels onto the styled frame
      at the same relative position (scale the `region` bounding box from
      donor resolution to content resolution).
   d. Compositing method: alpha blend using the overlay's own pixel mask
      (pixels that differ from background by > 20 in any channel are
      considered overlay pixels; others are transparent).
   e. Write composited frame to output writer.
5. Return `out_path`.

---

### File 3: `ai_editor/vision_template/neural_transfer_pipeline.py`

Top-level orchestrator that wires everything together.

#### Function: `run_neural_style_transfer(donor_video_path, content_video_path,
  out_dir, epochs=80, process_size=360, temporal_blend=0.35,
  device='cpu') -> dict`

Full pipeline:

```python
def run_neural_style_transfer(
    donor_video_path: str,
    content_video_path: str,
    out_dir: str,
    epochs: int = 80,
    process_size: int = 360,
    temporal_blend: float = 0.35,
    device: str = 'cpu',
) -> dict:
    """
    Returns a dict with keys:
    - renderer_path: str — path to saved style_renderer.pt
    - overlay_manifest_path: str — path to overlay_manifest.json
    - styled_video_path: str — intermediate styled video (no overlays)
    - final_output_path: str — final video with overlays composited
    - timing: dict — wall-clock seconds for each stage
    """
```

Stages (in order):
1. `train_style_renderer(donor_video_path, out_dir, epochs, process_size, device)`
2. `extract_overlays(donor_video_path, out_dir, process_size)`
3. `apply_style_renderer(content_video_path, renderer_path,
   f'{out_dir}/styled_intermediate.mp4', process_size, temporal_blend, device)`
4. `apply_overlays(content_video_path, manifest,
   f'{out_dir}/styled_intermediate.mp4', f'{out_dir}/final_output.mp4')`

Time each stage with `time.perf_counter`. Return the timing dict.
If any stage fails, catch the exception, log it, and re-raise as
`NeuralTransferError(stage_name, original_exception)`.

#### Exception: `NeuralTransferError(Exception)`

Fields: `stage: str`, `cause: Exception`.

---

### File 4: `ai_editor/generation_modes.py` (MODIFY existing)

Add one new constant to the existing `GenerationMode` enum or string constants:

```python
NEURAL_STYLE_TRANSFER = 'neural_style_transfer'
```

Do not change any existing constants.

---

### File 5: `ai_editor/vision_template/__init__.py` (MODIFY existing)

Add exports for the new public symbols:

```python
from .neural_transfer_pipeline import run_neural_style_transfer, NeuralTransferError
from .style_renderer import train_style_renderer, apply_style_renderer, StyleUNet
from .overlay_replicator import extract_overlays, apply_overlays, OverlayManifest
```

Do not remove any existing exports.

---

## Dependencies

All of these are either already in `requirements.txt` or are standard:
- `torch` — already present
- `torchvision` — add to `requirements.txt` if not already there (for VGG16
  perceptual loss; gracefully degrade if unavailable)
- `opencv-python` (`cv2`) — already present
- `numpy` — already present

Do not add any other dependencies.

---

## Constraints

- No FFmpeg subprocess calls anywhere in the new code.
- No Shotstack API calls anywhere in the new code.
- No LLM API calls anywhere in the new code.
- All video I/O uses `cv2.VideoCapture` and `cv2.VideoWriter` only.
- All model training and inference uses PyTorch only.
- The entire pipeline must be importable and runnable without a GPU
  (device='cpu' must always work).
- Do not write any test files.
- Do not modify any file outside the list above.
- All new code must be typed (Python type hints on all function signatures).
- Handle the case where `torch` is not installed: wrap imports in try/except
  and raise `ImportError` with a clear message if torch is missing.

---

## Acceptance check (run manually after implementation)

```python
from ai_editor.vision_template import run_neural_style_transfer

result = run_neural_style_transfer(
    donor_video_path='path/to/donor.mp4',
    content_video_path='path/to/content.mp4',
    out_dir='./transfer_output',
    epochs=10,        # low for quick smoke test
    process_size=240, # low resolution for speed
)
print(result)
# Should print dict with all 5 keys and no exceptions raised
```

If the above runs without error and produces a non-empty `.mp4` file at
`result['final_output_path']`, the implementation is correct.
