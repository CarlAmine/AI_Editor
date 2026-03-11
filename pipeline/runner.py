import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests

from ai_editor.analyzer import analyze_video_content_with_results
from ai_editor.downloader import (
    VideoClapError,
    VideoDownloadError,
    _is_youtube_url,
    clip_video,
    download_and_clip,
    download_video,
    download_video_section,
    extract_audio,
    extract_audio_segment,
)
from ai_editor.editor import create_and_render_video

from .artifacts import ArtifactRegistry
from .plans import (
    build_audio_plan,
    build_overlay_plan,
    build_postprocess_plan,
    build_render_spec,
    build_timeline_plan,
    write_plan,
)
from .state import (
    JobState,
    StageName,
    StageStatus,
    add_error,
    add_warning,
    load_state,
    new_state,
    save_state,
    update_stage,
)
from .storage import DriveStorageAdapter, UrlStorageAdapter


def _job_dirs(job_id: str) -> Dict[str, str]:
    root = os.path.join("tmp", "jobs", job_id)
    return {
        "job": root,
        "plans": os.path.join(root, "plans"),
        "media": os.path.join(root, "media"),
        "outputs": os.path.join(root, "outputs"),
        "logs": os.path.join(root, "logs"),
        "debug": os.path.join(root, "debug"),
    }


def _ensure_layout(d: Dict[str, str]) -> None:
    for p in d.values():
        os.makedirs(p, exist_ok=True)


def _infer_intent_mode(prompt: str, requirements: Dict[str, Any]) -> str:
    explicit = str(requirements.get("intent_mode", "")).lower().strip()
    if explicit in {"video", "shorts"}:
        return explicit
    t = (prompt or "").lower()
    return "shorts" if any(k in t for k in ["youtube short", "youtube shorts", "shorts", "short "]) else "video"


def _is_http_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return value.strip().lower().startswith(("http://", "https://"))


def _default_drive_folder() -> Optional[str]:
    return (
        os.getenv("DRIVE_UPLOAD_FOLDER_ID")
        or os.getenv("DRIVE_DEFAULT_FOLDER_ID")
        or os.getenv("VIDEO_FOLDER")
    )


def _upload_assets_for_shotstack(job_id: str, local_paths: List[str]) -> List[Dict[str, Any]]:
    if not local_paths:
        return []
    adapter = DriveStorageAdapter()
    folder_id = _default_drive_folder()
    results = []
    for path in local_paths:
        normalized = os.path.normpath(path)
        if not os.path.exists(normalized):
            raise RuntimeError(f"Aligned clip missing: {normalized}")
        attempts = 3
        last_exc: Optional[Exception] = None
        current_folder = folder_id
        asset = None
        for attempt in range(attempts):
            try:
                asset = adapter.upload(normalized, current_folder)
                break
            except Exception as exc:
                last_exc = exc
                msg = str(exc)
                if (
                    current_folder
                    and ("insufficientParentPermissions" in msg or "Insufficient permissions" in msg)
                ):
                    current_folder = None
                    print("Warning: uploading to root because default folder access is blocked.")
                    continue
                if attempt == attempts - 1:
                    raise
                time.sleep(2 ** attempt)
        if asset is None:
            raise RuntimeError(f"Failed to upload {normalized}") from last_exc
        try:
            adapter.drive.permissions().create(
                fileId=asset.id,
                body={"type": "anyone", "role": "reader"},
                fields="id",
            ).execute()
        except Exception as exc:
            raise RuntimeError("DRIVE_PERMISSION_FAILED") from exc
        public_url = adapter.get_fetchable_url(asset)
        try:
            resp = requests.head(public_url, timeout=10)
            if resp.status_code >= 400:
                print(f"Warning: HEAD {public_url} returned {resp.status_code}")
        except requests.RequestException as exc:
            print(f"Warning: could not verify {public_url}: {exc}")
        print(f"Uploaded {normalized} -> {public_url} ({asset.id})")
        results.append(
            {
                "local_path": normalized,
                "file_id": asset.id,
                "name": asset.name,
                "public_url": public_url,
            }
        )
    return results


def _probe_duration(path: str) -> float:
    try:
        import cv2

        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            return 0.0
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        frames = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
        cap.release()
        return (frames / fps) if fps > 0 else 0.0
    except Exception:
        return 0.0


def _probe_duration_any(path_or_url: str) -> float:
    if not path_or_url:
        return 0.0
    d = _probe_duration(path_or_url)
    if d > 0:
        return d
    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path_or_url),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            return float((proc.stdout or "0").strip() or 0.0)
    except Exception:
        pass
    return 0.0


def _is_direct_shotstack_source_url(url: str) -> bool:
    if not _is_http_url(url):
        return False
    u = str(url).lower().strip()
    if "drive.google.com/uc?" in u:
        return True
    if any(u.endswith(ext) for ext in [".mp4", ".mov", ".m4v", ".webm", ".mkv"]):
        return True
    return False


def _extract_start_override(source: Dict[str, Any]) -> float:
    try:
        if source.get("start") is not None:
            return max(0.0, float(source.get("start")))
    except (TypeError, ValueError):
        pass
    segments = source.get("segments") or []
    if isinstance(segments, list) and segments:
        first = segments[0] or {}
        try:
            if first.get("start") is not None:
                return max(0.0, float(first.get("start")))
        except (TypeError, ValueError):
            pass
    return 0.0


def _extract_bounded_segment(source: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    segments = source.get("segments") or []
    if not isinstance(segments, list) or not segments:
        return None
    first = segments[0] or {}
    try:
        start = float(first.get("start"))
        end = float(first.get("end"))
    except (TypeError, ValueError):
        return None
    if end <= start:
        return None
    return max(0.0, start), max(0.0, end)


def _parse_timestamp_seconds(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    # Plain numeric string.
    try:
        return float(raw)
    except ValueError:
        pass
    if ":" not in raw:
        return None
    parts = raw.split(":")
    if len(parts) > 3 or len(parts) < 2:
        return None
    try:
        if len(parts) == 3:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2])
        else:
            hours = 0
            minutes = int(parts[0])
            seconds = float(parts[1])
    except ValueError:
        return None
    total = hours * 3600 + minutes * 60 + seconds
    return float(total)


def _extract_music_segment(requirements: Dict[str, Any]) -> Optional[Tuple[float, Optional[float]]]:
    seg = requirements.get("custom_music_segment") or requirements.get("custom_music_segments")
    if isinstance(seg, list) and seg:
        seg = seg[0]
    if isinstance(seg, str):
        cleaned = seg.strip()
        if "-" in cleaned and "http" not in cleaned.lower():
            parts = [p.strip() for p in cleaned.split("-", 1)]
            if len(parts) == 2:
                start = _parse_timestamp_seconds(parts[0])
                end = _parse_timestamp_seconds(parts[1])
                if start is not None and (end is None or end > start):
                    return max(0.0, start), end
    if isinstance(seg, dict):
        start = _parse_timestamp_seconds(seg.get("start"))
        end = _parse_timestamp_seconds(seg.get("end")) if seg.get("end") is not None else None
        if start is not None:
            if end is not None and end <= start:
                return None
            return max(0.0, start), end

    start = requirements.get("custom_music_start")
    end = requirements.get("custom_music_end")
    start_val = _parse_timestamp_seconds(start)
    end_val = _parse_timestamp_seconds(end) if end is not None else None
    if start_val is not None:
        if end_val is not None and end_val <= start_val:
            return None
        return max(0.0, start_val), end_val
    return None


def _download_file(url: str, out_path: str) -> None:
    with requests.get(url, stream=True, timeout=180) as r:
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        raise RuntimeError(f"Downloaded file is empty: {out_path}")


def _run_shorts_refit(master_path: str, short_path: str, refit_mode: str) -> None:
    if refit_mode == "crop":
        refit_mode = "crop_center"
    if refit_mode not in {"crop_center", "pad"}:
        refit_mode = "crop_center"
    if refit_mode == "pad":
        vf = "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2"
    else:
        vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
    cmd = [
        "ffmpeg",
        "-i",
        master_path,
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        "-y",
        short_path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "").strip())


def _align_sources(raw_paths: List[str], scene_durations: List[float], out_dir: str) -> Tuple[List[str], Optional[str]]:
    src = []
    for p in raw_paths:
        d = _probe_duration(p)
        if d > 0:
            src.append({"path": p, "dur": d})
    if not src or not scene_durations:
        return [], None
    total_src = sum(s["dur"] for s in src)
    total_tgt = sum(scene_durations)
    if total_src + 0.05 < total_tgt:
        return [], (
            f"Uploaded source duration ({total_src:.1f}s) is shorter than analyzed timeline ({total_tgt:.1f}s). "
            "Proceeding with sources as-is. Re-upload if this is not your intent."
        )
    os.makedirs(out_dir, exist_ok=True)
    aligned = []
    for i, td in enumerate(scene_durations, start=1):
        source_idx = i - 1
        if source_idx >= len(src):
            return [], (
                f"Not enough source clips for strict index alignment: need source {i} for scene {i}."
            )
        cur = src[source_idx]
        if cur["dur"] <= 0.05:
            return [], f"Source {i} has invalid duration ({cur['dur']:.2f}s)."
        dst = os.path.join(out_dir, f"aligned_{i:03d}.mp4")
        # Keep aligned clip duration identical to raw source duration for index i.
        shutil.copy2(cur["path"], dst)
        aligned.append(dst)
    return aligned, None


def _sorted_indexed_artifact_keys(items: Dict[str, Any], prefix: str) -> List[str]:
    keys = []
    for key in items:
        if not key.startswith(prefix):
            continue
        suffix = key[len(prefix):]
        if suffix.isdigit():
            keys.append(key)
    return sorted(keys, key=lambda k: int(k[len(prefix):]))


def _collect_edit_request_lines(requirements: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    for key in ("edit_requests", "user_requests"):
        vals = requirements.get(key) or []
        if isinstance(vals, list):
            lines.extend([str(v) for v in vals if str(v).strip()])
    return lines


def _sanitize_overlay_text(text: str) -> str:
    txt = str(text or "")
    txt = re.sub(r"\((?:top|bottom|middle|center)\)", "", txt, flags=re.IGNORECASE)
    txt = txt.replace("|", " ")
    txt = txt.replace("'", "")
    txt = " ".join(txt.split())
    return txt.strip()


def _parse_edit_ops(requirements: Dict[str, Any]) -> List[Dict[str, Any]]:
    ops: List[Dict[str, Any]] = []
    lines = _collect_edit_request_lines(requirements)
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        prefix = line.split(":", 1)[0].strip().lower()
        if prefix in {"remove", "cut", "delete", "trim", "add", "replace", "swap", "edit"} and ":" in line:
            line = line.split(":", 1)[1].strip()
        low = line.lower()

        m = re.search(r"(?:trim|remove|cut)\s+(?:the\s+)?(?:end|last)\s+(\d+(?:\.\d+)?)", low)
        if not m:
            m = re.search(r"last\s+(\d+(?:\.\d+)?)\s*(?:s|sec|secs|seconds)", low)
        if m:
            ops.append({"op": "trim_end", "seconds": float(m.group(1)), "raw": raw})
            continue

        m = re.search(r"(?:remove|delete|cut)\s+(?:clip|scene)\s*(\d+)", low)
        if m:
            ops.append({"op": "remove_clip", "index": int(m.group(1)), "raw": raw})
            continue

        m = re.search(r"swap\s+(?:clip|scene)?\s*(\d+)\s*(?:and|with)\s*(\d+)", low)
        if not m:
            m = re.search(r"swap\s+(\d+)\s+(\d+)", low)
        if m:
            ops.append({"op": "swap", "a": int(m.group(1)), "b": int(m.group(2)), "raw": raw})
            continue

        m = re.search(
            r"replace\s+(?:clip|scene)?\s*(\d+)\s+(?:with|from)\s*(?:clip|scene)?\s*(\d+)",
            low,
        )
        if m:
            ops.append({"op": "replace_clip", "index": int(m.group(1)), "source": int(m.group(2)), "raw": raw})
            continue

        m = re.search(
            r"(?:add\s+)?overlay\s+text(?:\s+for)?\s*(?:clip|scene)?\s*(\d+)?\s*(?:is|=|:)?\s*(.+)$",
            line,
            flags=re.IGNORECASE,
        )
        if m:
            idx = int(m.group(1)) if m.group(1) else None
            text = _sanitize_overlay_text(m.group(2))
            if text:
                ops.append({"op": "set_overlay_text", "index": idx, "text": text, "raw": raw})

    return ops


def _reflow_timeline(timeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    cursor = 0.0
    for idx, row in enumerate(timeline, start=1):
        duration = float(row.get("duration", row.get("length", 0.0)) or 0.0)
        if duration <= 0:
            continue
        label = str(row.get("label", "")).strip()
        if label.startswith("scene_"):
            prefix = "scene"
        elif label.startswith("ocr_"):
            prefix = "ocr"
        else:
            prefix = "clip"
        row["index"] = idx
        row["scene_id"] = int(row.get("scene_id", idx))
        row["label"] = f"{prefix}_{idx:03d}"
        row["start"] = cursor
        row["end"] = cursor + duration
        row["duration"] = duration
        row["length"] = duration
        row["text_start"] = row.get("text_start", row["start"])
        row["text_end"] = row.get("text_end", row["end"])
        cursor = row["end"]
        out.append(row)
    return out


def _apply_edit_ops_to_timeline(
    timeline: List[Dict[str, Any]],
    ops: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if not timeline or not ops:
        return timeline, {"applied": [], "timing_changed": False, "count_changed": False}

    rows = [dict(r) for r in timeline]
    applied: List[Dict[str, Any]] = []
    timing_changed = False
    count_changed = False
    overlay_queue: List[str] = []

    def _valid_index(i: int) -> bool:
        return 1 <= i <= len(rows)

    for op in ops:
        if op["op"] == "trim_end":
            secs = max(0.0, float(op.get("seconds", 0.0)))
            if secs <= 0 or not rows:
                continue
            last = rows[-1]
            dur = float(last.get("duration", last.get("length", 0.0)) or 0.0)
            new_dur = max(0.0, dur - secs)
            last["duration"] = new_dur
            last["length"] = new_dur
            timing_changed = True
            if new_dur <= 0:
                rows.pop()
                count_changed = True
            applied.append(op)
            continue

        if op["op"] == "remove_clip":
            idx = int(op.get("index", 0) or 0)
            if _valid_index(idx):
                rows.pop(idx - 1)
                count_changed = True
                applied.append(op)
            continue

        if op["op"] == "swap":
            a = int(op.get("a", 0) or 0)
            b = int(op.get("b", 0) or 0)
            if _valid_index(a) and _valid_index(b) and a != b:
                rows[a - 1], rows[b - 1] = rows[b - 1], rows[a - 1]
                applied.append(op)
            continue

        if op["op"] == "replace_clip":
            idx = int(op.get("index", 0) or 0)
            src_idx = int(op.get("source", 0) or 0)
            if _valid_index(idx) and _valid_index(src_idx) and idx != src_idx:
                src = rows[src_idx - 1]
                dst = rows[idx - 1]
                for key in ("video_src", "videoSrc", "trim", "source_duration", "source_index"):
                    if key in src:
                        dst[key] = src.get(key)
                applied.append(op)
            continue

        if op["op"] == "set_overlay_text":
            idx = op.get("index")
            text = _sanitize_overlay_text(op.get("text", ""))
            if not text:
                continue
            if idx and _valid_index(int(idx)):
                row = rows[int(idx) - 1]
                row["text"] = text
                row["text_start"] = row.get("start", 0.0)
                row["text_end"] = row.get("end", row.get("start", 0.0))
                applied.append(op)
            else:
                overlay_queue.append(text)
                applied.append(op)
            continue

    if overlay_queue:
        for row in rows:
            if not overlay_queue:
                break
            if not str(row.get("text", "")).strip():
                row["text"] = overlay_queue.pop(0)

    rows = _reflow_timeline(rows)
    return rows, {"applied": applied, "timing_changed": timing_changed, "count_changed": count_changed}


def _build_reference_timeline(
    analysis: Dict[str, Any],
    sources: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    scenes = analysis.get("scenes") or []
    if not scenes:
        raise RuntimeError("Reference mimic mode requires analyzed scenes.")
    durations = [float(s.get("duration", 0.0)) for s in scenes]
    if any(d <= 0 for d in durations):
        raise RuntimeError("Reference mimic mode requires positive analyzed scene durations.")
    if not sources:
        raise RuntimeError("No valid source clips available for reference mimic mode.")

    if len(sources) < len(scenes):
        raise RuntimeError(
            f"Reference mimic requires at least {len(scenes)} sources; received {len(sources)}."
        )

    timeline = []
    for idx, scene in enumerate(scenes, start=1):
        target_duration = float(scene.get("duration", 0.0))
        src = sources[idx - 1]
        video_src = str(src.get("video_src", "")).strip()
        probe_src = str(src.get("probe_src", "")).strip() or video_src
        trim_start = max(0.0, float(src.get("trim", 0.0)))
        source_duration = -1.0
        if probe_src and not _is_http_url(probe_src):
            source_duration = _probe_duration_any(probe_src)
            if source_duration <= 0.0:
                raise RuntimeError(
                    f"Reference mimic source {idx} duration could not be determined: {probe_src}"
                )
            if source_duration + 0.02 < trim_start + target_duration:
                raise RuntimeError(
                    f"Reference mimic assignment failed for scene {idx}: source too short "
                    f"(source={source_duration:.2f}s, trim={trim_start:.2f}s, required={target_duration:.2f}s)."
                )
        start = float(scene.get("start_time", sum(durations[: idx - 1])))
        end = float(scene.get("end_time", start + target_duration))
        timeline.append(
            {
                "index": idx,
                "scene_id": int(scene.get("scene_id", idx)),
                "label": f"scene_{idx:03d}",
                "start": start,
                "end": end,
                "length": target_duration,
                "duration": target_duration,
                "videoSrc": video_src,
                "video_src": video_src,
                "trim": trim_start,
                "transitionIn": None,
                "transitionOut": None,
                "text": "",
                "text_start": start,
                "text_end": end,
                "source_duration": source_duration,
            }
        )
    return timeline


def _validate_reference_timeline(
    analysis: Dict[str, Any],
    timeline: List[Dict[str, Any]],
    overlay_timing: List[Dict[str, Any]],
    use_reference_audio: bool,
    reference_audio_duration: Optional[float],
) -> List[str]:
    errors: List[str] = []
    scenes = analysis.get("scenes") or []
    tol = 0.05
    if len(timeline) != len(scenes):
        errors.append(f"scene_count mismatch: generated={len(timeline)} analyzed={len(scenes)}")
    analyzed_durations = [float(s.get("duration", 0.0)) for s in scenes]
    generated_durations = [float(t.get("duration", 0.0)) for t in timeline]
    for i, (gd, ad) in enumerate(zip(generated_durations, analyzed_durations), start=1):
        if abs(gd - ad) > tol:
            errors.append(f"scene_duration mismatch at {i}: generated={gd:.3f}, analyzed={ad:.3f}")
    analyzed_total = sum(analyzed_durations)
    generated_total = sum(generated_durations)
    if abs(generated_total - analyzed_total) > tol:
        errors.append(f"total_duration mismatch: generated={generated_total:.3f}, analyzed={analyzed_total:.3f}")
    if len(overlay_timing) != len(timeline):
        errors.append(f"overlay_count mismatch: overlays={len(overlay_timing)} scenes={len(timeline)}")
    for i, (row, scene_row) in enumerate(zip(overlay_timing, timeline), start=1):
        st = float(row.get("start", 0.0))
        en = float(row.get("end", 0.0))
        scene_start = float(scene_row.get("start", 0.0))
        scene_end = float(scene_row.get("end", scene_start + float(scene_row.get("duration", 0.0))))
        if abs(st - scene_start) > tol:
            errors.append(
                f"overlay_start mismatch at {i}: overlay={st:.3f}, scene={scene_start:.3f}"
            )
        if abs((en - st) - (scene_end - scene_start)) > tol:
            errors.append(
                f"overlay_length mismatch at {i}: overlay={(en-st):.3f}, scene={(scene_end-scene_start):.3f}"
            )
    last_end = -1.0
    for row in sorted(overlay_timing, key=lambda x: float(x.get("start", 0.0))):
        st = float(row.get("start", 0.0))
        en = float(row.get("end", 0.0))
        if en < st:
            errors.append(f"overlay timing invalid: start={st:.3f}, end={en:.3f}")
        if st < last_end - 1e-3:
            errors.append(f"overlay overlap detected: start={st:.3f}, prev_end={last_end:.3f}")
        last_end = max(last_end, en)
    if timeline:
        final_scene_end = float(timeline[-1].get("end", 0.0))
        if abs(final_scene_end - generated_total) > tol:
            errors.append(
                f"final_scene_end mismatch: final_end={final_scene_end:.3f}, total={generated_total:.3f}"
            )
    # Reference audio bed is allowed to span independently; do not hard-fail on probe mismatch.
    return errors


def _build_overlay_timing_from_timeline(
    timeline: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    overlays: List[Dict[str, Any]] = []
    for i, row in enumerate(timeline, start=1):
        start = float(row.get("text_start", row.get("start", 0.0)))
        end = float(row.get("text_end", row.get("end", start)))
        if end <= start:
            continue
        overlays.append(
            {
                "index": i,
                "text": str(row.get("text", "")).strip(),
                "start": start,
                "end": end,
                "length": end - start,
            }
        )
    return overlays


def _build_ocr_timeline(
    text_segments: List[Dict[str, Any]],
    sources: List[Dict[str, Any]],
    strict_index_alignment: bool = False,
) -> List[Dict[str, Any]]:
    if not text_segments:
        raise RuntimeError(
            "OCR mode selected but no OCR text segments were produced from analysis keyframes."
        )
    if not sources:
        raise RuntimeError("OCR mode requires at least one source clip URL/path.")

    ordered_segments = sorted(
        text_segments,
        key=lambda s: float(s.get("start", 0.0)),
    )
    if strict_index_alignment and len(sources) < len(ordered_segments):
        raise RuntimeError(
            f"OCR mode in reference mimic requires at least {len(ordered_segments)} sources; "
            f"received {len(sources)}."
        )
    timeline: List[Dict[str, Any]] = []
    source_duration_cache: Dict[str, float] = {}
    for idx, seg in enumerate(ordered_segments, start=1):
        start = float(seg.get("start", 0.0))
        end = float(seg.get("end", start))
        duration = end - start
        if duration <= 0.0:
            continue

        if strict_index_alignment:
            source = sources[idx - 1]
        else:
            source = sources[min(idx - 1, len(sources) - 1)]
        video_src = str(source.get("video_src", "")).strip()
        probe_src = str(source.get("probe_src", "")).strip() or video_src
        trim_start = max(0.0, float(source.get("trim", 0.0) or 0.0))
        if not video_src:
            raise RuntimeError(f"OCR timeline source {idx} has no usable URL/path.")

        cache_key = probe_src or video_src
        if cache_key not in source_duration_cache:
            if cache_key and _is_http_url(cache_key):
                source_duration_cache[cache_key] = -1.0
            else:
                source_duration_cache[cache_key] = _probe_duration_any(cache_key)
        source_duration = float(source_duration_cache.get(cache_key, 0.0))
        if source_duration <= 0.0:
            # Remote URLs (notably Google Drive) often fail local cv2/ffprobe probing due redirects/auth/timeouts.
            # In that case, keep canonical OCR timing and defer media fetchability/duration enforcement to renderer.
            source_duration = -1.0
        elif source_duration + 0.02 < trim_start + duration:
            raise RuntimeError(
                f"OCR timeline assignment failed for segment {idx}: source too short "
                f"(source={source_duration:.2f}s, trim={trim_start:.2f}s, required={duration:.2f}s)."
            )

        text = str(seg.get("text", "")).strip()
        timeline.append(
            {
                "index": idx,
                "scene_id": idx,
                "label": f"ocr_{idx:03d}",
                "start": start,
                "end": end,
                "length": duration,
                "duration": duration,
                "videoSrc": video_src,
                "video_src": video_src,
                "trim": trim_start,
                "transitionIn": None,
                "transitionOut": None,
                "text": text,
                "text_start": start,
                "text_end": end,
                "source_duration": source_duration,
                "source_index": int(source.get("index", 0) or 0),
            }
        )
    if not timeline:
        raise RuntimeError("OCR mode produced no usable timeline segments.")
    return timeline


def _validate_ocr_timeline(
    text_segments: List[Dict[str, Any]],
    timeline: List[Dict[str, Any]],
    overlay_timing: List[Dict[str, Any]],
) -> List[str]:
    errors: List[str] = []
    tol = 0.05
    ordered_segments = sorted(text_segments, key=lambda s: float(s.get("start", 0.0)))
    if len(timeline) != len(ordered_segments):
        errors.append(
            f"ocr_segment_count mismatch: timeline={len(timeline)} ocr_segments={len(ordered_segments)}"
        )
    if len(overlay_timing) != len(timeline):
        errors.append(f"overlay_count mismatch: overlays={len(overlay_timing)} timeline={len(timeline)}")

    for i, (row, seg) in enumerate(zip(timeline, ordered_segments), start=1):
        rs = float(row.get("start", 0.0))
        re = float(row.get("end", rs))
        rd = float(row.get("duration", re - rs))
        ss = float(seg.get("start", 0.0))
        se = float(seg.get("end", ss))
        sd = se - ss
        if abs(rs - ss) > tol:
            errors.append(f"timeline_start mismatch at {i}: timeline={rs:.3f}, ocr={ss:.3f}")
        if abs(re - se) > tol:
            errors.append(f"timeline_end mismatch at {i}: timeline={re:.3f}, ocr={se:.3f}")
        if abs(rd - sd) > tol:
            errors.append(f"timeline_duration mismatch at {i}: timeline={rd:.3f}, ocr={sd:.3f}")

    for i, (overlay, row) in enumerate(zip(overlay_timing, timeline), start=1):
        os_ = float(overlay.get("start", 0.0))
        oe = float(overlay.get("end", os_))
        rs = float(row.get("start", 0.0))
        re = float(row.get("end", rs))
        if abs(os_ - rs) > tol:
            errors.append(f"overlay_start mismatch at {i}: overlay={os_:.3f}, video={rs:.3f}")
        if abs((oe - os_) - (re - rs)) > tol:
            errors.append(
                f"overlay_length mismatch at {i}: overlay={(oe-os_):.3f}, video={(re-rs):.3f}"
            )

    if timeline:
        total_timeline = sum(float(row.get("duration", 0.0)) for row in timeline)
        total_ocr = sum(
            max(0.0, float(seg.get("end", 0.0)) - float(seg.get("start", 0.0)))
            for seg in ordered_segments
        )
        if abs(total_timeline - total_ocr) > tol:
            errors.append(f"total_duration mismatch: timeline={total_timeline:.3f}, ocr={total_ocr:.3f}")
        timeline_end = max(float(row.get("end", 0.0)) for row in timeline)
        overlay_end = max((float(r.get("end", 0.0)) for r in overlay_timing), default=0.0)
        if abs(overlay_end - timeline_end) > tol:
            errors.append(f"final_end mismatch: overlay_end={overlay_end:.3f}, timeline_end={timeline_end:.3f}")

    return errors


def _artifact_path_exists(registry: ArtifactRegistry, key: str) -> bool:
    art = registry.get(key)
    return bool(art and art.type == "file" and os.path.exists(art.path_or_url))


@dataclass
class Ctx:
    job_id: str
    request_payload: Dict[str, Any]
    dirs: Dict[str, str]
    state: JobState
    artifacts: ArtifactRegistry
    runtime: Dict[str, Any]


def _save(ctx: Ctx) -> None:
    save_state(ctx.dirs["job"], ctx.state)
    ctx.artifacts.save(ctx.dirs["job"])


def _run_stage(ctx: Ctx, stage: StageName, fn, done_check=None) -> None:
    if done_check and done_check():
        update_stage(ctx.state, stage, StageStatus.SKIPPED, {"reused": True})
        _save(ctx)
        return
    update_stage(ctx.state, stage, StageStatus.RUNNING)
    _save(ctx)
    try:
        fn()
        update_stage(ctx.state, stage, StageStatus.SUCCEEDED)
        _save(ctx)
    except Exception as e:
        add_error(ctx.state, stage, "STAGE_FAILED", str(e), {"exception": repr(e)})
        update_stage(ctx.state, stage, StageStatus.FAILED, {"exception": repr(e)})
        _save(ctx)
        ctx.runtime["failed"] = True
        ctx.runtime["failed_stage"] = stage.value
        ctx.runtime["failed_message"] = str(e)


def _build_failure_response(ctx: Ctx) -> Dict[str, Any]:
    warnings = ctx.state.warnings
    user_notice = next((w["message"] for w in warnings if w.get("code") == "SOURCE_DURATION_SHORT"), None)
    ffmpeg_error = next((w.get("detail") for w in warnings if w.get("code") == "FFMPEG_POSTPROCESS_FAILED"), None)
    last = ctx.state.errors[-1] if ctx.state.errors else {
        "message": ctx.runtime.get("failed_message", "Pipeline failed."),
        "stage": ctx.runtime.get("failed_stage", "UNKNOWN"),
        "code": "PIPELINE_FAILED",
    }
    shot = ctx.artifacts.get("render.shotstack_url")
    return {
        "success": False,
        "error": last.get("message", "Pipeline failed."),
        "render_id": (shot.meta or {}).get("render_id") if shot else None,
        "status": "failed",
        "project_id": ctx.job_id,
        "warnings": warnings,
        "errors": ctx.state.errors,
        "user_notice": user_notice,
        "ffmpeg_error": ffmpeg_error,
    }


def run_job(job_id: str, request_payload: Dict[str, Any]) -> Dict[str, Any]:
    dirs = _job_dirs(job_id)
    _ensure_layout(dirs)

    req_state = request_payload.get("requirements_state") or {}
    requirements = dict(req_state)
    requirements["prompt"] = request_payload.get("prompt", "")
    requirements["music_mode"] = request_payload.get("music_mode", "original")
    requirements["custom_music_url"] = request_payload.get("custom_music_url")
    requirements["custom_music_start"] = request_payload.get("custom_music_start")
    requirements["custom_music_end"] = request_payload.get("custom_music_end")
    requirements["custom_music_segment"] = request_payload.get("custom_music_segment")
    requirements["custom_music_segments"] = request_payload.get("custom_music_segments")
    requirements["generation_mode"] = str(requirements.get("generation_mode", "free_generation_mode")).lower()
    if requirements["generation_mode"] not in {"free_generation_mode", "reference_mimic_mode"}:
        requirements["generation_mode"] = "free_generation_mode"
    requirements["edit_mode"] = str(requirements.get("edit_mode", "scene")).lower().strip()
    if requirements["edit_mode"] not in {"scene", "ocr"}:
        requirements["edit_mode"] = "scene"
    requirements["intent_mode"] = _infer_intent_mode(requirements.get("prompt", ""), requirements)
    requirements["output_mode"] = str(requirements.get("output_mode", "")).lower().strip()
    if requirements["output_mode"] not in {"native_9x16", "crop_to_9x16", ""}:
        requirements["output_mode"] = ""
    requirements["refit_mode"] = str(requirements.get("refit_mode", os.getenv("REFIT_MODE", "crop_center"))).lower()
    if requirements["refit_mode"] == "crop":
        requirements["refit_mode"] = "crop_center"
    if requirements["refit_mode"] not in {"crop_center", "pad", "native_9x16"}:
        requirements["refit_mode"] = "crop_center"
    if not requirements["output_mode"]:
        requirements["output_mode"] = "native_9x16" if requirements["refit_mode"] == "native_9x16" else "crop_to_9x16"

    state = load_state(dirs["job"]) or new_state(
        job_id=job_id,
        input_summary={
            "primary_url": request_payload.get("primary_url"),
            "has_drive_folder": bool(request_payload.get("gdrive_folder_id")),
            "sources_count": len(request_payload.get("sources") or []),
        },
        requirements=requirements,
    )
    artifacts = ArtifactRegistry.load(dirs["job"])
    ctx = Ctx(job_id=job_id, request_payload=request_payload, dirs=dirs, state=state, artifacts=artifacts, runtime={})

    # INGEST
    def stage_ingest():
        with open(os.path.join(dirs["debug"], "request_payload.json"), "w", encoding="utf-8") as f:
            json.dump(request_payload, f, ensure_ascii=False, indent=2)

    _run_stage(ctx, StageName.INGEST, stage_ingest)
    if ctx.runtime.get("failed"):
        return _build_failure_response(ctx)

    # FETCH_PRIMARY
    def stage_fetch_primary():
        primary_dst = os.path.join(dirs["media"], "primary.mp4")
        p = download_video(request_payload["primary_url"], dirs["media"], "primary.mp4")
        ctx.artifacts.register_file("primary.video", p, {"source": request_payload["primary_url"]}, "video/mp4")

    _run_stage(
        ctx,
        StageName.FETCH_PRIMARY,
        stage_fetch_primary,
        done_check=lambda: _artifact_path_exists(ctx.artifacts, "primary.video"),
    )
    if ctx.runtime.get("failed"):
        return _build_failure_response(ctx)

    # ANALYZE_PRIMARY
    def stage_analyze_primary():
        primary = ctx.artifacts.get("primary.video").path_or_url
        summary, analysis = analyze_video_content_with_results(primary)
        analysis_json = os.path.join(dirs["debug"], "analysis.json")
        summary_txt = os.path.join(dirs["debug"], "analysis_summary.txt")
        with open(analysis_json, "w", encoding="utf-8") as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)
        with open(summary_txt, "w", encoding="utf-8") as f:
            f.write(summary)
        ctx.artifacts.register_file("analysis.json", analysis_json, {}, "application/json")
        ctx.artifacts.register_file("analysis.summary", summary_txt, {}, "text/plain")

    _run_stage(
        ctx,
        StageName.ANALYZE_PRIMARY,
        stage_analyze_primary,
        done_check=lambda: _artifact_path_exists(ctx.artifacts, "analysis.json"),
    )
    if ctx.runtime.get("failed"):
        return _build_failure_response(ctx)

    # FETCH_SOURCES
    def stage_fetch_sources():
        folder_id = request_payload.get("gdrive_folder_id")
        sources = request_payload.get("sources") or []
        generation_mode = requirements.get("generation_mode", "free_generation_mode")
        if folder_id:
            adapter = DriveStorageAdapter()
            assets = adapter.list_videos(folder_id)
            if not assets:
                raise RuntimeError("No video files found in provided Google Drive folder.")
            if generation_mode == "reference_mimic_mode":
                # Mimic mode: use original Drive URLs directly (no pre-trim/re-upload).
                for i, asset in enumerate(assets, start=1):
                    fetch_url = adapter.get_fetchable_url(asset)
                    ctx.artifacts.register_url(
                        f"sources.fetch.{i}",
                        fetch_url,
                        {"backend": "drive", "asset_id": asset.id, "trim_start": 0.0},
                        "video/mp4",
                    )
            else:
                for i, asset in enumerate(assets, start=1):
                    dst = os.path.join(dirs["media"], f"source_raw_{i:03d}.mp4")
                    local = adapter.download(asset, dst)
                    ctx.artifacts.register_file(
                        f"sources.raw.{i}",
                        local,
                        {"backend": "drive", "asset_id": asset.id},
                        "video/mp4",
                    )
                    ctx.artifacts.register_url(
                        f"sources.fetch.{i}",
                        adapter.get_fetchable_url(asset),
                        {"backend": "drive", "asset_id": asset.id},
                        "video/mp4",
                    )
            ctx.runtime["drive_adapter"] = adapter
            ctx.runtime["drive_folder_id"] = folder_id
        else:
            if generation_mode == "reference_mimic_mode":
                if not sources:
                    raise RuntimeError("Reference mimic mode requires explicit source URLs when Drive folder is not provided.")
                for i, source in enumerate(sources, start=1):
                    url = str(source.get("url", "")).strip()
                    if not url:
                        raise RuntimeError(f"Source {i} is missing URL.")
                    trim_start = _extract_start_override(source)
                    if _is_direct_shotstack_source_url(url):
                        ctx.artifacts.register_url(
                            f"sources.fetch.{i}",
                            url,
                            {"backend": "url", "trim_start": trim_start},
                            "video/mp4",
                        )
                    else:
                        segment_bounds = _extract_bounded_segment(source)
                        if segment_bounds and ("youtube.com" in url.lower() or "youtu.be" in url.lower()):
                            local = download_video_section(
                                url=url,
                                output_dir=dirs["media"],
                                filename=f"source_raw_{i:03d}.mp4",
                                start_time=segment_bounds[0],
                                end_time=segment_bounds[1],
                            )
                            trim_start = 0.0
                        else:
                            local = download_video(url, dirs["media"], f"source_raw_{i:03d}.mp4")
                        ctx.artifacts.register_file(
                            f"sources.raw.{i}",
                            local,
                            {"backend": "url", "source_url": url, "trim_start": trim_start},
                            "video/mp4",
                        )
                        ctx.artifacts.register_file(
                            f"sources.fetch.{i}",
                            local,
                            {"backend": "local", "source_url": url, "trim_start": trim_start},
                            "video/mp4",
                        )
            else:
                # Preserve current free-mode behavior by using existing clip downloader.
                clip_result = download_and_clip(sources, os.path.join(dirs["media"], "source_work"))
                if not clip_result.get("success"):
                    raise RuntimeError(f"Clipping failed: {clip_result.get('error')}")
                clips = clip_result.get("clips") or []
                if not clips:
                    raise RuntimeError("No source clips found.")
                for i, clip in enumerate(clips, start=1):
                    p = clip["path"]
                    ctx.artifacts.register_file(f"sources.raw.{i}", p, {"backend": "url"}, "video/mp4")
                    ctx.artifacts.register_file(f"sources.fetch.{i}", p, {"backend": "local"}, "video/mp4")

    _run_stage(
        ctx,
        StageName.FETCH_SOURCES,
        stage_fetch_sources,
        done_check=lambda: ctx.artifacts.exists("sources.raw.1") or ctx.artifacts.exists("sources.fetch.1"),
    )
    if ctx.runtime.get("failed"):
        return _build_failure_response(ctx)

    # ALIGN_SOURCES
    def stage_align_sources():
        analysis = json.load(open(ctx.artifacts.get("analysis.json").path_or_url, "r", encoding="utf-8"))
        scene_durations = [
            float(s.get("duration", 0.0))
            for s in (analysis.get("scenes") or [])
            if float(s.get("duration", 0.0)) > 0
        ]
        raw_keys = _sorted_indexed_artifact_keys(ctx.artifacts.items, "sources.raw.")
        raw_paths = [ctx.artifacts.get(k).path_or_url for k in raw_keys]
        aligned_paths, notice = _align_sources(raw_paths, scene_durations, os.path.join(dirs["media"], "aligned"))
        if notice:
            if requirements.get("generation_mode") == "reference_mimic_mode":
                raise RuntimeError(notice)
            add_warning(ctx.state, "SOURCE_DURATION_SHORT", notice)
            return
        if not aligned_paths:
            return
        for i, p in enumerate(aligned_paths, start=1):
            ctx.artifacts.register_file(f"sources.aligned.{i}", p, {"aligned": True}, "video/mp4")

        # Update fetch URLs to aligned outputs if possible.
        drive_adapter = ctx.runtime.get("drive_adapter")
        drive_folder = ctx.runtime.get("drive_folder_id")
        if drive_adapter and drive_folder:
            try:
                for i, p in enumerate(aligned_paths, start=1):
                    uploaded = drive_adapter.upload(p, drive_folder)
                    ctx.artifacts.register_url(
                        f"sources.fetch.{i}",
                        drive_adapter.get_fetchable_url(uploaded),
                        {"backend": "drive", "aligned": True, "asset_id": uploaded.id},
                        "video/mp4",
                    )
            except Exception as e:
                add_warning(
                    ctx.state,
                    "DRIVE_UPLOAD_TIMEOUT",
                    "Aligned clip upload to Drive failed; using original Drive links.",
                    str(e),
                )
        else:
            for i, p in enumerate(aligned_paths, start=1):
                ctx.artifacts.register_file(f"sources.fetch.{i}", p, {"backend": "local", "aligned": True}, "video/mp4")

    _run_stage(
        ctx,
        StageName.ALIGN_SOURCES,
        stage_align_sources,
        done_check=lambda: requirements.get("generation_mode") == "reference_mimic_mode"
        or ctx.artifacts.exists("sources.aligned.1")
        or ctx.state.stages[StageName.ALIGN_SOURCES.value].status in {StageStatus.SUCCEEDED, StageStatus.SKIPPED},
    )
    if ctx.runtime.get("failed"):
        return _build_failure_response(ctx)

    # AUDIO_PLAN
    def stage_audio_plan():
        soundtrack_url = None
        music_mode = requirements.get("music_mode", "original")
        custom_music_url = requirements.get("custom_music_url")
        music_segment = _extract_music_segment(requirements)
        use_reference_audio_bed = False
        mute_source_audio = False
        if music_mode == "custom" and custom_music_url:
            custom_video = None
            if music_segment:
                seg_start, seg_end = music_segment
                if seg_end is not None and _is_youtube_url(custom_music_url):
                    try:
                        custom_video = download_video_section(
                            url=custom_music_url,
                            output_dir=dirs["media"],
                            filename="custom_music_source.mp4",
                            start_time=float(seg_start),
                            end_time=float(seg_end),
                        )
                    except VideoDownloadError:
                        custom_video = None
                if custom_video:
                    soundtrack_file = extract_audio(custom_video, dirs["media"], "custom_music.mp3")
                else:
                    full_video = download_video(custom_music_url, dirs["media"], "custom_music_source.mp4")
                    soundtrack_file = extract_audio_segment(
                        full_video,
                        dirs["media"],
                        "custom_music.mp3",
                        start_time=seg_start,
                        end_time=seg_end,
                    )
            else:
                custom_video = download_video(custom_music_url, dirs["media"], "custom_music_source.mp4")
                soundtrack_file = extract_audio(custom_video, dirs["media"], "custom_music.mp3")
            ctx.artifacts.register_file("audio.soundtrack", soundtrack_file, {"mode": "custom"}, "audio/mpeg")
            soundtrack_url = soundtrack_file
        elif music_mode == "original" and requirements.get("generation_mode") == "reference_mimic_mode":
            primary = ctx.artifacts.get("primary.video").path_or_url
            soundtrack_file = extract_audio(primary, dirs["media"], "reference_audio.mp3")
            ctx.artifacts.register_file("audio.soundtrack", soundtrack_file, {"mode": "reference_primary"}, "audio/mpeg")
            soundtrack_url = soundtrack_file
            use_reference_audio_bed = True
            mute_source_audio = True
        audio_plan = build_audio_plan(
            {
                "soundtrack_url": soundtrack_url,
                "use_reference_audio_bed": use_reference_audio_bed,
                "mute_source_audio": mute_source_audio,
            },
            requirements,
        )
        write_plan(dirs["job"], "audio_plan.json", audio_plan)

    _run_stage(
        ctx,
        StageName.AUDIO_PLAN,
        stage_audio_plan,
        done_check=lambda: os.path.exists(os.path.join(dirs["plans"], "audio_plan.json")),
    )
    if ctx.runtime.get("failed"):
        return _build_failure_response(ctx)

    # RENDER_PLAN
    def stage_render_plan():
        analysis = json.load(open(ctx.artifacts.get("analysis.json").path_or_url, "r", encoding="utf-8"))
        summary = open(ctx.artifacts.get("analysis.summary").path_or_url, "r", encoding="utf-8").read()
        generation_mode = requirements.get("generation_mode", "free_generation_mode")
        edit_mode = str(requirements.get("edit_mode", "scene")).lower().strip()
        if edit_mode not in {"scene", "ocr"}:
            edit_mode = "scene"

        if generation_mode == "reference_mimic_mode":
            source_keys = _sorted_indexed_artifact_keys(ctx.artifacts.items, "sources.fetch.")
            if not source_keys:
                raise RuntimeError("Reference mimic mode requires fetchable source URLs.")
            # Reference mimic timing comes from analyzed timeline (scene or OCR), not source probes.
            # Avoid slow/fragile remote duration probes for Drive URLs.
            src_durations = []
        else:
            source_keys = _sorted_indexed_artifact_keys(ctx.artifacts.items, "sources.aligned.")
            if not source_keys:
                source_keys = _sorted_indexed_artifact_keys(ctx.artifacts.items, "sources.raw.")
            src_paths = [ctx.artifacts.get(k).path_or_url for k in source_keys]
            src_durations = [_probe_duration(p) for p in src_paths]
        render_duration = float(sum(d for d in src_durations if d > 0))
        analysis_duration = max(
            max((float(s.get("end_time", 0.0)) for s in (analysis.get("scenes") or [])), default=0.0),
            max((float(k.get("timestamp", 0.0)) for k in (analysis.get("keyframes") or [])), default=0.0),
        )

        montage_mode = bool(source_keys and len(source_keys) > 1)
        overlay_plan = build_overlay_plan(
            analysis,
            requirements,
            summary,
            render_duration=render_duration if render_duration > 0 else None,
            analysis_duration=analysis_duration if analysis_duration > 0 else None,
            montage_mode=montage_mode,
        )
        timeline_plan = build_timeline_plan(analysis.get("scenes") or [], src_durations, requirements)
        audio_plan = json.load(open(os.path.join(dirs["plans"], "audio_plan.json"), "r", encoding="utf-8"))
        render_spec = build_render_spec(timeline_plan, overlay_plan, audio_plan, requirements)
        postprocess_plan = build_postprocess_plan(requirements)

        if edit_mode == "ocr":
            ocr_source_keys = _sorted_indexed_artifact_keys(ctx.artifacts.items, "sources.fetch.")
            if not ocr_source_keys:
                ocr_source_keys = source_keys
            if not ocr_source_keys:
                raise RuntimeError("OCR mode requires at least one source clip.")

            source_rows = []
            for idx, key in enumerate(ocr_source_keys, start=1):
                art = ctx.artifacts.get(key)
                meta = art.meta or {}
                trim_start = float(meta.get("trim_start", 0.0) or 0.0)
                if generation_mode == "reference_mimic_mode":
                    trim_start = 0.0
                probe_src = art.path_or_url
                raw_art = ctx.artifacts.get(f"sources.raw.{idx}")
                if raw_art and raw_art.type == "file" and os.path.exists(raw_art.path_or_url):
                    probe_src = raw_art.path_or_url
                source_rows.append(
                    {
                        "index": idx,
                        "video_src": art.path_or_url,
                        "probe_src": probe_src,
                        "trim": trim_start,
                    }
                )

            ocr_segments = overlay_plan.get("text_segments") or []
            canonical_timeline = _build_ocr_timeline(
                text_segments=ocr_segments,
                sources=source_rows,
                strict_index_alignment=(generation_mode == "reference_mimic_mode"),
            )
            edit_ops = _parse_edit_ops(requirements)
            edit_summary = None
            if edit_ops:
                canonical_timeline, edit_summary = _apply_edit_ops_to_timeline(canonical_timeline, edit_ops)
                if edit_summary.get("applied"):
                    add_warning(
                        ctx.state,
                        "MANUAL_EDIT_APPLIED",
                        "Applied manual edit operations to OCR timeline.",
                        edit_summary,
                    )
            for row in canonical_timeline:
                if "text" in row:
                    row["text"] = _sanitize_overlay_text(row.get("text", ""))
            overlay_timing = _build_overlay_timing_from_timeline(canonical_timeline)
            skip_validation = bool(edit_summary and (edit_summary.get("timing_changed") or edit_summary.get("count_changed")))
            if not skip_validation:
                ocr_errors = _validate_ocr_timeline(
                    text_segments=ocr_segments,
                    timeline=canonical_timeline,
                    overlay_timing=overlay_timing,
                )
                if ocr_errors:
                    raise RuntimeError("OCR timing validation failed:\n" + "\n".join(ocr_errors))
            render_spec["canonical_timeline"] = canonical_timeline
            render_spec["overlay_timing"] = overlay_timing
            if edit_summary:
                render_spec["edit_summary"] = edit_summary
                render_spec["edit_ops"] = edit_ops

        elif generation_mode == "reference_mimic_mode":
            source_rows = []
            for idx, key in enumerate(source_keys, start=1):
                art = ctx.artifacts.get(key)
                trim_start = 0.0
                probe_src = art.path_or_url
                raw_art = ctx.artifacts.get(f"sources.raw.{idx}")
                if raw_art and raw_art.type == "file" and os.path.exists(raw_art.path_or_url):
                    probe_src = raw_art.path_or_url
                source_rows.append(
                    {
                        "index": idx,
                        "video_src": art.path_or_url,
                        "probe_src": probe_src,
                        "trim": trim_start,
                    }
                )
            canonical_timeline = _build_reference_timeline(
                analysis=analysis,
                sources=source_rows,
            )
            script = overlay_plan.get("overlay_script") or {}
            script_texts = []
            if isinstance(script, dict):
                if script.get("title"):
                    script_texts.append(str(script.get("title")))
                script_texts.extend([str(x) for x in (script.get("items") or []) if str(x)])
            if not script_texts:
                script_texts = [str(o.get("text", "")).strip() for o in (overlay_plan.get("overlays") or []) if str(o.get("text", "")).strip()]
            # Strict mimic policy: overlay timing always inherits scene timing exactly.
            for i, scene in enumerate(canonical_timeline):
                text = script_texts[i] if i < len(script_texts) else ""
                start = float(scene["start"])
                end = float(scene["end"])
                scene["text"] = _sanitize_overlay_text(text)
                scene["text_start"] = start
                scene["text_end"] = end
            edit_ops = _parse_edit_ops(requirements)
            edit_summary = None
            if edit_ops:
                canonical_timeline, edit_summary = _apply_edit_ops_to_timeline(canonical_timeline, edit_ops)
                if edit_summary.get("applied"):
                    add_warning(
                        ctx.state,
                        "MANUAL_EDIT_APPLIED",
                        "Applied manual edit operations to reference timeline.",
                        edit_summary,
                    )
            for row in canonical_timeline:
                if "text" in row:
                    row["text"] = _sanitize_overlay_text(row.get("text", ""))
            overlay_timing = _build_overlay_timing_from_timeline(canonical_timeline)
            reference_audio_duration = None
            if audio_plan.get("use_reference_audio_bed") and ctx.artifacts.exists("audio.soundtrack"):
                reference_audio_duration = _probe_duration(ctx.artifacts.get("audio.soundtrack").path_or_url)
            skip_validation = bool(edit_summary and (edit_summary.get("timing_changed") or edit_summary.get("count_changed")))
            if not skip_validation:
                errors = _validate_reference_timeline(
                    analysis=analysis,
                    timeline=canonical_timeline,
                    overlay_timing=overlay_timing,
                    use_reference_audio=bool(audio_plan.get("use_reference_audio_bed")),
                    reference_audio_duration=reference_audio_duration,
                )
                if errors:
                    raise RuntimeError("Reference mimic validation failed:\n" + "\n".join(errors))
            render_spec["canonical_timeline"] = canonical_timeline
            render_spec["overlay_timing"] = overlay_timing
            if edit_summary:
                render_spec["edit_summary"] = edit_summary
                render_spec["edit_ops"] = edit_ops

        write_plan(dirs["job"], "overlay_plan.json", overlay_plan)
        write_plan(
            dirs["job"],
            "overlay_script.json",
            overlay_plan.get("overlay_script") or {"title": "", "items": [], "source": ""},
        )
        if render_spec.get("canonical_timeline"):
            write_plan(
                dirs["job"],
                "canonical_timeline.json",
                {
                    "generation_mode": generation_mode,
                    "edit_mode": edit_mode,
                    "timeline": render_spec.get("canonical_timeline", []),
                },
            )
            write_plan(
                dirs["job"],
                "overlay_timing.json",
                {
                    "generation_mode": generation_mode,
                    "edit_mode": edit_mode,
                    "overlays": render_spec.get("overlay_timing", []),
                },
            )
        write_plan(
            dirs["job"],
            "text_segments.json",
            {
                "segments": overlay_plan.get("text_segments", []),
                "warnings": overlay_plan.get("warnings", []),
                "analysis_duration": analysis_duration,
                "render_duration": render_duration,
            },
        )
        write_plan(dirs["job"], "timeline_plan.json", timeline_plan)
        write_plan(dirs["job"], "render_spec.json", render_spec)
        write_plan(dirs["job"], "postprocess_plan.json", postprocess_plan)
        for w in overlay_plan.get("warnings", []):
            add_warning(ctx.state, w.get("code", "OVERLAY_WARNING"), w.get("message", "Overlay warning"), w.get("detail"))

    _run_stage(
        ctx,
        StageName.RENDER_PLAN,
        stage_render_plan,
        done_check=lambda: os.path.exists(os.path.join(dirs["plans"], "render_spec.json")),
    )
    if ctx.runtime.get("failed"):
        return _build_failure_response(ctx)

    # SHOTSTACK_RENDER
    def stage_shotstack_render():
        spec = json.load(open(os.path.join(dirs["plans"], "render_spec.json"), "r", encoding="utf-8"))
        canonical_timeline = spec.get("canonical_timeline") or []
        edit_summary = spec.get("edit_summary") or {}
        generation_mode = str(spec.get("generation_mode", requirements.get("generation_mode", "free_generation_mode"))).lower()
        edit_mode = str(spec.get("edit_mode", requirements.get("edit_mode", "scene"))).lower().strip()
        if edit_mode not in {"scene", "ocr"}:
            edit_mode = "scene"
        if generation_mode == "reference_mimic_mode" and edit_mode == "scene" and not canonical_timeline:
            raise RuntimeError(
                "reference_mimic_mode requires canonical_timeline in render_spec; refusing non-canonical render."
            )
        if edit_mode == "ocr" and not canonical_timeline:
            raise RuntimeError(
                "OCR mode requires canonical_timeline in render_spec; refusing scene-timed fallback."
            )
        fetch_entries = []
        if canonical_timeline:
            for idx, row in enumerate(canonical_timeline, start=1):
                fetch_entries.append(
                    {
                        "key": f"timeline.scene.{idx}",
                        "path": row.get("video_src"),
                        "meta": {"timeline": True},
                    }
                )
        else:
            fetch_keys = _sorted_indexed_artifact_keys(ctx.artifacts.items, "sources.fetch.")
            if not fetch_keys:
                raise RuntimeError("No fetchable sources available for rendering.")
            for k in fetch_keys:
                art = ctx.artifacts.get(k)
                fetch_entries.append({"key": k, "path": art.path_or_url, "meta": art.meta or {}})
        local_uploads = [os.path.normpath(e["path"]) for e in fetch_entries if e["path"] and not _is_http_url(e["path"])]
        shotstack_links = _upload_assets_for_shotstack(ctx.job_id, local_uploads) if local_uploads else []
        shotstack_links_path = os.path.join(dirs["plans"], "shotstack_asset_links.json")
        os.makedirs(dirs["plans"], exist_ok=True)
        with open(shotstack_links_path, "w", encoding="utf-8") as f:
            json.dump(shotstack_links, f, ensure_ascii=False, indent=2)
        ctx.artifacts.register_file("sources.aligned.drive_links", shotstack_links_path, {"uploaded": bool(shotstack_links)}, "application/json")
        upload_map = {os.path.normpath(item["local_path"]): item for item in shotstack_links}
        for entry in fetch_entries:
            path = entry["path"]
            normalized = os.path.normpath(path) if path else None
            public_url = path
            if normalized and normalized in upload_map:
                public_url = upload_map[normalized]["public_url"]
                if entry["key"].startswith("sources.fetch."):
                    ctx.artifacts.register_url(
                        entry["key"],
                        public_url,
                        {"backend": "drive", **({"aligned": entry["meta"].get("aligned")} if entry["meta"].get("aligned") else {})},
                        "video/mp4",
                    )
            entry["public_url"] = public_url
        video_urls = [entry["public_url"] for entry in fetch_entries if entry["public_url"]]

        if canonical_timeline:
            for i, row in enumerate(canonical_timeline):
                local_src = os.path.normpath(str(row.get("video_src", "")))
                if local_src in upload_map:
                    canonical_timeline[i]["video_src"] = upload_map[local_src]["public_url"]
                elif _is_http_url(row.get("video_src")):
                    canonical_timeline[i]["video_src"] = row.get("video_src")
                else:
                    raise RuntimeError(f"Canonical timeline source is not fetchable: {row.get('video_src')}")

            # Guard against accidental clip-count drift before render.
            analysis = json.load(open(ctx.artifacts.get("analysis.json").path_or_url, "r", encoding="utf-8"))
            analyzed_scenes = analysis.get("scenes") or []
            if (
                generation_mode == "reference_mimic_mode"
                and edit_mode == "scene"
                and len(canonical_timeline) != len(analyzed_scenes)
                and not (edit_summary.get("count_changed") or edit_summary.get("timing_changed"))
            ):
                raise RuntimeError(
                    f"reference_mimic_mode clip-count mismatch: canonical={len(canonical_timeline)} analyzed={len(analyzed_scenes)}"
                )

        probe_keys = _sorted_indexed_artifact_keys(ctx.artifacts.items, "sources.aligned.")
        if not probe_keys:
            probe_keys = _sorted_indexed_artifact_keys(ctx.artifacts.items, "sources.raw.")
        duration_probe_urls = None if canonical_timeline else [
            ctx.artifacts.get(k).path_or_url for k in probe_keys
        ]

        for idx, url in enumerate(video_urls, start=1):
            if not _is_http_url(url):
                raise RuntimeError(f"Shotstack asset URL invalid: {url} (entry {idx})")

        soundtrack_url = spec.get("soundtrack_url")
        if soundtrack_url and not _is_http_url(soundtrack_url):
            sound_uploads = _upload_assets_for_shotstack(ctx.job_id, [soundtrack_url])
            if not sound_uploads:
                raise RuntimeError("Failed to upload local soundtrack for Shotstack.")
            soundtrack_url = sound_uploads[0]["public_url"]
            spec["soundtrack_url"] = soundtrack_url

        render_result = create_and_render_video(
            api_key=os.getenv("SHOTSTACK_KEY"),
            video_urls=video_urls,
            duration_probe_urls=duration_probe_urls,
            project_title=f"Auto-Edit ({ctx.job_id})",
            overlay_text=[requirements.get("prompt", "")[:50]],
            soundtrack_url=soundtrack_url,
            music_mode=spec.get("music_mode", "original"),
            resolution=spec.get("resolution", "1080x1920"),
            wait_for_render=True,
            overlay_plan=spec.get("overlay_plan") or None,
            overlay_timing=spec.get("overlay_timing") or None,
            overlay_script=spec.get("overlay_script") or None,
            timing_mode=str(spec.get("timing_mode", "ocr_keyframe")),
            generation_mode=str(spec.get("generation_mode", requirements.get("generation_mode", "free_generation_mode"))),
            canonical_timeline=canonical_timeline or None,
            force_mobile_safe_text=bool(spec.get("force_mobile_safe_text")),
            mobile_safe_text_mode=bool(spec.get("mobile_safe_text_mode", False)),
            overlay_full_clip=bool(spec.get("overlay_full_clip")),
            mute_source_audio=bool(spec.get("mute_source_audio", False)),
            disable_auto_transitions=bool(spec.get("disable_auto_transitions", False)),
            refit_mode=str(spec.get("refit_mode", requirements.get("refit_mode", "crop_center"))),
            output_mode=str(spec.get("output_mode", requirements.get("output_mode", "crop_to_9x16"))),
            debug_text_visibility=bool(requirements.get("debug_text_visibility", False)),
            debug_render_spec_path=os.path.join(dirs["plans"], "render_spec.json"),
            debug_overlay_timing_path=os.path.join(dirs["plans"], "overlay_timing.json"),
            debug_shotstack_payload_path=os.path.join(dirs["plans"], "shotstack_request_payload.json"),
        )
        if not render_result.get("success") or not render_result.get("url"):
            raise RuntimeError(
                f"Render failed: {render_result.get('error') or 'No output URL returned.'}"
            )

        master_name = "master_16x9.mp4"
        master_path = os.path.join(dirs["outputs"], master_name)
        _download_file(render_result["url"], master_path)
        ctx.artifacts.register_file("render.master_16x9", master_path, {"render_id": render_result.get("render_id")}, "video/mp4")
        ctx.artifacts.register_url("render.shotstack_url", render_result["url"], {"render_id": render_result.get("render_id")}, "video/mp4")
        ctx.runtime["render_result"] = render_result

    _run_stage(
        ctx,
        StageName.SHOTSTACK_RENDER,
        stage_shotstack_render,
        done_check=lambda: _artifact_path_exists(ctx.artifacts, "render.master_16x9"),
    )
    if ctx.runtime.get("failed"):
        return _build_failure_response(ctx)

    # POSTPROCESS
    def stage_postprocess():
        plan = json.load(open(os.path.join(dirs["plans"], "postprocess_plan.json"), "r", encoding="utf-8"))
        if not plan.get("create_shorts"):
            update_stage(ctx.state, StageName.POSTPROCESS, StageStatus.SKIPPED, {"reason": "intent_mode=video"})
            _save(ctx)
            return
        master = ctx.artifacts.get("render.master_16x9").path_or_url
        short_path = os.path.join(dirs["outputs"], "short_9x16.mp4")
        try:
            _run_shorts_refit(master, short_path, plan.get("refit_mode", "crop_center"))
            ctx.artifacts.register_file("render.short_9x16", short_path, {"refit_mode": plan.get("refit_mode", "crop_center")}, "video/mp4")
        except Exception as e:
            add_warning(
                ctx.state,
                "FFMPEG_POSTPROCESS_FAILED",
                "Shorts conversion failed; using master preview fallback.",
                str(e),
            )

    _run_stage(
        ctx,
        StageName.POSTPROCESS,
        stage_postprocess,
        done_check=lambda: _artifact_path_exists(ctx.artifacts, "render.short_9x16")
        or (
            os.path.exists(os.path.join(dirs["plans"], "postprocess_plan.json"))
            and not json.load(open(os.path.join(dirs["plans"], "postprocess_plan.json"), "r", encoding="utf-8")).get("create_shorts")
        ),
    )
    if ctx.runtime.get("failed"):
        return _build_failure_response(ctx)

    # PUBLISH
    def stage_publish():
        create_shorts = json.load(open(os.path.join(dirs["plans"], "postprocess_plan.json"), "r", encoding="utf-8")).get("create_shorts")
        if create_shorts and _artifact_path_exists(ctx.artifacts, "render.short_9x16"):
            preview_key = "render.short_9x16"
            preview_mode = "shorts"
            preview_name = "short_9x16.mp4"
        else:
            preview_key = "render.master_16x9"
            preview_mode = "video"
            preview_name = "master_16x9.mp4"
        preview_url = f"/files/{ctx.job_id}/outputs/{preview_name}"
        ctx.runtime["preview_url"] = preview_url
        ctx.runtime["preview_mode"] = preview_mode
        ctx.runtime["preview_key"] = preview_key

    _run_stage(ctx, StageName.PUBLISH, stage_publish)
    if ctx.runtime.get("failed"):
        return _build_failure_response(ctx)

    # CLEANUP (deferred by design)
    update_stage(ctx.state, StageName.CLEANUP, StageStatus.SKIPPED, {"reason": "deferred_until_youtube_upload"})
    _save(ctx)

    # Response mapping (backward compatible + optional warnings/errors)
    render_url_art = ctx.artifacts.get("render.shotstack_url")
    render_url = render_url_art.path_or_url if render_url_art else None
    render_id = (render_url_art.meta or {}).get("render_id") if render_url_art else None
    warnings = ctx.state.warnings
    user_notice = next((w["message"] for w in warnings if w.get("code") == "SOURCE_DURATION_SHORT"), None)
    ffmpeg_error = next((w.get("detail") for w in warnings if w.get("code") == "FFMPEG_POSTPROCESS_FAILED"), None)
    intent_mode = requirements.get("intent_mode", "video")
    render_spec = json.load(open(os.path.join(dirs["plans"], "render_spec.json"), "r", encoding="utf-8"))
    render_aspect = "16:9" if render_spec.get("resolution") == "1920x1080" else "9:16"

    if ctx.state.errors:
        last = ctx.state.errors[-1]
        return {
            "success": False,
            "error": last.get("message", "Pipeline failed."),
            "render_id": render_id,
            "status": "failed",
            "project_id": ctx.job_id,
            "warnings": warnings,
            "errors": ctx.state.errors,
            "user_notice": user_notice,
            "ffmpeg_error": ffmpeg_error,
        }

    return {
        "success": True,
        "url": render_url,
        "render_id": render_id,
        "status": "done",
        "project_id": ctx.job_id,
        "intent_mode": intent_mode,
        "refit_mode": requirements.get("refit_mode", "crop_center"),
        "output_mode": requirements.get("output_mode", "crop_to_9x16"),
        "render_aspect": render_aspect,
        "preview_url": ctx.runtime.get("preview_url"),
        "preview_mode": ctx.runtime.get("preview_mode", "video"),
        "user_notice": user_notice,
        "ffmpeg_error": ffmpeg_error,
        "warnings": warnings,
        "errors": ctx.state.errors,
    }
