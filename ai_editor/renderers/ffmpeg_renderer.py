"""FFmpeg-based local video renderer."""

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


def _resolve_font_file(style_hint: str = "regular") -> Optional[str]:
    """Return the first usable font file matching the requested style hint.

    style_hint: "impact" | "bold" | "regular"
    Falls back to a less-specific variant when the exact file is not found.
    """
    if style_hint == "impact":
        impact_candidates = [
            os.getenv("FFMPEG_FONT_FILE_IMPACT"),
            r"C:\Windows\Fonts\impact.ttf",
            r"C:\Windows\Fonts\ariblk.ttf",   # Arial Black
            "/usr/share/fonts/truetype/msttcorefonts/Impact.ttf",
            "/usr/share/fonts/truetype/impact.ttf",
            "/Library/Fonts/Impact.ttf",
        ]
        for candidate in impact_candidates:
            if candidate and Path(candidate).exists():
                return candidate
        style_hint = "bold"  # fall through

    if style_hint == "bold":
        bold_candidates = [
            os.getenv("FFMPEG_FONT_FILE_BOLD"),
            r"C:\Windows\Fonts\arialbd.ttf",
            r"C:\Windows\Fonts\ariblk.ttf",   # Arial Black
            r"C:\Windows\Fonts\calibrib.ttf",
            r"C:\Windows\Fonts\segoeuib.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/Library/Fonts/Arial Bold.ttf",
        ]
        for candidate in bold_candidates:
            if candidate and Path(candidate).exists():
                return candidate
        # Fall through to regular

    regular_candidates = [
        os.getenv("FFMPEG_FONT_FILE"),
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    for candidate in regular_candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def _escape_drawtext_path(path: str) -> str:
    """Escape a font file path for FFmpeg drawtext."""
    value = path.replace("\\", "/")
    value = value.replace(":", r"\:")
    value = value.replace("'", r"\'")
    return value


def _escape_drawtext_text(text: str) -> str:
    """Escape overlay text for FFmpeg drawtext."""
    value = str(text or "")
    value = value.replace("\\", r"\\")
    value = value.replace(":", r"\:")
    value = value.replace("'", r"\'")
    value = value.replace("%", r"\%")
    value = value.replace("\n", " ")
    return value


DEFAULT_TEXT_STYLE = {"box": False, "stroke": True, "shadow": False, "font_size": 42}


def _drawtext_style_parts(style: Dict[str, Any], box_color: Optional[str] = None) -> str:
    """Build optional drawtext style fragments."""
    box = bool(style.get("box", False))
    stroke = bool(style.get("stroke", True))
    shadow = bool(style.get("shadow", False))
    parts: List[str] = []
    if box:
        fill = box_color or "black"
        parts.extend([f"box=1", f"boxcolor={fill}@0.5", "boxborderw=10"])
    if stroke:
        parts.extend(["borderw=2", "bordercolor=black@0.6"])
    if shadow:
        parts.extend(["shadowcolor=black@0.45", "shadowx=2", "shadowy=2"])
    return ":".join(parts)


def _map_coord_to_output(
    cx_norm: float,
    cy_norm: float,
    src_w: int,
    src_h: int,
    out_w: int,
    out_h: int,
    refit_mode: str,
) -> tuple:
    """Map a normalised [0-1] source coordinate to the output frame pixel position.

    Handles both crop_center (scale-up then crop) and pad (scale-down then letterbox).
    Returns (out_cx, out_cy) as floats clamped to the output frame.
    """
    if src_w <= 0 or src_h <= 0:
        return cx_norm * out_w, cy_norm * out_h

    if refit_mode == "pad":
        scale = min(out_w / src_w, out_h / src_h)
        scaled_w = src_w * scale
        scaled_h = src_h * scale
        offset_x = (out_w - scaled_w) / 2
        offset_y = (out_h - scaled_h) / 2
        out_cx = cx_norm * src_w * scale + offset_x
        out_cy = cy_norm * src_h * scale + offset_y
    else:  # crop_center (default)
        scale = max(out_w / src_w, out_h / src_h)
        scaled_w = src_w * scale
        scaled_h = src_h * scale
        crop_x = (scaled_w - out_w) / 2
        crop_y = (scaled_h - out_h) / 2
        out_cx = cx_norm * src_w * scale - crop_x
        out_cy = cy_norm * src_h * scale - crop_y

    out_cx = max(0.0, min(float(out_w), out_cx))
    out_cy = max(0.0, min(float(out_h), out_cy))
    return out_cx, out_cy


def _concat_demuxer_path(path: Path) -> str:
    """Normalize a clip path for FFmpeg concat demuxer entries."""
    value = path.resolve().as_posix()
    value = value.replace("'", r"'\''")
    return value


class FFmpegRenderer:
    """Local FFmpeg-based video renderer."""

    def __init__(self, ffmpeg_binary: Optional[str] = None, ffprobe_binary: Optional[str] = None):
        """Initialize FFmpeg renderer.

        Args:
            ffmpeg_binary: Optional path to ffmpeg executable.
            ffprobe_binary: Optional path to ffprobe executable.
        """
        self.ffmpeg = ffmpeg_binary or os.getenv("FFMPEG_BINARY") or "ffmpeg"
        self.ffprobe = ffprobe_binary or os.getenv("FFPROBE_BINARY") or "ffprobe"
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
        warnings = []

        try:
            # Create working directories
            ffmpeg_dir = os.path.join(job_dir, "ffmpeg")
            outputs_dir = os.path.join(job_dir, "outputs")
            debug_dir = os.path.join(job_dir, "debug")
            os.makedirs(ffmpeg_dir, exist_ok=True)
            os.makedirs(outputs_dir, exist_ok=True)
            os.makedirs(debug_dir, exist_ok=True)

            # Validate and extract timeline
            canonical_timeline = render_spec.get("canonical_timeline") or []
            if not canonical_timeline:
                return self._failure(
                    "No canonical_timeline found in render_spec",
                    debug_dir=debug_dir,
                    job_id=job_id,
                )

            # Check for transition metadata and log warning
            has_transitions = False
            for row in canonical_timeline:
                meta = row.get("metadata") or {}
                if "transition_in" in meta or "transition_out" in meta:
                    has_transitions = True
                    break
            if has_transitions:
                msg = "Transitions are currently rendered as hard cuts under FFmpeg."
                warnings.append(msg)

            # Get refit and output modes
            refit_mode = str(render_spec.get("refit_mode", "crop_center")).strip().lower()
            output_mode = str(render_spec.get("output_mode", "crop_to_9x16")).strip().lower()
            
            # Get resolution and other parameters
            resolution = render_spec.get("resolution", "1080x1920")
            width, height = self._parse_resolution(resolution)
            fps = 30
            
            mute_source_audio = bool(render_spec.get("mute_source_audio", False))
            preserve_audio = not mute_source_audio

            filter_plan_clips = []
            for index, row in enumerate(canonical_timeline):
                meta = row.get("metadata") or {}
                filter_plan_clips.append(
                    {
                        "index": index,
                        "start": float(row.get("start", 0.0)),
                        "end": float(row.get("end", row.get("start", 0.0))),
                        "duration": float(row.get("duration", row.get("length", 0.0)) or 0.0),
                        "text": row.get("text"),
                        "text_start": row.get("text_start"),
                        "text_end": row.get("text_end"),
                        "transition_in": meta.get("transition_in"),
                        "transition_out": meta.get("transition_out"),
                        "transition_skipped": True,
                    }
                )

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
                    refit_mode=refit_mode,
                    mute_source_audio=mute_source_audio,
                )
                if clip_path:
                    clip_paths.append(clip_path)
                else:
                    return self._failure(
                        f"Failed to build normalized clip at index {index}",
                        debug_dir=debug_dir,
                        job_id=job_id,
                        warnings=warnings,
                    )

            if not clip_paths:
                return self._failure(
                    "Failed to build any normalized clips from canonical_timeline",
                    debug_dir=debug_dir,
                    job_id=job_id,
                    warnings=warnings,
                )

            build_commands = [
                command for command in self._commands if command.get("type") == "build_clip"
            ]
            for plan_clip, command in zip(filter_plan_clips, build_commands):
                plan_clip["filter_graph"] = command.get("filter_graph")
                plan_clip["command"] = command.get("command")
                plan_clip["retry_without_text"] = command.get("retry_without_text", False)

            self._write_render_filter_plan(
                debug_dir,
                {
                    "provider": "ffmpeg",
                    "transitions_rendered": False,
                    "clips": filter_plan_clips,
                    "concat_commands": [
                        entry for entry in self._commands if entry.get("type") == "concat"
                    ],
                },
            )

            # Concatenate clips
            concat_path = os.path.join(ffmpeg_dir, "concat.txt")
            self._write_concat_file(concat_path, clip_paths)

            concat_output = os.path.join(ffmpeg_dir, "concatenated.mp4")
            codec_settings = {
                "vcodec": "libx264",
                "pix_fmt": "yuv420p",
                "fps": fps,
                "crf": 23,
            }
            if not self._concat_clips(
                concat_path,
                concat_output,
                codec_settings,
                clip_paths=clip_paths,
                preserve_audio=preserve_audio,
            ):
                return self._failure(
                    "Failed to concatenate clips",
                    debug_dir=debug_dir,
                    job_id=job_id,
                    warnings=warnings,
                )

            # Add audio if needed
            output_file = concat_output
            soundtrack_url = render_spec.get("soundtrack_url")
            if soundtrack_url:
                output_file = os.path.join(ffmpeg_dir, "with_audio.mp4")
                if not self._add_audio(concat_output, soundtrack_url, output_file, preserve_source_audio=preserve_audio):
                    return self._failure(
                        "Failed to add/mix audio to video",
                        debug_dir=debug_dir,
                        job_id=job_id,
                        warnings=warnings,
                    )

            # Final output
            master_path = os.path.join(outputs_dir, "master_16x9.mp4")
            shutil.copy(output_file, master_path)

            # Write debug files
            self._write_debug_commands(os.path.join(debug_dir, "ffmpeg_commands.json"))
            self._write_debug_summary(
                os.path.join(debug_dir, "ffmpeg_render_summary.json"),
                {
                    "provider": "ffmpeg",
                    "job_id": job_id,
                    "resolution": resolution,
                    "refit_mode": refit_mode,
                    "output_mode": output_mode,
                    "fps": fps,
                    "clip_count": len(clip_paths),
                    "output": master_path,
                    "warnings": warnings,
                    "success": True,
                },
            )

            return {
                "success": True,
                "url": f"/files/{job_id}/outputs/master_16x9.mp4",
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
                warnings=warnings,
            )

    def _build_video_filters(
        self,
        row: Dict[str, Any],
        width: int,
        height: int,
        fps: int,
        trim_start: float,
        duration: float,
        refit_mode: str,
        include_text: bool = True,
    ) -> tuple[List[str], bool]:
        """Build the video filter chain for a normalized clip."""
        v_filters = [
            f"trim=start={trim_start}:duration={duration},setpts=PTS-STARTPTS,fps={fps}",
        ]

        if refit_mode == "pad":
            scale_filter = (
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black"
            )
        else:
            scale_filter = (
                f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height}"
            )
        v_filters.append(scale_filter)

        had_text_overlay = False
        if include_text:
            had_text_overlay = self._append_drawtext_filter(
                v_filters, row, duration, width, height, refit_mode
            )

        v_filters.append("format=yuv420p")
        return v_filters, had_text_overlay

    def _append_drawtext_filter(
        self,
        v_filters: List[str],
        row: Dict[str, Any],
        duration: float,
        out_width: int = 0,
        out_height: int = 0,
        refit_mode: str = "crop_center",
    ) -> bool:
        """Append a drawtext filter replicating the original text position and style.

        When text_bbox (normalised 4-point coords) is present the text is placed at
        the exact same position it occupied in the source video, mapped through the
        same scale/crop transform applied to the video.  Extracted colour, font size,
        and background are used when available.  Fade-in / fade-out transitions are
        rendered via an alpha expression.
        """
        metadata = row.get("metadata") or {}
        if str(metadata.get("text_action", "")).lower() in {"remove", "skip"}:
            return False

        text_overlay = str(row.get("text", "")).strip() if row.get("text") else None
        if not text_overlay:
            return False

        row_start = float(row.get("start", 0.0))
        text_start = float(row.get("text_start", row_start))
        text_end = float(row.get("text_end", row_start + duration))
        rel_start = max(0.0, text_start - row_start)
        rel_end = min(duration, text_end - row_start)

        escaped_text = _escape_drawtext_text(text_overlay)

        # ── Extracted style (read first so font resolution can use the hint) ──
        ext = row.get("text_extracted_style") or {}
        style = row.get("text_style") or metadata.get("text_style") or DEFAULT_TEXT_STYLE
        if not isinstance(style, dict):
            style = DEFAULT_TEXT_STYLE

        font_color = ext.get("text_color") or "white"
        bg_color = ext.get("bg_color") or "black"
        font_style_hint = str(ext.get("font_style_hint") or "regular").lower()

        font_file = _resolve_font_file(style_hint=font_style_hint)
        if not font_file:
            log.warning("No usable font file found for FFmpeg drawtext; skipping text overlay.")
            return False
        fontfile = _escape_drawtext_path(font_file)

        # ── Position ──────────────────────────────────────────────────────────
        bbox_norm = row.get("text_bbox")
        src_w = int(metadata.get("src_width") or 0)
        src_h = int(metadata.get("src_height") or 0)

        if bbox_norm and len(bbox_norm) >= 4 and out_width > 0 and out_height > 0:
            x_norms = [pt[0] for pt in bbox_norm]
            y_norms = [pt[1] for pt in bbox_norm]
            cx_norm = (min(x_norms) + max(x_norms)) / 2
            cy_norm = (min(y_norms) + max(y_norms)) / 2
            out_cx, out_cy = _map_coord_to_output(
                cx_norm, cy_norm, src_w, src_h, out_width, out_height, refit_mode
            )
            x_expr = f"({out_cx:.1f}-text_w/2)"
            y_expr = f"({out_cy:.1f}-text_h/2)"
        else:
            position = str(row.get("position", "")).strip().lower()
            if "top" in position:
                x_expr = "(w-text_w)/2"
                y_expr = "h/6"
            elif "bottom" in position:
                x_expr = "(w-text_w)/2"
                y_expr = "h*5/6"
            else:
                x_expr = "(w-text_w)/2"
                y_expr = "(h-text_h)/2"

        # ── Font size: map bbox height through the same scale transform ───────
        # This ensures the text occupies the same fraction of the output frame
        # as it did in the source, regardless of resolution change or refit mode.
        if bbox_norm and len(bbox_norm) >= 4 and src_w > 0 and src_h > 0 and out_width > 0 and out_height > 0:
            y_norms = [pt[1] for pt in bbox_norm]
            bbox_height_norm = max(y_norms) - min(y_norms)
            if refit_mode == "pad":
                scale = min(out_width / src_w, out_height / src_h)
            else:  # crop_center
                scale = max(out_width / src_w, out_height / src_h)
            font_size = max(10, int(bbox_height_norm * src_h * scale * 0.85))
        else:
            font_size = int(ext.get("font_size_est") or style.get("font_size", 42) or 42)

        # Merge extracted has_background into style so box is drawn when present
        if ext.get("has_background") and not style.get("box"):
            style = {**style, "box": True}

        style_parts = _drawtext_style_parts(style, box_color=bg_color)
        style_suffix = f":{style_parts}" if style_parts else ""

        # ── Transitions ───────────────────────────────────────────────────────
        transition_in = str(row.get("text_transition_in") or "cut").strip().lower()
        transition_out = str(row.get("text_transition_out") or "cut").strip().lower()
        fade_dur = 0.25  # seconds for each fade ramp

        do_fade_in = transition_in == "fade_in" and (rel_end - rel_start) > fade_dur * 2
        do_fade_out = transition_out == "fade_out" and (rel_end - rel_start) > fade_dur * 2

        if do_fade_in and do_fade_out:
            alpha_expr = (
                f"if(lt(t-{rel_start:.3f},{fade_dur}),"
                f"(t-{rel_start:.3f})/{fade_dur},"
                f"if(gt(t,{rel_end:.3f}-{fade_dur}),"
                f"({rel_end:.3f}-t)/{fade_dur},1))"
            )
        elif do_fade_in:
            alpha_expr = (
                f"if(lt(t-{rel_start:.3f},{fade_dur}),"
                f"(t-{rel_start:.3f})/{fade_dur},1)"
            )
        elif do_fade_out:
            alpha_expr = (
                f"if(gt(t,{rel_end:.3f}-{fade_dur}),"
                f"({rel_end:.3f}-t)/{fade_dur},1)"
            )
        else:
            alpha_expr = None

        enable_expr = f":enable='between(t,{rel_start:.3f},{rel_end:.3f})'"
        alpha_part = f":alpha='{alpha_expr}'" if alpha_expr else ""

        drawtext = (
            f"drawtext=fontfile='{fontfile}':"
            f"text='{escaped_text}':"
            f"fontcolor={font_color}:"
            f"fontsize={font_size}:"
            f"x={x_expr}:"
            f"y={y_expr}"
            f"{style_suffix}"
            f"{alpha_part}"
            f"{enable_expr}"
        )
        v_filters.append(drawtext)
        return True

    def _write_render_filter_plan(self, debug_dir: str, plan: Dict[str, Any]) -> None:
        os.makedirs(debug_dir, exist_ok=True)
        path = os.path.join(debug_dir, "render_filter_plan.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(plan, handle, indent=2, ensure_ascii=False)

    def _run_normalized_clip_ffmpeg(
        self,
        index: int,
        video_src: str,
        output_clip: str,
        trim_start: float,
        duration: float,
        text_overlay: Optional[str],
        v_filters: List[str],
        mute_source_audio: bool,
        retry_without_text: bool = False,
    ) -> bool:
        """Execute FFmpeg to build a normalized clip."""
        video_filter_complex = ",".join(v_filters)
        preserve_audio = not mute_source_audio
        filter_complex = f"[0:v]{video_filter_complex}[out_v]"
        maps = ["-map", "[out_v]"]
        inputs = ["-i", video_src]

        if preserve_audio:
            if self._has_audio(video_src):
                audio_filter = (
                    f"[0:a]atrim=start={trim_start}:duration={duration},"
                    "asetpts=PTS-STARTPTS,"
                    "aformat=sample_fmts=s16:sample_rates=48000:channel_layouts=stereo[out_a]"
                )
                filter_complex += f";{audio_filter}"
                maps.extend(["-map", "[out_a]", "-c:a", "aac"])
            else:
                silent_filter = (
                    f"anullsrc=channel_layout=stereo:sample_rate=48000,"
                    f"atrim=duration={duration},asetpts=PTS-STARTPTS[out_a]"
                )
                filter_complex += f";{silent_filter}"
                maps.extend(["-map", "[out_a]", "-c:a", "aac"])

        cmd = [
            self.ffmpeg,
            *inputs,
            "-filter_complex",
            filter_complex,
            *maps,
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "23",
            "-y",
            output_clip,
        ]

        self._commands.append(
            {
                "index": index,
                "type": "build_clip",
                "input": video_src,
                "output": output_clip,
                "trim_start": trim_start,
                "duration": duration,
                "text_overlay": text_overlay,
                "retry_without_text": retry_without_text,
                "filter_graph": filter_complex,
                "command": " ".join(cmd),
            }
        )

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                log.error(
                    "FFmpeg clip build failed (index %s): input=%s output=%s command=%s "
                    "filter_graph=%s stderr=%s",
                    index,
                    video_src,
                    output_clip,
                    " ".join(cmd),
                    filter_complex,
                    result.stderr,
                )
                return False
            return True
        except Exception as exc:
            log.error(
                "FFmpeg clip build exception (index %s): input=%s output=%s command=%s "
                "filter_graph=%s error=%s",
                index,
                video_src,
                output_clip,
                " ".join(cmd),
                filter_complex,
                exc,
            )
            return False

    def _build_normalized_clip(
        self,
        index: int,
        row: Dict[str, Any],
        output_dir: str,
        width: int,
        height: int,
        fps: int,
        refit_mode: str = "crop_center",
        mute_source_audio: bool = False,
    ) -> Optional[str]:
        """Build a normalized clip from a timeline row."""
        video_src = str(row.get("video_src", "")).strip()
        if not video_src:
            return None

        trim_start = float(row.get("trim", 0.0) or 0.0)
        duration = float(row.get("duration", row.get("length", 0.0)) or 0.0)
        text_overlay = str(row.get("text", "")).strip() if row.get("text") else None

        if duration <= 0:
            return None

        if video_src.startswith(("http://", "https://")):
            local_src = os.path.join(output_dir, f"source_{index}.mp4")
            if not self._download_file(video_src, local_src):
                return None
            video_src = local_src

        output_clip = os.path.join(output_dir, f"clip_{index}.mp4")

        v_filters, had_text_overlay = self._build_video_filters(
            row=row,
            width=width,
            height=height,
            fps=fps,
            trim_start=trim_start,
            duration=duration,
            refit_mode=refit_mode,
            include_text=True,
        )

        if self._run_normalized_clip_ffmpeg(
            index=index,
            video_src=video_src,
            output_clip=output_clip,
            trim_start=trim_start,
            duration=duration,
            text_overlay=text_overlay,
            v_filters=v_filters,
            mute_source_audio=mute_source_audio,
        ):
            return output_clip

        if had_text_overlay:
            log.warning(
                "Retrying clip %s without text overlay after drawtext failure.",
                index,
            )
            v_filters_no_text, _ = self._build_video_filters(
                row=row,
                width=width,
                height=height,
                fps=fps,
                trim_start=trim_start,
                duration=duration,
                refit_mode=refit_mode,
                include_text=False,
            )
            if self._run_normalized_clip_ffmpeg(
                index=index,
                video_src=video_src,
                output_clip=output_clip,
                trim_start=trim_start,
                duration=duration,
                text_overlay=text_overlay,
                v_filters=v_filters_no_text,
                mute_source_audio=mute_source_audio,
                retry_without_text=True,
            ):
                return output_clip

        return None

    def _concat_clips(
        self,
        concat_file: str,
        output_file: str,
        codec_settings: Dict[str, Any],
        clip_paths: Optional[List[str]] = None,
        preserve_audio: bool = False,
    ) -> bool:
        """Concatenate clips using concat demuxer."""
        concat_contents = ""
        if os.path.isfile(concat_file):
            concat_contents = Path(concat_file).read_text(encoding="utf-8")

        cmd = [
            self.ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            concat_file,
            "-c:v",
            codec_settings.get("vcodec", "libx264"),
            "-preset",
            "fast",
            "-crf",
            str(codec_settings.get("crf", 23)),
            "-pix_fmt",
            codec_settings.get("pix_fmt", "yuv420p"),
        ]
        if preserve_audio:
            cmd.extend(["-c:a", "copy"])
        else:
            cmd.extend(["-an"])

        cmd.append(output_file)

        log.info(
            "FFmpeg concat starting: concat_file=%s output=%s clip_paths=%s "
            "concat_contents=%r command=%s",
            concat_file,
            output_file,
            clip_paths or [],
            concat_contents,
            " ".join(cmd),
        )

        self._commands.append(
            {
                "type": "concat",
                "input": concat_file,
                "output": output_file,
                "clip_paths": clip_paths or [],
                "concat_contents": concat_contents,
                "command": " ".join(cmd),
            }
        )

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if result.returncode != 0:
                log.error(
                    "FFmpeg concat failed: concat_file=%s output=%s clip_paths=%s "
                    "concat_contents=%r command=%s stderr=%s",
                    concat_file,
                    output_file,
                    clip_paths or [],
                    concat_contents,
                    " ".join(cmd),
                    result.stderr,
                )
                return False
            return True
        except Exception as exc:
            log.error(
                "FFmpeg concat exception: concat_file=%s output=%s clip_paths=%s "
                "concat_contents=%r command=%s error=%s",
                concat_file,
                output_file,
                clip_paths or [],
                concat_contents,
                " ".join(cmd),
                exc,
            )
            return False

    def _add_audio(self, video_file: str, audio_url: str, output_file: str, preserve_source_audio: bool = False) -> bool:
        """Add/mix audio to video."""
        audio_file = audio_url
        
        # Download if URL
        if audio_url.startswith(("http://", "https://")):
            audio_file = os.path.join(os.path.dirname(output_file), "audio.aac")
            if not self._download_file(audio_url, audio_file):
                return False

        if preserve_source_audio:
            # Mix source audio and soundtrack using amix
            filter_complex = "[0:a][1:a]amix=inputs=2:duration=first,aformat=sample_fmts=s16:sample_rates=48000:channel_layouts=stereo[a]"
            cmd = [
                self.ffmpeg,
                "-i", video_file,
                "-i", audio_file,
                "-filter_complex", filter_complex,
                "-map", "0:v",
                "-map", "[a]",
                "-c:v", "copy",
                "-c:a", "aac",
                "-shortest",
                "-y",
                output_file,
            ]
        else:
            # Map soundtrack as the only audio
            filter_complex = "[1:a]aformat=sample_fmts=s16:sample_rates=48000:channel_layouts=stereo[a]"
            cmd = [
                self.ffmpeg,
                "-i", video_file,
                "-i", audio_file,
                "-filter_complex", filter_complex,
                "-map", "0:v",
                "-map", "[a]",
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
        """Write FFmpeg concat demuxer file with absolute clip paths."""
        concat_file = Path(concat_path)
        concat_file.parent.mkdir(parents=True, exist_ok=True)
        with concat_file.open("w", encoding="utf-8") as handle:
            for clip_path in clip_paths:
                handle.write(f"file '{_concat_demuxer_path(Path(clip_path))}'\n")

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
        return (1080, 1920)

    def _has_audio(self, path: str) -> bool:
        """Check if video path has an audio stream using ffprobe."""
        cmd = [
            self.ffprobe,
            "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=codec_type",
            "-of", "csv=p=0",
            path
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return "audio" in result.stdout.lower()
        except Exception:
            return False

    def _failure(
        self,
        error_msg: str,
        debug_dir: str,
        job_id: str,
        exception: Optional[Exception] = None,
        warnings: Optional[List[str]] = None,
        stderr: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Write failure debug files and return error result."""
        os.makedirs(debug_dir, exist_ok=True)
        
        error_detail = {
            "provider": "ffmpeg",
            "job_id": job_id,
            "stage": "ffmpeg_render",
            "error": error_msg,
            "exception": repr(exception) if exception else None,
            "warnings": warnings or [],
            "stderr_snippet": stderr[-500:] if stderr else None,
            "timestamp": self._iso_now(),
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
