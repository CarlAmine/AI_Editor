import os
import json
import time
import requests
import textwrap
import copy
from datetime import datetime
from typing import List, Dict, Optional, Union, Any
from dataclasses import dataclass, asdict
import shotstack_sdk as shotstack
from shotstack_sdk.api import edit_api
from shotstack_sdk.model.soundtrack import Soundtrack
from shotstack_sdk.model.video_asset import VideoAsset
from shotstack_sdk.model.html_asset import HtmlAsset
from shotstack_sdk.model.clip import Clip
from shotstack_sdk.model.track import Track
from shotstack_sdk.model.timeline import Timeline
from shotstack_sdk.model.output import Output
from shotstack_sdk.model.edit import Edit
from shotstack_sdk.model.transition import Transition
from shotstack_sdk.model.offset import Offset

MIN_TEXT_DURATION = 1.2
SAFE_OFFSET_LIMIT = 0.8


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _is_video_clip(clip: Dict[str, Any]) -> bool:
    return (clip.get("asset") or {}).get("type") == "video"


def _is_title_clip(clip: Dict[str, Any]) -> bool:
    return (clip.get("asset") or {}).get("type") in {"title", "text", "html", "image"}


def _is_audio_clip(clip: Dict[str, Any]) -> bool:
    return (clip.get("asset") or {}).get("type") == "audio"


def _wrap_text_for_html(text: str, wrap_width: int) -> str:
    words = str(text).split()
    lines = []
    current = []
    for word in words:
        candidate = " ".join(current + [word]).strip()
        if len(candidate) <= wrap_width:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return "<br/>".join(lines[:3])


def normalize_tracks(edit: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Ensure video track(s) are first and overlay/title track(s) follow.
    Returns warnings list.
    """
    warnings = []
    tracks = edit.get("tracks") or []
    overlay_tracks = []
    video_tracks = []
    audio_tracks = []
    other_tracks = []
    for t in tracks:
        clips = t.get("clips") or []
        if any(_is_title_clip(c) for c in clips):
            overlay_tracks.append(t)
        elif any(_is_video_clip(c) for c in clips):
            video_tracks.append(t)
        elif any(_is_audio_clip(c) for c in clips):
            audio_tracks.append(t)
        else:
            other_tracks.append(t)

    new_tracks = overlay_tracks + video_tracks + audio_tracks + other_tracks
    if new_tracks != tracks:
        edit["tracks"] = new_tracks
        warnings.append(
            {
                "code": "TRACK_ORDER_FIXED",
                "message": "Reordered tracks so overlays are first and video tracks are below.",
                "detail": {
                    "overlay_tracks": len(overlay_tracks),
                    "video_tracks": len(video_tracks),
                    "audio_tracks": len(audio_tracks),
                },
            }
        )
    return warnings


def normalize_text_clips(edit: Dict[str, Any], debug_text_mode: bool = False) -> List[Dict[str, Any]]:
    """
    Enforce minimum title duration, merge rapid word-clips, safe offsets, and transition rules.
    Returns warnings list.
    """
    warnings = []
    tracks = edit.get("tracks") or []

    for track in tracks:
        clips = track.get("clips") or []
        title_idx = [i for i, c in enumerate(clips) if _is_title_clip(c)]
        if not title_idx:
            continue

        # Merge consecutive short "word-like" clips.
        merged = []
        i = 0
        merged_count = 0
        while i < len(clips):
            cur = copy.deepcopy(clips[i])
            if not _is_title_clip(cur):
                merged.append(cur)
                i += 1
                continue
            text = str((cur.get("asset") or {}).get("text", "")).strip()
            start = float(cur.get("start", 0.0))
            length = float(cur.get("length", 0.0))
            end = start + length
            j = i + 1
            pieces = [text]
            while j < len(clips):
                nxt = clips[j]
                if not _is_title_clip(nxt):
                    break
                ntext = str((nxt.get("asset") or {}).get("text", "")).strip()
                if not ntext:
                    break
                nstart = float(nxt.get("start", 0.0))
                nlen = float(nxt.get("length", 0.0))
                # Merge only near back-to-back short word clips.
                word_like = len(ntext.split()) <= 2 and len(ntext) <= 22 and len(" ".join(pieces).split()) <= 8
                if word_like and abs(nstart - end) < 0.05:
                    pieces.append(ntext)
                    end = nstart + nlen
                    j += 1
                    merged_count += 1
                else:
                    break
            cur["asset"]["text"] = " ".join(pieces).strip()
            cur["length"] = max(end - start, length)
            merged.append(cur)
            i = j

        if merged_count > 0:
            warnings.append(
                {
                    "code": "TEXT_CLIPS_MERGED",
                    "message": f"Merged {merged_count} adjacent short title clips.",
                    "detail": {"merged_count": merged_count},
                }
            )

        # Enforce minimum duration + transitions + offset clamp.
        duration_extended = 0
        offsets_clamped = 0
        for c in merged:
            if not _is_title_clip(c):
                continue
            if debug_text_mode:
                c["start"] = float(c.get("start", 0.0))
                c["length"] = 2.0
                c["offset"] = {"x": 0.0, "y": 0.0}
                c["transition"] = None
                continue

            length = float(c.get("length", 0.0))
            if length < MIN_TEXT_DURATION:
                c["length"] = MIN_TEXT_DURATION
                duration_extended += 1

            # Disable transitions unless clip is long enough.
            if float(c.get("length", 0.0)) >= 2.0:
                c["transition"] = {"in": "fade", "out": "fade"}
            else:
                c["transition"] = None

            # Safe offset defaults + clamp.
            off = c.get("offset") or {}
            x = float(off.get("x", 0.0))
            # For 16:9 prefer upper third if unspecified.
            y_default = 0.2 if edit.get("aspect_ratio") == "16:9" else 0.0
            y = float(off.get("y", y_default))
            if edit.get("aspect_ratio") == "16:9" and abs(y) > 0.4:
                y = y_default
            cx = _clamp(x, -SAFE_OFFSET_LIMIT, SAFE_OFFSET_LIMIT)
            cy = _clamp(y, -SAFE_OFFSET_LIMIT, SAFE_OFFSET_LIMIT)
            if cx != x or cy != y:
                offsets_clamped += 1
            c["offset"] = {"x": cx, "y": cy}

        if duration_extended > 0:
            warnings.append(
                {
                    "code": "TEXT_DURATION_EXTENDED",
                    "message": f"Extended {duration_extended} title clip(s) to minimum {MIN_TEXT_DURATION}s.",
                    "detail": {"count": duration_extended, "min_duration": MIN_TEXT_DURATION},
                }
            )
        if offsets_clamped > 0:
            warnings.append(
                {
                    "code": "TEXT_OFFSET_CLAMPED",
                    "message": f"Clamped {offsets_clamped} title clip offset(s) into safe bounds.",
                    "detail": {"count": offsets_clamped, "limit": SAFE_OFFSET_LIMIT},
                }
            )

        track["clips"] = merged

    return warnings


def validate_edit(edit: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Validate/fix edit shape so title clips are visible and overlap video timeline.
    Returns warnings list for applied fixes.
    """
    warnings = []
    tracks = edit.get("tracks") or []
    video_end = 0.0
    for ti, track in enumerate(tracks):
        for c in track.get("clips") or []:
            if _is_video_clip(c):
                start = float(c.get("start", 0.0))
                length = float(c.get("length", 0.0))
                video_end = max(video_end, start + length)

    # Ensure overlay tracks are above (lower index) than video tracks.
    highest_overlay_track = -1
    lowest_video_track = None
    for ti, track in enumerate(tracks):
        has_video = any(_is_video_clip(c) for c in (track.get("clips") or []))
        has_title = any(_is_title_clip(c) for c in (track.get("clips") or []))
        if has_title:
            highest_overlay_track = max(highest_overlay_track, ti)
        if has_video and lowest_video_track is None:
            lowest_video_track = ti

    if highest_overlay_track >= 0 and lowest_video_track is not None and highest_overlay_track > lowest_video_track:
        warnings.extend(normalize_tracks(edit))

    # Ensure title clips overlap video timeline.
    adjusted = 0
    if video_end > 0:
        for track in edit.get("tracks") or []:
            for c in track.get("clips") or []:
                if not _is_title_clip(c):
                    continue
                start = float(c.get("start", 0.0))
                length = float(c.get("length", 0.0))
                if start >= video_end:
                    c["start"] = max(0.0, video_end - max(length, MIN_TEXT_DURATION))
                    adjusted += 1
                elif start + length <= 0:
                    c["start"] = 0.0
                    adjusted += 1
    if adjusted > 0:
        warnings.append(
            {
                "code": "TRACK_ORDER_FIXED",
                "message": f"Adjusted {adjusted} title clip(s) to overlap the visible video timeline.",
                "detail": {"adjusted": adjusted},
            }
        )
    return warnings


def validate_reference_mimic_alignment(edit: Dict[str, Any], tolerance: float = 1e-3) -> List[str]:
    errors: List[str] = []
    tracks = edit.get("tracks") or []
    video_clips: List[Dict[str, Any]] = []
    text_clips: List[Dict[str, Any]] = []
    for track in tracks:
        for clip in track.get("clips") or []:
            if _is_video_clip(clip):
                video_clips.append(clip)
            elif _is_title_clip(clip):
                text_clips.append(clip)
    video_clips.sort(key=lambda c: float(c.get("start", 0.0)))
    text_clips.sort(key=lambda c: float(c.get("start", 0.0)))

    if len(text_clips) != len(video_clips):
        errors.append(f"text/video clip count mismatch: text={len(text_clips)}, video={len(video_clips)}")
    for i, (v, t) in enumerate(zip(video_clips, text_clips), start=1):
        vs = float(v.get("start", 0.0))
        vl = float(v.get("length", 0.0))
        ts = float(t.get("start", 0.0))
        tl = float(t.get("length", 0.0))
        if abs(vs - ts) > tolerance:
            errors.append(f"overlay start mismatch at clip {i}: text={ts:.6f}, video={vs:.6f}")
        if abs(vl - tl) > tolerance:
            errors.append(f"overlay length mismatch at clip {i}: text={tl:.6f}, video={vl:.6f}")

    prev_end = -1.0
    for i, c in enumerate(text_clips, start=1):
        st = float(c.get("start", 0.0))
        en = st + float(c.get("length", 0.0))
        if st < prev_end - tolerance:
            errors.append(f"overlay overlap at clip {i}: start={st:.6f}, previous_end={prev_end:.6f}")
        prev_end = max(prev_end, en)

    if video_clips:
        final_end = max(float(v.get("start", 0.0)) + float(v.get("length", 0.0)) for v in video_clips)
        if text_clips:
            text_final_end = max(float(t.get("start", 0.0)) + float(t.get("length", 0.0)) for t in text_clips)
            if abs(final_end - text_final_end) > tolerance:
                errors.append(
                    f"final end mismatch: text_end={text_final_end:.6f}, video_end={final_end:.6f}"
                )
    return errors


def _ensure_overlay_html_assets(edit: Dict[str, Any]) -> List[Dict[str, Any]]:
    warnings = []
    for track in edit.get("tracks") or []:
        for clip in track.get("clips") or []:
            asset = clip.get("asset") or {}
            if asset.get("type") == "title":
                asset["type"] = "html"
                warnings.append(
                    {
                        "code": "OVERLAY_TITLE_CONVERTED_TO_TEXT",
                        "message": "Converted legacy title overlay to stable HTML text.",
                        "detail": {"start": clip.get("start"), "length": clip.get("length")},
                    }
                )
    return warnings


def create_and_render_video(
    api_key: str,
    video_urls: List[str],
    duration_probe_urls: Optional[List[str]] = None,
    project_title: str = "My Pipeline Video",
    overlay_text: List[str] = [],
    soundtrack_url: Optional[str] = None,
    music_mode: str = "original",
    resolution: str = "1080x1920",
    wait_for_render: bool = True,
    overlay_plan: Optional[List[Dict[str, Any]]] = None,
    overlay_timing: Optional[List[Dict[str, Any]]] = None,
    overlay_script: Optional[Dict[str, Any]] = None,
    timing_mode: str = "ocr_keyframe",
    generation_mode: str = "free_generation_mode",
    canonical_timeline: Optional[List[Dict[str, Any]]] = None,
    force_mobile_safe_text: bool = False,
    mobile_safe_text_mode: bool = False,
    overlay_full_clip: bool = False,
    mute_source_audio: bool = False,
    disable_auto_transitions: bool = False,
    refit_mode: str = "crop_center",
    output_mode: str = "crop_to_9x16",
    debug_text_visibility: bool = False,
    debug_render_spec_path: Optional[str] = None,
    debug_overlay_timing_path: Optional[str] = None,
) -> Dict:
    """
    Pipeline function to assemble clips, add text/music, and render a video using Shotstack.

    Args:
        api_key (str): Shotstack API Key (Stage or Production).
        video_urls (List[str]): List of public URLs to video clips.
        project_title (str): Title for metadata.
        overlay_text (List[str]): List of text lines to display sequentially over the video.
        soundtrack_url (str, optional): URL to an MP3/Audio file. Defaults to a stock upbeat track if None.
        resolution (str): Output resolution (e.g., "1080x1920", "1920x1080").
        wait_for_render (bool): If True, polls API until complete. If False, returns ID immediately.

    Returns:
        Dict: Contains 'success', 'render_id', 'status', and 'url' (if waited).
    """

    # --- 1. Configuration & Constants ---
    HOST = "https://api.shotstack.io/stage"  # Change to "production" if needed

    def get_video_duration(api_key: str, url: str) -> float:
        """Fetches the duration of a remote video file using OpenCV.

        Opens the URL with cv2.VideoCapture and computes frames/fps.  If
        probing fails we return a conservative 5‑second default so the
        pipeline still works.
        """
        print("[duration probe] using OpenCV")
        try:
            import cv2
            cap = cv2.VideoCapture(url)
            if cap.isOpened():
                fps = cap.get(cv2.CAP_PROP_FPS) or 0
                frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
                cap.release()
                if fps > 0 and frames > 0:
                    duration = frames / fps
                    print(f"✓ Duration (OpenCV): {duration:.2f}s")
                    return float(duration)
                else:
                    print(f"OpenCV opened URL but returned fps={fps}, frames={frames}")
            else:
                print("OpenCV failed to open the URL")
        except Exception as e:
            print(f"OpenCV probe error: {e}")

        print(f"Could not determine duration, falling back to 5.0s for {url[:50]}...")
        return 5.0  # Fallback default

    # Default Assets (Fallback)
    DEFAULT_MUSIC = "https://shotstack-assets.s3-ap-southeast-2.amazonaws.com/music/positive.mp3"
    
    # --- 2. Data Models (Simplified) ---
    @dataclass
    class VideoClip:
        url: str
        duration: float = 5.0
        start_time: float = 0.0

    @dataclass
    class TextOverlay:
        text: str
        start_time: float
        duration: float = 3.0
        position: str = "center"
        transition: Optional[Dict[str, Any]] = None

    def _build_clip_anchored_overlays(
        clip_specs: List[Dict[str, Any]],
        texts: List[str],
        out_warnings: List[Dict[str, Any]],
    ) -> List[TextOverlay]:
        overlays_out: List[TextOverlay] = []
        if not clip_specs or not texts:
            return overlays_out
        transition_pad = 0.4
        item_index = 0
        packed_items = 0
        for idx, clip in enumerate(clip_specs):
            clip_start = float(clip.get("start", 0.0))
            clip_end = clip_start + float(clip.get("length", 0.0))
            pad = transition_pad
            safe_start = clip_start + pad
            safe_end = clip_end - pad
            if safe_end - safe_start < 0.7:
                pad = 0.2
                safe_start = clip_start + pad
                safe_end = clip_end - pad
            if safe_end - safe_start < 0.7:
                out_warnings.append(
                    {
                        "code": "OVERLAY_CLIP_SAFE_WINDOW_TOO_SHORT",
                        "message": "Skipped overlay for short clip safe window.",
                        "detail": {"clip_index": idx, "clip_start": clip_start, "clip_end": clip_end},
                    }
                )
                continue

            if idx == 0 and item_index < len(texts):
                title_text = texts[item_index]
                item_index += 1
                title_dur = min(2.5, max(1.5, safe_end - safe_start))
                overlays_out.append(
                    TextOverlay(
                        text=title_text,
                        start_time=safe_start,
                        duration=min(title_dur, safe_end - safe_start),
                        position="top",
                    )
                )
                safe_start = min(safe_end, safe_start + title_dur + 0.1)

            if item_index >= len(texts):
                continue
            remaining = len(texts) - item_index
            remaining_clips = max(1, len(clip_specs) - idx)
            items_for_clip = max(1, (remaining + remaining_clips - 1) // remaining_clips)
            safe_duration = max(0.0, safe_end - safe_start)
            while items_for_clip > 1 and safe_duration / items_for_clip < 0.9:
                items_for_clip -= 1
            if items_for_clip > 1:
                packed_items += items_for_clip
            step = safe_duration / items_for_clip if items_for_clip > 0 else safe_duration
            for local_idx in range(items_for_clip):
                if item_index >= len(texts):
                    break
                start = safe_start + local_idx * step
                dur = max(0.9, step - 0.05) if items_for_clip > 1 else safe_duration
                dur = min(dur, max(0.01, safe_end - start))
                overlays_out.append(
                    TextOverlay(
                        text=texts[item_index],
                        start_time=start,
                        duration=dur,
                        position="top",
                    )
                )
                item_index += 1
            if item_index >= len(texts):
                break
        if packed_items > 0:
            out_warnings.append(
                {
                    "code": "OVERLAY_ITEMS_PACKED",
                    "message": "Packed multiple overlay items into single clips.",
                    "detail": {"items_packed": packed_items},
                }
            )
        return overlays_out

    # --- 3. Logic: Prepare Project Data ---
    print(f"Initializing Project: {project_title}")

    use_reference_mimic = str(generation_mode).lower() == "reference_mimic_mode"
    if use_reference_mimic and not canonical_timeline:
        return {
            "success": False,
            "error": "reference_mimic_mode requires canonical_timeline; refusing heuristic timing fallback.",
        }

    # NEW: Dynamically fetch durations unless strict timeline is provided.
    clips = []
    if use_reference_mimic and canonical_timeline:
        for row in canonical_timeline:
            src = str(row.get("video_src", "")).strip()
            dur = float(row.get("duration", 0.0))
            if not src or dur <= 0:
                return {
                    "success": False,
                    "error": f"Invalid canonical_timeline row (missing src/duration): {row}",
                }
            clips.append(VideoClip(url=src, duration=dur, start_time=float(row.get("start", 0.0))))
        clips.sort(key=lambda c: float(c.start_time))
    else:
        for i, url in enumerate(video_urls):
            probe_url = (
                duration_probe_urls[i]
                if duration_probe_urls and i < len(duration_probe_urls)
                else url
            )
            print(f"Probing metadata for: {probe_url}...")
            actual_duration = get_video_duration(api_key, probe_url)
            clips.append(VideoClip(url=url, duration=actual_duration))

    if use_reference_mimic and clips:
        total_video_duration = max(float(c.start_time) + float(c.duration) for c in clips)
    else:
        total_video_duration = sum(c.duration for c in clips)
    print(f"Total assembled video duration: {total_video_duration:.1f}s from {len(clips)} clips")

    planning_warnings: List[Dict[str, Any]] = []

    # Process Text Overlays
    # Priority 1: Use an explicit overlay_plan (timestamps from analyzer + LLM).
    # Priority 2: Fall back to evenly-spaced overlays based on overlay_text.
    text_overlays: List[TextOverlay] = []

    if use_reference_mimic and overlay_timing:
        for item in sorted(overlay_timing, key=lambda o: float(o.get("start", 0.0))):
            start = float(item.get("start", 0.0))
            end = float(item.get("end", start))
            text = str(item.get("text", "")).strip() or " "
            duration = max(0.0, end - start)
            if duration <= 0:
                continue
            text_overlays.append(
                TextOverlay(
                    text=text,
                    start_time=start,
                    duration=duration,
                    position="top",
                    transition=None,
                )
            )
    elif overlay_plan:
        print(f"Using overlay_plan with {len(overlay_plan)} entries.")
        for item in overlay_plan:
            try:
                ts = float(item.get("timestamp", 0.0))
            except (TypeError, ValueError):
                continue

            if ts < 0 or ts >= total_video_duration:
                continue

            raw_text = item.get("text", "")
            if not raw_text:
                continue
            text = str(raw_text).strip()
            if not text:
                continue

            pos_raw = (item.get("position") or "bottom").lower()
            if pos_raw in {"top", "middle", "center", "bottom"}:
                position = "center" if pos_raw in {"middle", "center"} else pos_raw
            else:
                position = "bottom"

            try:
                dur = float(item.get("duration", 3.0))
            except (TypeError, ValueError):
                dur = 3.0
            dur = max(0.01, min(dur, total_video_duration - ts))
            text_overlays.append(
                TextOverlay(
                    text=text,
                    start_time=ts,
                    duration=dur,
                    position=position,
                    transition=item.get("transition"),
                )
            )

    if not text_overlays and overlay_text:
        interval = total_video_duration / (len(overlay_text) + 1)
        for i, text in enumerate(overlay_text):
            text_overlays.append(
                TextOverlay(
                    text=text,
                    start_time=(i + 1) * interval - 1.5,
                    duration=min(3.0, max(0.5, interval - 0.1)),
                    position="center" if i % 2 == 0 else "bottom",
                    transition=None,
                )
            )

    # --- 4. Logic: Build Shotstack JSON Template ---
    
    def _get_transition(index, total):
        if disable_auto_transitions:
            return None
        if index == 0:
            return Transition(_in="fade")
        if index == total - 1:
            return Transition(out="fade")
        transitions = ["slideLeft", "slideRight", "zoom", "wipeLeft", "wipeRight"]
        return Transition(_in=transitions[index % len(transitions)])

    
    def _get_offset(position):
        if debug_text_visibility:
            return {"x": 0.0, "y": 0.0}
        if position == "top":
            y_default = -0.2
        elif position == "bottom":
            y_default = 0.2
        else:
            y_default = -0.0
        return {"x": 0.0, "y": _clamp(y_default, -0.25, 0.25)}

    def _overlay_width() -> int:
        if resolution == "1920x1080":
            return 700
        if resolution == "1080x1920":
            return 600
        return 660

    def _build_overlay_html(text: str) -> str:
        wrap_width = 18 if output_mode == "crop_to_9x16" else 22
        wrapped = _wrap_text_for_html(text, wrap_width)
        if not wrapped:
            wrapped = "&nbsp;"
        return (
            f"<div style=\"font-family:'Space Grotesk',sans-serif;"
            f"font-size:54px;line-height:1.2;color:#ffffff;text-align:center;\">{wrapped}</div>"
        )

    def _fit_overlay_text(text: str) -> str:
        safe_for_9x16 = mobile_safe_text_mode or force_mobile_safe_text
        if not safe_for_9x16:
            return text
        compact = " ".join(str(text).split())
        wrap_width = 20
        if refit_mode == "crop_center":
            wrap_width = 18
        elif refit_mode == "native_9x16":
            wrap_width = 22
        if len(compact) <= wrap_width:
            return compact
        wrapped = textwrap.wrap(compact, width=wrap_width)
        return "\n".join(wrapped[:2])

    # Build intermediate edit spec (dict), normalize, validate, then convert to SDK objects.
    video_clip_specs = []
    current_time = 0.0
    for i, clip in enumerate(clips):
        start_time = float(clip.start_time) if use_reference_mimic else float(current_time)
        video_clip_specs.append(
            {
                "asset": {"type": "video", "src": clip.url, "trim": 0.0},
                "start": start_time,
                "length": float(clip.duration),
                "fit": "cover",
                "position": "center",
                "transition": None if use_reference_mimic else _get_transition(i, len(clips)),
            }
        )
        if mute_source_audio:
            video_clip_specs[-1]["volume"] = 0.0
        current_time += float(clip.duration)

    if use_reference_mimic and canonical_timeline and not text_overlays:
        for row in canonical_timeline:
            text = str(row.get("text", "")).strip() or " "
            start = float(row.get("text_start", row.get("start", 0.0)))
            end = float(row.get("text_end", row.get("end", start)))
            duration = max(0.0, end - start)
            if duration <= 0:
                continue
            text_overlays.append(
                TextOverlay(
                    text=text,
                    start_time=start,
                    duration=duration,
                    position="top",
                    transition=None,
                )
            )
    elif timing_mode == "clip_anchored":
        script_texts: List[str] = []
        if isinstance(overlay_script, dict):
            title = str(overlay_script.get("title", "")).strip()
            items = [str(x).strip() for x in (overlay_script.get("items") or []) if str(x).strip()]
            if title:
                script_texts.append(title)
            script_texts.extend(items)
        if not script_texts:
            script_texts = [str(o.text).strip() for o in text_overlays if str(o.text).strip()]
        text_overlays = _build_clip_anchored_overlays(video_clip_specs, script_texts, planning_warnings)

    if text_overlays:
        text_overlays.sort(key=lambda o: o.start_time)
    if overlay_full_clip and text_overlays and not use_reference_mimic:
        for overlay, vid_spec in zip(text_overlays, video_clip_specs):
            overlay.start_time = vid_spec["start"]
            overlay.duration = vid_spec["length"]

    text_clip_specs = []
    if text_overlays:
        width = _overlay_width()
        for overlay in text_overlays:
            html_asset = {
                "type": "html",
                "html": _build_overlay_html(overlay.text),
                "css": "div{font-size:54px;letter-spacing:0.5px;font-family:'Space Grotesk',sans-serif;line-height:1.2;}",
                "width": width,
                "height": 220,
                "background": "#00000052",
                "position": overlay.position,
            }
            clip = {
                "asset": html_asset,
                "start": overlay.start_time,
                "length": overlay.duration,
                "offset": _get_offset(overlay.position),
            }
            if overlay.transition and float(overlay.duration) >= 2.0 and not use_reference_mimic:
                clip["transition"] = overlay.transition
            text_clip_specs.append(clip)

    edit_spec = {
        "aspect_ratio": "16:9" if resolution == "1920x1080" else ("9:16" if resolution == "1080x1920" else "1:1"),
        "tracks": [
            {"name": "overlay", "clips": text_clip_specs},
            {"name": "video", "clips": video_clip_specs},
        ],
    }

    warnings = []
    warnings.extend(planning_warnings)
    warnings.extend(normalize_tracks(edit_spec))
    if not use_reference_mimic:
        warnings.extend(normalize_text_clips(edit_spec, debug_text_mode=debug_text_visibility))
    warnings.extend(validate_edit(edit_spec))
    warnings.extend(_ensure_overlay_html_assets(edit_spec))

    if use_reference_mimic and canonical_timeline:
        tol = 1e-6
        expected = sorted(canonical_timeline, key=lambda r: float(r.get("start", 0.0)))
        if len(video_clip_specs) != len(expected):
            return {
                "success": False,
                "error": (
                    f"Reference mimic validation failed: rendered clip count={len(video_clip_specs)} "
                    f"does not match canonical scenes={len(expected)}"
                ),
                "warnings": warnings,
            }
        for i, (clip_spec, row) in enumerate(zip(video_clip_specs, expected), start=1):
            cs = float(clip_spec.get("start", 0.0))
            cl = float(clip_spec.get("length", 0.0))
            rs = float(row.get("start", 0.0))
            rl = float(row.get("duration", row.get("length", 0.0)))
            if abs(cs - rs) > tol:
                return {
                    "success": False,
                    "error": (
                        f"Reference mimic validation failed at clip {i}: start={cs:.9f} "
                        f"expected={rs:.9f}"
                    ),
                    "warnings": warnings,
                }
            if abs(cl - rl) > tol:
                return {
                    "success": False,
                    "error": (
                        f"Reference mimic validation failed at clip {i}: length={cl:.9f} "
                        f"expected={rl:.9f}"
                    ),
                    "warnings": warnings,
                }

    if use_reference_mimic:
        mimic_errors = validate_reference_mimic_alignment(edit_spec)
        if mimic_errors:
            return {
                "success": False,
                "error": "Reference mimic timing validation failed: " + "; ".join(mimic_errors),
                "warnings": warnings,
            }

    # Refit-mode specific overlay safety pass.
    safe_for_9x16 = mobile_safe_text_mode or force_mobile_safe_text
    if safe_for_9x16:
        wrapped_count = 0
        clamped_count = 0
        for t in edit_spec.get("tracks", []):
            for c in t.get("clips", []):
                asset = c.get("asset") or {}
                if asset.get("type") not in {"title", "text", "html"}:
                    continue
                if asset.get("type") in {"title", "text"}:
                    wrapped = _fit_overlay_text(asset.get("text", ""))
                    if wrapped != asset.get("text", ""):
                        wrapped_count += 1
                    asset["text"] = wrapped
                off = c.get("offset") or {"x": 0.0, "y": 0.0}
                x = float(off.get("x", 0.0))
                y = float(off.get("y", 0.0))
                if refit_mode in {"crop_center", "native_9x16"}:
                    cx = 0.0
                    cy = _clamp(y, -0.25, 0.25)
                elif refit_mode == "pad":
                    cx = _clamp(x, -SAFE_OFFSET_LIMIT, SAFE_OFFSET_LIMIT)
                    cy = _clamp(y, -0.35, 0.35)
                else:
                    cx = _clamp(x, -SAFE_OFFSET_LIMIT, SAFE_OFFSET_LIMIT)
                    cy = _clamp(y, -SAFE_OFFSET_LIMIT, SAFE_OFFSET_LIMIT)
                if cx != x or cy != y:
                    clamped_count += 1
                c["offset"] = {"x": cx, "y": cy}
        if wrapped_count > 0:
            warnings.append(
                {
                    "code": "TEXT_WRAPPED_9X16_SAFE",
                    "message": f"Wrapped {wrapped_count} title clip(s) for 9:16 safety.",
                    "detail": {"count": wrapped_count, "refit_mode": refit_mode},
                }
            )
        if clamped_count > 0:
            warnings.append(
                {
                    "code": "TEXT_OFFSET_CLAMPED",
                    "message": f"Clamped {clamped_count} title clip offset(s) for 9:16 safety.",
                    "detail": {"count": clamped_count, "refit_mode": refit_mode},
                }
            )

    if debug_render_spec_path:
        try:
            with open(debug_render_spec_path, "w", encoding="utf-8") as f:
                json.dump(edit_spec, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            print(f"Could not write debug render spec: {e}")

    if debug_overlay_timing_path:
        try:
            timing_rows = []
            for overlay in text_overlays:
                start = float(overlay.start_time)
                length = float(overlay.duration)
                timing_rows.append(
                    {
                        "text": overlay.text,
                        "start": start,
                        "end": start + length,
                    }
                )
            with open(debug_overlay_timing_path, "w", encoding="utf-8") as f:
                json.dump(timing_rows, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Could not write debug overlay timing: {e}")

    # Convert normalized spec to Shotstack SDK objects.
    tracks = []
    for t in edit_spec.get("tracks", []):
        sdk_clips = []
        for c in t.get("clips", []):
            asset = c.get("asset", {})
            if asset.get("type") == "video":
                sdk_asset = VideoAsset(src=asset.get("src"), trim=float(asset.get("trim", 0.0)))
            elif asset.get("type") == "html":
                sdk_asset = HtmlAsset(
                    html=asset.get("html", ""),
                    css=asset.get("css"),
                    width=asset.get("width"),
                    height=asset.get("height"),
                    background=asset.get("background"),
                    position=asset.get("position"),
                )
            elif asset.get("type") in {"title", "text"}:
                text_html = _build_overlay_html(str(asset.get("text", "")))
                sdk_asset = HtmlAsset(
                    html=text_html,
                    css="div{font-size:54px;letter-spacing:0.5px;font-family:'Space Grotesk',sans-serif;line-height:1.2;}",
                    width=_overlay_width(),
                    height=220,
                    background="#00000052",
                    position=asset.get("position", "center"),
                )
            else:
                continue

            trans = c.get("transition")
            sdk_transition = None
            if isinstance(trans, Transition):
                sdk_transition = trans
            elif isinstance(trans, dict) and (trans.get("in") or trans.get("out")):
                sdk_transition = Transition(_in=trans.get("in"), out=trans.get("out"))

            off = c.get("offset")
            sdk_offset = None
            if isinstance(off, dict):
                sdk_offset = Offset(x=float(off.get("x", 0.0)), y=float(off.get("y", 0.0)))

            clip_kwargs = {
                "asset": sdk_asset,
                "start": float(c.get("start", 0.0)),
                "length": float(c.get("length", 0.0)),
            }
            if c.get("fit") is not None:
                clip_kwargs["fit"] = c.get("fit")
            if c.get("position") is not None:
                clip_kwargs["position"] = c.get("position")
            if c.get("volume") is not None:
                clip_kwargs["volume"] = float(c.get("volume"))
            if sdk_offset is not None:
                clip_kwargs["offset"] = sdk_offset
            if sdk_transition is not None:
                clip_kwargs["transition"] = sdk_transition

            sdk_clip = Clip(**clip_kwargs)
            sdk_clips.append(sdk_clip)
        if sdk_clips:
            tracks.append(Track(clips=sdk_clips))

    # Soundtrack handling
    soundtrack = None
    if soundtrack_url and music_mode in {"custom", "original"}:
        effect = "fadeOut" if music_mode == "custom" else None
        soundtrack = Soundtrack(src=soundtrack_url, effect=effect, volume=0.5)
        if music_mode == "original":
            print("[editor] Using reference audio bed from analyzed video")
        else:
            print(f"[editor] Using custom soundtrack: {soundtrack_url}")
    elif music_mode == "original":
        # Keep original audio from clips (don't add separate soundtrack)
        print("[editor] Using original audio from clips (no overlay music)")
        soundtrack = None
    else:
        # Default fallback to a standard track (shouldn't happen in normal flow)
        soundtrack = Soundtrack(src=DEFAULT_MUSIC, effect="fadeOut", volume=0.3)
        print("[editor] Using default soundtrack (fallback)")

    # Timeline Object
    # Shotstack expects a Soundtrack object; if we intend to preserve original
    # audio (no separate soundtrack) we should omit the `soundtrack` field.
    if soundtrack is None:
        timeline = Timeline(
            background="#000000",
            tracks=tracks
        )
    else:
        timeline = Timeline(
            background="#000000",
            soundtrack=soundtrack,
            tracks=tracks
        )

    # Output Settings
    res_width = "1080"  # Shotstack uses simplified resolution strings mostly
    if resolution == "1080x1920":
        aspect = "9:16"
    elif resolution == "1920x1080":
        aspect = "16:9"
    else:
        aspect = "9:16"

    output = Output(
        format="mp4",
        resolution="1080", 
        aspect_ratio=aspect,
        fps=30.0
    )

    edit_object = Edit(timeline=timeline, output=output)

    # --- 5. Execution: Submit to Shotstack ---
    
    try:
        config = shotstack.Configuration(host=HOST)
        config.api_key['DeveloperKey'] = api_key
        
        with shotstack.ApiClient(config) as api_client:
            api_instance = edit_api.EditApi(api_client)
            
            print("Submitting render job to Shotstack...")
            api_response = api_instance.post_render(edit_object)
            
            render_id = api_response['response']['id']
            message = api_response['response']['message']
            print(f"Submitted! Render ID: {render_id}")

            result_data = {
                "success": True,
                "render_id": render_id,
                "status": "queued",
                "message": message,
                "dashboard_url": f"https://dashboard.shotstack.io/edit/{render_id}",
                "warnings": warnings,
            }

            if not wait_for_render:
                return result_data

            # --- 6. Optional: Polling Logic ---
            print("Waiting for render to complete...")
            attempts = 0
            max_attempts = 60
            
            while attempts < max_attempts:
                time.sleep(3)  # Wait between checks
                
                # Check Status
                # Note: We use requests directly here for simple status checking to avoid regenerating API client
                status_url = f"{HOST}/render/{render_id}"
                headers = {"x-api-key": api_key}
                status_resp = requests.get(status_url, headers=headers)
                
                if status_resp.status_code == 200:
                    data = status_resp.json()['response']
                    status = data['status']
                    
                    if status == 'done':
                        url = data.get('url')
                        if not url:
                            print("Render completed without output URL.")
                            result_data['success'] = False
                            result_data['status'] = 'failed'
                            result_data['error'] = "Shotstack returned status=done but no output URL."
                            return result_data
                        print("Render Complete!")
                        result_data['success'] = True
                        result_data['status'] = 'done'
                        result_data['url'] = url
                        return result_data
                    elif status == 'failed':
                        print(" Render Failed.")
                        result_data['success'] = False
                        result_data['status'] = 'failed'
                        result_data['error'] = data.get('error')
                        return result_data
                    else:
                        print(f"   Status: {status}...")
                
                attempts += 1
            
            result_data['success'] = False
            result_data['status'] = 'timeout'
            result_data['error'] = "Render polling timed out before completion."
            return result_data

    except Exception as e:
        print(f"Error during rendering: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

