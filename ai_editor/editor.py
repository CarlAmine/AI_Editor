import os
import json
import time
import requests
from datetime import datetime
from typing import List, Dict, Optional, Union, Any
from dataclasses import dataclass, asdict
import shotstack_sdk as shotstack
from shotstack_sdk.api import edit_api
from shotstack_sdk.model.soundtrack import Soundtrack
from shotstack_sdk.model.video_asset import VideoAsset
from shotstack_sdk.model.title_asset import TitleAsset
from shotstack_sdk.model.clip import Clip
from shotstack_sdk.model.track import Track
from shotstack_sdk.model.timeline import Timeline
from shotstack_sdk.model.output import Output
from shotstack_sdk.model.edit import Edit
from shotstack_sdk.model.transition import Transition
from shotstack_sdk.model.offset import Offset


def create_and_render_video(
    api_key: str,
    video_urls: List[str],
    project_title: str = "My Pipeline Video",
    overlay_text: List[str] = [],
    soundtrack_url: Optional[str] = None,
    music_mode: str = "original",
    resolution: str = "1080x1920",
    wait_for_render: bool = True,
    overlay_plan: Optional[List[Dict[str, Any]]] = None,
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

    # --- 3. Logic: Prepare Project Data ---
    print(f"Initializing Project: {project_title}")

    # NEW: Dynamically fetch durations instead of hardcoding 5.0
    clips = []
    for url in video_urls:
        print(f"Probing metadata for: {url}...")
        actual_duration = get_video_duration(api_key, url)
        clips.append(VideoClip(url=url, duration=actual_duration))

    total_video_duration = sum(c.duration for c in clips)
    print(f"Total assembled video duration: {total_video_duration:.1f}s from {len(clips)} clips")

    # Process Text Overlays
    # Priority 1: Use an explicit overlay_plan (timestamps from analyzer + LLM).
    # Priority 2: Fall back to evenly-spaced overlays based on overlay_text.
    text_overlays: List[TextOverlay] = []

    if overlay_plan:
        print(f"Using overlay_plan with {len(overlay_plan)} entries.")
        
        # Calculate the original video duration from overlay timestamps
        # (the max timestamp indicates the source video length)
        max_overlay_ts = max((float(item.get("timestamp", 0.0)) for item in overlay_plan if "timestamp" in item), default=total_video_duration)
        
        # If original duration differs from assembled duration, rescale timestamps proportionally
        if max_overlay_ts > 0 and abs(max_overlay_ts - total_video_duration) > 0.5:
            scale_factor = total_video_duration / max_overlay_ts
            print(f"Rescaling overlay timestamps: {max_overlay_ts:.1f}s → {total_video_duration:.1f}s (factor: {scale_factor:.2f})")
        else:
            scale_factor = 1.0
        
        for item in overlay_plan:
            try:
                ts = float(item.get("timestamp", 0.0)) * scale_factor
            except (TypeError, ValueError):
                continue

            if ts < 0 or ts > total_video_duration:
                print(f"Skipping overlay at {ts:.1f}s (outside video duration)")
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

            # Use explicit duration from the plan when available, otherwise default to 3.0
            try:
                dur = float(item.get("duration", 3.0))
            except (TypeError, ValueError):
                dur = 3.0

            text_overlays.append(
                TextOverlay(
                    text=text,
                    start_time=ts,
                    duration=dur,
                    position=position,
                )
            )

    # Fallback: derive overlays purely from overlay_text if no valid plan was provided.
    if not text_overlays and overlay_text:
        print("No valid overlay_plan; falling back to prompt-based overlay_text.")
        interval = total_video_duration / (len(overlay_text) + 1)
        for i, text in enumerate(overlay_text):
            text_overlays.append(
                TextOverlay(
                    text=text,
                    start_time=(i + 1) * interval - 1.5,
                    duration=min(3.0, max(0.5, interval - 0.1)),
                    position="center" if i % 2 == 0 else "bottom",
                )
            )

    # If an overlay_plan was provided, adjust durations so overlays do not
    # unintentionally extend past the next planned timestamp while preserving
    # simultaneous overlays that share the same timestamp (e.g., top+bottom titles).
    if text_overlays:
        # Sort overlays by start time for duration clamping logic
        text_overlays.sort(key=lambda o: o.start_time)

        for i, o in enumerate(text_overlays):
            # Find the next overlay that has a strictly greater timestamp
            next_start = None
            for j in range(i + 1, len(text_overlays)):
                if text_overlays[j].start_time > o.start_time:
                    next_start = text_overlays[j].start_time
                    break

            if next_start is None:
                next_start = total_video_duration

            if next_start == total_video_duration:
                # last overlay – give it a sensible minimum duration (up to 3s or
                # until video end, whichever is shorter) so it isn't virtually
                # invisible at the very end.
                max_dur = min(3.0, max(0.1, total_video_duration - o.start_time))
            else:
                # Allow overlay to last until just before the next different timestamp
                max_dur = max(0.1, next_start - o.start_time - 0.05)
                # Clamp to remaining video length as well
                max_dur = min(max_dur, max(0.1, total_video_duration - o.start_time))
            # Set duration to span from this overlay to the next (regardless of plan duration)
            o.duration = max_dur

    # --- 4. Logic: Build Shotstack JSON Template ---
    
    def _get_transition(index, total):
        if index == 0:
            return Transition(_in="fade")
        if index == total - 1:
            return Transition(out="fade")
        transitions = ["slideLeft", "slideRight", "zoom", "wipeLeft", "dissolve"]
        return Transition(_in=transitions[index % len(transitions)])

    
    def _get_offset(position):
        if position == "top":
            return Offset(x=0.0, y=-0.7)
        if position == "bottom":
            return Offset(x=0.0, y=0.7)
        return Offset(x=0.0, y=0.0)

    # Build Timeline
    # prepare both video and text clip lists first
    video_clips_objs = []
    current_time = 0.0
    for i, clip in enumerate(clips):
        vid_asset = VideoAsset(src=clip.url, trim=0.0)
        shotstack_clip = Clip(
            asset=vid_asset,
            start=current_time,
            length=clip.duration,
            fit="cover",
            position="center",
            transition=_get_transition(i, len(clips))
        )
        video_clips_objs.append(shotstack_clip)
        current_time += clip.duration

    text_clips_objs = []
    if text_overlays:
        # ensure no extremely short durations
        for o in text_overlays:
            remaining = total_video_duration - o.start_time
            if o.duration < 0.5 and remaining > 0.1:
                o.duration = min(0.5, remaining)
        for overlay in text_overlays:
            title_asset = TitleAsset(
                text=overlay.text,
                style="minimal",
                size="medium"
            )
            t_clip = Clip(
                asset=title_asset,
                start=overlay.start_time,
                length=overlay.duration,
                offset=_get_offset(overlay.position),
                transition=Transition(_in="fade", out="fade")
            )
            text_clips_objs.append(t_clip)

    # build timeline tracks with text FIRST so it renders ABOVE video
    tracks = []
    if text_clips_objs:
        tracks.append(Track(clips=text_clips_objs))
    tracks.append(Track(clips=video_clips_objs))

    # Soundtrack handling
    soundtrack = None
    if music_mode == "custom" and soundtrack_url:
        # Use provided custom music
        soundtrack = Soundtrack(src=soundtrack_url, effect="fadeOut", volume=0.5)
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
                "dashboard_url": f"https://dashboard.shotstack.io/edit/{render_id}"
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
                        print("Render Complete!")
                        result_data['status'] = 'done'
                        result_data['url'] = data['url']
                        return result_data
                    elif status == 'failed':
                        print(" Render Failed.")
                        result_data['status'] = 'failed'
                        result_data['error'] = data.get('error')
                        return result_data
                    else:
                        print(f"   Status: {status}...")
                
                attempts += 1
            
            result_data['status'] = 'timeout'
            return result_data

    except Exception as e:
        print(f"Error during rendering: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

