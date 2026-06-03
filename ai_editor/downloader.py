"""
Video Downloader and Clipper Module

Handles downloading YouTube/TikTok videos and clipping them based on timestamps.
Replaces the Google Drive integration with a local file-based workflow.
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import json
from urllib.parse import urlparse


class VideoDownloadError(Exception):
    """Raised when video download fails."""
    pass


class VideoClapError(Exception):
    """Raised when video clipping fails."""
    pass


def _is_youtube_url(url: str) -> bool:
    try:
        host = (urlparse(str(url)).netloc or "").lower()
    except Exception:
        return False
    return any(
        h in host
        for h in [
            "youtube.com",
            "www.youtube.com",
            "m.youtube.com",
            "youtu.be",
            "www.youtu.be",
        ]
    )


def _format_hms(seconds: float) -> str:
    total = max(0.0, float(seconds))
    h = int(total // 3600)
    m = int((total % 3600) // 60)
    s = total - (h * 3600 + m * 60)
    # Keep millisecond precision so cuts can be accurate.
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def _find_download_output(expected_path: str) -> str:
    if os.path.exists(expected_path):
        return expected_path
    base, _ext = os.path.splitext(expected_path)
    parent = os.path.dirname(expected_path) or "."
    prefix = os.path.basename(base)
    candidates = [
        os.path.join(parent, name)
        for name in os.listdir(parent)
        if name.startswith(prefix + ".")
    ]
    if not candidates:
        raise VideoDownloadError(f"Downloaded clip not found: {expected_path}")
    candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return candidates[0]


def _run_yt_dlp_command(cmd: List[str]) -> Optional[str]:
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        return None
    except subprocess.CalledProcessError as e:
        return e.stderr.decode() if isinstance(e.stderr, bytes) else str(e.stderr)
    except FileNotFoundError as e:
        raise VideoDownloadError("yt-dlp not found. Install with: pip install yt-dlp") from e


def download_video_section(
    url: str,
    output_dir: str,
    filename: str,
    start_time: float,
    end_time: float,
) -> str:
    """
    Download only the requested section from a YouTube URL using yt-dlp/ffmpeg seek.
    Falls back to caller-managed logic if this fails.
    """
    os.makedirs(output_dir, exist_ok=True)
    duration = float(end_time) - float(start_time)
    if duration <= 0:
        raise VideoDownloadError("End time must be greater than start time for section download.")

    output_path = os.path.join(output_dir, filename)
    section = f"*{_format_hms(start_time)}-{_format_hms(end_time)}"
    section_mode = str(os.getenv("YTDLP_SECTION_MODE", "fast")).strip().lower()
    print(
        f"[downloader] Section download via yt-dlp: {url} "
        f"{start_time:.3f}s-{end_time:.3f}s -> {output_path}"
    )

    attempts = []
    if section_mode != "accurate":
        attempts.append((
            "fast",
            [
                "yt-dlp",
                "--no-playlist",
                "--extractor-args", "youtube:player_client=ios,android,web",
                "-f", "b[ext=mp4]/b",
                "--download-sections", section,
                "-o", output_path,
                url,
            ],
        ))
    attempts.append((
        "accurate",
        [
            "yt-dlp",
            "--no-playlist",
            "--extractor-args", "youtube:player_client=ios,android,web",
            "-f", "bv*+ba/b",
            "--merge-output-format", "mp4",
            "--download-sections", section,
            "--force-keyframes-at-cuts",
            "-o", output_path,
            url,
        ],
    ))

    last_error = None
    for mode_name, cmd in attempts:
        print(f"[downloader] Trying {mode_name} section mode")
        last_error = _run_yt_dlp_command(cmd)
        if last_error is None:
            break
        print(f"[downloader] {mode_name} section mode failed, falling back")
    if last_error is not None:
        raise VideoDownloadError(f"yt-dlp section download failed: {last_error}")

    resolved_path = _find_download_output(output_path)
    probe = _probe_media(resolved_path)
    if not probe["has_video"]:
        raise VideoDownloadError(f"Section clip has no video stream: {resolved_path}")
    file_size_mb = os.path.getsize(resolved_path) / (1024 * 1024)
    print(
        f"✓ Section clip created: {resolved_path} ({file_size_mb:.1f} MB, {duration:.1f}s) "
        f"| has_audio={probe['has_audio']}"
    )
    return resolved_path


def _probe_media(path: str) -> Dict:
    """
    Probe media streams/format using ffprobe.

    Returns:
        Dict: {
            "has_video": bool,
            "has_audio": bool,
            "streams": list,
            "format": dict
        }
    """
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout or "{}")
        streams = data.get("streams", []) or []
        has_video = any(str(s.get("codec_type", "")).lower() == "video" for s in streams)
        has_audio = any(str(s.get("codec_type", "")).lower() == "audio" for s in streams)
        return {
            "has_video": has_video,
            "has_audio": has_audio,
            "streams": streams,
            "format": data.get("format", {}) or {},
        }
    except FileNotFoundError as e:
        raise VideoDownloadError("ffprobe not found. Install from: https://ffmpeg.org/download.html") from e
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else str(e.stderr)
        raise VideoDownloadError(f"ffprobe failed for {path}: {stderr}")
    except json.JSONDecodeError as e:
        raise VideoDownloadError(f"ffprobe returned invalid JSON for {path}: {e}")


def download_video(url: str, output_dir: str, filename: Optional[str] = None) -> str:
    """
    Download a video from YouTube or TikTok.

    Args:
        url (str): YouTube or TikTok URL
        output_dir (str): Directory to save the video
        filename (str, optional): Custom filename. If None, yt-dlp will choose.

    Returns:
        str: File path to the downloaded video

    Raises:
        VideoDownloadError: If download fails
    """
    os.makedirs(output_dir, exist_ok=True)

    try:
        # Build yt-dlp command
        output_template = os.path.join(output_dir, "%(title)s.%(ext)s")
        if filename:
            output_template = os.path.join(output_dir, filename)

        cmd = [
            "yt-dlp",
            "--no-playlist",
            "--extractor-args", "youtube:player_client=ios,android,web",
            "-f", "bv*+ba/b",
            "--merge-output-format", "mp4",
            "-o", output_template,
            url,
        ]

        print(f"[downloader] Downloading: {url}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        # Find the downloaded file
        if filename:
            filepath = os.path.join(output_dir, filename)
        else:
            # When yt-dlp auto-names, we need to find the file
            files = [f for f in os.listdir(output_dir) if f.startswith("%(title)s") == False]
            if not files:
                raise VideoDownloadError("Downloaded file not found in output directory")
            filepath = os.path.join(output_dir, files[0])

        if not os.path.exists(filepath):
            raise VideoDownloadError(f"Downloaded file not found: {filepath}")

        probe = _probe_media(filepath)
        if not probe["has_video"]:
            raise VideoDownloadError(f"Downloaded file has no video stream: {filepath}")
        if not probe["has_audio"]:
            raise VideoDownloadError(
                "Downloaded file has no audio stream after yt-dlp merge. "
                "Try a different source URL or format."
            )

        file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
        print(f"✓ Downloaded: {filepath} ({file_size_mb:.1f} MB) | has_audio={probe['has_audio']}")

        return filepath

    except subprocess.CalledProcessError as e:
        error_msg = f"yt-dlp failed: {e.stderr}"
        print(f"✗ {error_msg}")
        raise VideoDownloadError(error_msg)
    except FileNotFoundError:
        raise VideoDownloadError(
            "yt-dlp not found. Install with: pip install yt-dlp"
        )
    except Exception as e:
        raise VideoDownloadError(f"Download error: {str(e)}")


def extract_audio(video_path: str, output_dir: str, audio_filename: str = "audio.mp3") -> str:
    """
    Extract audio track from a video file.

    Args:
        video_path (str): Path to video file
        output_dir (str): Directory to save audio
        audio_filename (str): Output audio filename

    Returns:
        str: Path to extracted audio file

    Raises:
        VideoClapError: If extraction fails
    """
    os.makedirs(output_dir, exist_ok=True)
    audio_path = os.path.join(output_dir, audio_filename)

    try:
        cmd = [
            "ffmpeg",
            "-i", video_path,
            "-vn",  # Disable video output
            "-map", "0:a:0?",  # First audio stream if present; don't fail if missing
            "-c:a", "libmp3lame",
            "-q:a", "2",  # High quality VBR
            "-y",  # Overwrite output file
            audio_path,
        ]

        print(f"[downloader] Extracting audio to: {audio_path}")
        subprocess.run(cmd, capture_output=True, check=True)

        if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
            raise VideoClapError(
                "Audio extraction failed: source has no usable audio stream."
            )

        print(f"✓ Audio extracted: {audio_path}")
        return audio_path

    except subprocess.CalledProcessError as e:
        raise VideoClapError(f"ffmpeg audio extraction failed: {e.stderr.decode()}")
    except FileNotFoundError:
        raise VideoClapError("ffmpeg not found. Install from: https://ffmpeg.org/download.html")
    except Exception as e:
        raise VideoClapError(f"Audio extraction error: {str(e)}")


def extract_audio_segment(
    source_path: str,
    output_dir: str,
    audio_filename: str,
    start_time: float,
    end_time: Optional[float] = None,
) -> str:
    """
    Extract a segment of audio from a media file (video or audio).

    Args:
        source_path (str): Path to source media file
        output_dir (str): Directory to save audio
        audio_filename (str): Output audio filename
        start_time (float): Start time in seconds
        end_time (float, optional): End time in seconds (if None, extract to end)

    Returns:
        str: Path to extracted audio segment

    Raises:
        VideoClapError: If extraction fails
    """
    os.makedirs(output_dir, exist_ok=True)
    audio_path = os.path.join(output_dir, audio_filename)

    try:
        start = max(0.0, float(start_time or 0.0))
        duration = None
        if end_time is not None:
            end = float(end_time)
            if end <= start:
                raise VideoClapError("Audio segment end time must be greater than start time.")
            duration = end - start

        cmd = [
            "ffmpeg",
            "-ss",
            str(start),
            "-i",
            source_path,
        ]
        if duration is not None:
            cmd += ["-t", str(duration)]
        cmd += [
            "-vn",
            "-map",
            "0:a:0?",
            "-c:a",
            "libmp3lame",
            "-q:a",
            "2",
            "-y",
            audio_path,
        ]

        print(f"[downloader] Extracting audio segment to: {audio_path}")
        subprocess.run(cmd, capture_output=True, check=True)

        if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
            raise VideoClapError("Audio extraction failed: source has no usable audio stream.")

        print(f"✓ Audio segment extracted: {audio_path}")
        return audio_path

    except subprocess.CalledProcessError as e:
        raise VideoClapError(f"ffmpeg audio segment extraction failed: {e.stderr.decode()}")
    except FileNotFoundError:
        raise VideoClapError("ffmpeg not found. Install from: https://ffmpeg.org/download.html")
    except Exception as e:
        raise VideoClapError(f"Audio segment extraction error: {str(e)}")


def clip_video(
    video_path: str,
    output_path: str,
    start_time: float,
    end_time: float,
) -> str:
    """
    Clip a video file between two timestamps.

    Args:
        video_path (str): Path to input video
        output_path (str): Path for output clip
        start_time (float): Start time in seconds
        end_time (float): End time in seconds

    Returns:
        str: Path to clipped video

    Raises:
        VideoClapError: If clipping fails
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    try:
        duration = end_time - start_time
        if duration <= 0:
            raise VideoClapError("End time must be greater than start time")

        cmd = [
            "ffmpeg",
            "-i", video_path,
            "-ss", str(start_time),
            "-t", str(duration),
            "-c:v", "libx264",
            "-c:a", "aac",
            "-b:a", "192k",
            "-y",  # Overwrite output
            output_path,
        ]

        print(f"[downloader] Clipping: {start_time}s to {end_time}s → {output_path}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        if not os.path.exists(output_path):
            raise VideoClapError("Clip file not created")

        probe = _probe_media(output_path)
        file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(
            f"✓ Clip created: {output_path} ({file_size_mb:.1f} MB, {duration:.1f}s) "
            f"| has_audio={probe['has_audio']}"
        )

        return output_path

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode() if isinstance(e.stderr, bytes) else str(e.stderr)
        raise VideoClapError(f"ffmpeg clipping failed: {error_msg}")
    except FileNotFoundError:
        raise VideoClapError("ffmpeg not found. Install from: https://ffmpeg.org/download.html")
    except Exception as e:
        raise VideoClapError(f"Clipping error: {str(e)}")


def download_and_clip(
    sources: List[Dict],
    output_dir: str,
) -> Dict:
    """
    Download videos and clip them based on specified segments.

    Args:
        sources (List[Dict]): List of source specifications with format:
            [
                {
                    "label": 1,
                    "url": "https://youtube.com/watch?v=...",
                    "segments": [
                        {"start": 12.5, "end": 29.0},
                        {"start": 40, "end": 55}
                    ]
                },
                ...
            ]
        output_dir (str): Base directory for output clips

    Returns:
        Dict: {
            "success": bool,
            "clips": [
                {"label": 1, "segment": 0, "path": "/path/to/clip_001.mp4"},
                {"label": 1, "segment": 1, "path": "/path/to/clip_002.mp4"},
                ...
            ],
            "error": str (if not successful)
        }
    """
    os.makedirs(output_dir, exist_ok=True)
    clips = []
    downloaded_videos = {}  # Cache downloaded videos by URL
    clip_counter = 1

    try:
        for source in sources:
            url = source.get("url")
            label = source.get("label", "unknown")
            segments = source.get("segments", [])

            if not url:
                return {
                    "success": False,
                    "error": f"Source missing URL: {source}",
                    "clips": [],
                }

            # If no segments specified, use the whole video
            if not segments:
                # Download video once per unique URL
                if url not in downloaded_videos:
                    try:
                        video_path = download_video(url, output_dir, f"download_{label}.mp4")
                        downloaded_videos[url] = video_path
                    except VideoDownloadError as e:
                        return {
                            "success": False,
                            "error": f"Failed to download {url}: {str(e)}",
                            "clips": [],
                        }
                video_path = downloaded_videos[url]
                clips.append({
                    "label": label,
                    "segment": 0,
                    "path": video_path,
                    "is_full_video": True,
                })
                clip_counter += 1
            else:
                # Clip each segment
                for segment_idx, segment in enumerate(segments):
                    start = segment.get("start", 0)
                    end = segment.get("end")

                    if end is None or start >= end:
                        return {
                            "success": False,
                            "error": f"Invalid segment for label {label}: start={start}, end={end}",
                            "clips": [],
                        }

                    # Name clips predictably: clip_001.mp4, clip_002.mp4, etc.
                    clip_filename = f"clip_{clip_counter:03d}.mp4"
                    clip_path = os.path.join(output_dir, clip_filename)

                    try:
                        if _is_youtube_url(url):
                            # Fast path: directly ask yt-dlp/ffmpeg to download only the time range.
                            clipped_path = download_video_section(
                                url=url,
                                output_dir=output_dir,
                                filename=clip_filename,
                                start_time=float(start),
                                end_time=float(end),
                            )
                        else:
                            raise VideoDownloadError("non-youtube")
                    except VideoDownloadError:
                        # Fallback path: full download once + local ffmpeg clipping.
                        if url not in downloaded_videos:
                            try:
                                video_path = download_video(url, output_dir, f"download_{label}.mp4")
                                downloaded_videos[url] = video_path
                            except VideoDownloadError as e:
                                return {
                                    "success": False,
                                    "error": f"Failed to download {url}: {str(e)}",
                                    "clips": [],
                                }
                        video_path = downloaded_videos[url]
                        try:
                            clipped_path = clip_video(video_path, clip_path, start, end)
                        except VideoClapError as e:
                            return {
                                "success": False,
                                "error": f"Failed to clip segment {segment_idx} of label {label}: {str(e)}",
                                "clips": [],
                            }
                    except VideoClapError as e:
                        return {
                            "success": False,
                            "error": f"Failed to clip segment {segment_idx} of label {label}: {str(e)}",
                            "clips": [],
                        }

                    clips.append({
                        "label": label,
                        "segment": segment_idx,
                        "path": clipped_path,
                        "start": start,
                        "end": end,
                        "is_full_video": False,
                    })
                    clip_counter += 1

        print(f"\n✓ Successfully created {len(clips)} clips from {len(downloaded_videos)} source(s)")

        return {
            "success": True,
            "clips": clips,
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error in download_and_clip: {str(e)}",
            "clips": [],
        }


def cleanup_directory(path: str) -> bool:
    """
    Safely delete a directory and all its contents.

    Args:
        path (str): Directory path to delete

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        if os.path.isdir(path):
            import shutil
            shutil.rmtree(path)
            print(f"✓ Cleaned up: {path}")
            return True
        return False
    except Exception as e:
        print(f"✗ Cleanup failed for {path}: {str(e)}")
        return False
