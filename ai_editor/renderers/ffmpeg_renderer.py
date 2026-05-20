"""FFmpeg-based local video renderer."""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from ai_editor.renderers.base import BaseRenderer


class FFmpegRenderer(BaseRenderer):
    """Local FFmpeg-based video renderer."""

    def __init__(self, ffmpeg_binary: str = "ffmpeg", ffprobe_binary: str = "ffprobe"):
        """Initialize FFmpeg renderer.

        Args:
            ffmpeg_binary: Path to ffmpeg executable.
            ffprobe_binary: Path to ffprobe executable.
        """
        self.ffmpeg = ffmpeg_binary
        self.ffprobe = ffprobe_binary
        self._commands: List[Dict[str, Any]] = []

    def render(
        self,
        render_spec: Dict[str, Any],
        job_id: str,
        job_dir: str,
    ) -> Dict[str, Any]:
        """Render video from render_spec using FFmpeg locally.

        Args:
            render_spec: Normalized render specification with canonical_timeline.
            job_id: Unique job identifier.
            job_dir: Job working directory.

        Returns:
            Dict with success, url, render_id, error, debug_info.
        """
        self._commands = []

        try:
            # Create working directories
            ffmpeg_dir = os.path.join(job_dir, "ffmpeg")
            outputs_dir = os.path.join(job_dir, "outputs")
            os.makedirs(ffmpeg_dir, exist_ok=True)
            os.makedirs(outputs_dir, exist_ok=True)

            # Validate and extract timeline
            canonical_timeline = render_spec.get("canonical_timeline") or []
            if not canonical_timeline:
                return self._failure(
                    "No canonical_timeline found in render_spec",
                    debug_dir=os.path.join(job_dir, "debug"),
                    job_id=job_id,
                )

            # Get resolution and other parameters
            resolution = render_spec.get("resolution", "1080x1920")
            width, height = self._parse_resolution(resolution)
            fps = 30
            codec_settings = {
                "vcodec": "libx264",
                "pix_fmt": "yuv420p",
                "fps": fps,
                "crf": 23,  # Quality (0-51, lower is better)
            }

            # Build temporary clips
            clip_paths = []
            for index, row in enumerate(canonical_timeline):
                clip_path = self._build_normalized_clip(
                    index=index,
                    row=row,
                    output_dir=ffmpeg_dir,
                    width=width,
                    height=height,
                    fps=fps,
                )
                if clip_path:
                    clip_paths.append(clip_path)

            if not clip_paths:
                return self._failure(
                    "Failed to build any normalized clips from canonical_timeline",
                    debug_dir=os.path.join(job_dir, "debug"),
                    job_id=job_id,
                )

            # Concatenate clips
            concat_path = os.path.join(ffmpeg_dir, "concat.txt")
            self._write_concat_file(concat_path, clip_paths)

            concat_output = os.path.join(ffmpeg_dir, "concatenated.mp4")
            if not self._concat_clips(concat_path, concat_output, codec_settings):
                return self._failure(
                    "Failed to concatenate clips",
                    debug_dir=os.path.join(job_dir, "debug"),
                    job_id=job_id,
                )

            # Add audio if needed
            output_file = concat_output
            soundtrack_url = render_spec.get("soundtrack_url")
            if soundtrack_url:
                output_file = os.path.join(ffmpeg_dir, "with_audio.mp4")
                if not self._add_audio(concat_output, soundtrack_url, output_file):
                    return self._failure(
                        "Failed to add audio to video",
                        debug_dir=os.path.join(job_dir, "debug"),
                        job_id=job_id,
                    )

            # Final output
            master_path = os.path.join(outputs_dir, "master.mp4")
            shutil.copy(output_file, master_path)

            # Write debug files
            debug_dir = os.path.join(job_dir, "debug")
            os.makedirs(debug_dir, exist_ok=True)
            self._write_debug_commands(os.path.join(debug_dir, "ffmpeg_commands.json"))
            self._write_debug_summary(
                os.path.join(debug_dir, "ffmpeg_render_summary.json"),
                {
                    "job_id": job_id,
                    "resolution": resolution,
                    "fps": fps,
                    "clip_count": len(clip_paths),
                    "output": master_path,
                    "success": True,
                },
            )

            return {
                "success": True,
                "url": f"/files/{job_id}/outputs/master.mp4",
                "render_id": f"ffmpeg-{job_id}",
                "output_path": master_path,
                "debug_info": {
                    "commands_file": os.path.join(debug_dir, "ffmpeg_commands.json"),
                    "summary_file": os.path.join(debug_dir, "ffmpeg_render_summary.json"),
                },
            }

        except Exception as exc:
            return self._failure(
                str(exc),
                debug_dir=os.path.join(job_dir, "debug"),
                job_id=job_id,
                exception=exc,
            )

    def _build_normalized_clip(
        self,
        index: int,
        row: Dict[str, Any],
        output_dir: str,
        width: int,
        height: int,
        fps: int,
    ) -> Optional[str]:
        """Build a normalized clip from a timeline row.

        Handles:
        - Trimming (row["trim"] or 0)
        - Duration (row["duration"] or row["length"])
        - Scaling/cropping to resolution
        - FPS enforcement
        - Text overlay (row["text"])
        - Codec settings (yuv420p, x264)
        """
        video_src = str(row.get("video_src", "")).strip()
        if not video_src:
            return None

        trim_start = float(row.get("trim", 0.0) or 0.0)
        duration = float(row.get("duration", row.get("length", 0.0)) or 0.0)
        text_overlay = str(row.get("text", "")).strip() if row.get("text") else None

        if duration <= 0:
            return None

        # Download if needed
        if video_src.startswith(("http://", "https://")):
            local_src = os.path.join(output_dir, f"source_{index}.mp4")
            if not self._download_file(video_src, local_src):
                return None
            video_src = local_src

        output_clip = os.path.join(output_dir, f"clip_{index}.mp4")

        # Build filter chain
        filters = []

        # Trim
        if trim_start > 0:
            filters.append(f"[0:v]trim=start={trim_start}:duration={duration}[trimmed]")
            filters.append("[trimmed]fps={fps}[fps_normalized]")
        else:
            filters.append(f"[0:v]fps={fps}[fps_normalized]")

        # Scale and pad
        scale_filter = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black"
        filters.append(f"[fps_normalized]{scale_filter}[scaled]")

        # Text overlay
        if text_overlay:
            # Escape text for drawtext filter
            escaped_text = self._escape_drawtext(text_overlay)
            drawtext = (
                f"[scaled]drawtext=text='{escaped_text}':fontsize=54:fontcolor=white:"
                "x=(w-text_w)/2:y=(h-text_h)/2:borderw=2:bordercolor=black"
                "[with_text]"
            )
            filters.append(drawtext)
            final_filter = "[with_text]format=yuv420p[out]"
        else:
            final_filter = "[scaled]format=yuv420p[out]"
        filters.append(final_filter)

        filter_complex = ";".join(filters)

        # Build command
        cmd = [
            self.ffmpeg,
            "-i", video_src,
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-y",
            output_clip,
        ]

        self._commands.append({
            "index": index,
            "type": "build_clip",
            "input": video_src,
            "output": output_clip,
            "trim_start": trim_start,
            "duration": duration,
            "text_overlay": text_overlay,
            "command": " ".join(cmd),
        })

        # Execute
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                print(f"FFmpeg clip build failed (index {index}): {result.stderr}")
                return None
            return output_clip
        except Exception as exc:
            print(f"FFmpeg clip build exception (index {index}): {exc}")
            return None

    def _concat_clips(self, concat_file: str, output_file: str, codec_settings: Dict[str, Any]) -> bool:
        """Concatenate clips using concat demuxer."""
        cmd = [
            self.ffmpeg,
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c:v", codec_settings.get("vcodec", "libx264"),
            "-preset", "fast",
            "-crf", str(codec_settings.get("crf", 23)),
            "-pix_fmt", codec_settings.get("pix_fmt", "yuv420p"),
            "-y",
            output_file,
        ]

        self._commands.append({
            "type": "concat",
            "input": concat_file,
            "output": output_file,
            "command": " ".join(cmd),
        })

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if result.returncode != 0:
                print(f"FFmpeg concat failed: {result.stderr}")
                return False
            return True
        except Exception as exc:
            print(f"FFmpeg concat exception: {exc}")
            return False

    def _add_audio(self, video_file: str, audio_url: str, output_file: str) -> bool:
        """Add audio to video."""
        audio_file = audio_url
        
        # Download if URL
        if audio_url.startswith(("http://", "https://")):
            audio_file = os.path.join(os.path.dirname(output_file), "audio.aac")
            if not self._download_file(audio_url, audio_file):
                return False

        cmd = [
            self.ffmpeg,
            "-i", video_file,
            "-i", audio_file,
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            "-y",
            output_file,
        ]

        self._commands.append({
            "type": "add_audio",
            "video": video_file,
            "audio": audio_url,
            "output": output_file,
            "command": " ".join(cmd),
        })

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                print(f"FFmpeg add_audio failed: {result.stderr}")
                return False
            return True
        except Exception as exc:
            print(f"FFmpeg add_audio exception: {exc}")
            return False

    def _write_concat_file(self, concat_path: str, clip_paths: List[str]) -> None:
        """Write FFmpeg concat demuxer file."""
        lines = [f"file '{clip}'" for clip in clip_paths]
        with open(concat_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _download_file(self, url: str, output_path: str) -> bool:
        """Download file from URL."""
        try:
            import requests
            response = requests.get(url, timeout=60, stream=True)
            response.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return True
        except Exception as exc:
            print(f"Download failed for {url}: {exc}")
            return False

    def _parse_resolution(self, resolution: str) -> tuple:
        """Parse resolution string to (width, height)."""
        parts = resolution.split("x")
        if len(parts) == 2:
            try:
                return (int(parts[0]), int(parts[1]))
            except ValueError:
                pass
        return (1080, 1920)  # Default mobile

    def _escape_drawtext(self, text: str) -> str:
        """Escape text for FFmpeg drawtext filter."""
        # Escape special characters for drawtext
        text = text.replace("'", "'\\''")
        text = text.replace(":", "\\:")
        text = text.replace("[", "\\[")
        text = text.replace("]", "\\]")
        return text

    def _failure(
        self,
        error_msg: str,
        debug_dir: str,
        job_id: str,
        exception: Optional[Exception] = None,
    ) -> Dict[str, Any]:
        """Write failure debug files and return error result."""
        os.makedirs(debug_dir, exist_ok=True)
        
        error_detail = {
            "stage": "ffmpeg_render",
            "error": error_msg,
            "exception": repr(exception) if exception else None,
            "job_id": job_id,
            "timestamp": json.dumps(self._iso_now()),
        }
        
        self._write_debug_commands(os.path.join(debug_dir, "ffmpeg_commands.json"))
        self._write_debug_error(os.path.join(debug_dir, "ffmpeg_error.json"), error_detail)

        return {
            "success": False,
            "url": None,
            "render_id": None,
            "error": error_msg,
            "debug_info": {
                "error_file": os.path.join(debug_dir, "ffmpeg_error.json"),
                "commands_file": os.path.join(debug_dir, "ffmpeg_commands.json"),
            },
        }

    def _write_debug_commands(self, path: str) -> None:
        """Write FFmpeg commands debug file."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._commands, f, indent=2, ensure_ascii=False)

    def _write_debug_error(self, path: str, error_detail: Dict[str, Any]) -> None:
        """Write FFmpeg error debug file."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(error_detail, f, indent=2, ensure_ascii=False)

    def _write_debug_summary(self, path: str, summary: Dict[str, Any]) -> None:
        """Write FFmpeg render summary debug file."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

    @staticmethod
    def _iso_now() -> str:
        """Return current time as ISO 8601 string."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
