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


class VideoDownloadError(Exception):
    """Raised when video download fails."""
    pass


class VideoClapError(Exception):
    """Raised when video clipping fails."""
    pass


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
            "-f", "bv*+ba/b",  # Prefer best video+audio, fallback to best combined
            "--merge-output-format",
            "mp4",
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

            # If no segments specified, use the whole video
            if not segments:
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
                        clipped_path = clip_video(video_path, clip_path, start, end)
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
