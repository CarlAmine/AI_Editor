import json
import os
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests

from ai_editor.analyzer import analyze_video_content_with_results
from ai_editor.downloader import VideoClapError, VideoDownloadError, clip_video, download_and_clip, download_video, extract_audio
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
    return os.getenv("DRIVE_DEFAULT_FOLDER_ID") or os.getenv("VIDEO_FOLDER")


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
    si = 0
    soff = 0.0
    for i, td in enumerate(scene_durations, start=1):
        if si >= len(src):
            break
        cur = src[si]
        rem = max(0.0, cur["dur"] - soff)
        if rem <= 0.05:
            si += 1
            soff = 0.0
            continue
        take = min(td, rem)
        if take <= 0.05:
            continue
        dst = os.path.join(out_dir, f"aligned_{i:03d}.mp4")
        clip_video(cur["path"], dst, soff, soff + take)
        aligned.append(dst)
        soff += take
        if soff >= cur["dur"] - 0.05:
            si += 1
            soff = 0.0
    return aligned, None


def _build_reference_timeline(
    analysis: Dict[str, Any],
    source_paths: List[str],
    work_dir: str,
) -> List[Dict[str, Any]]:
    scenes = analysis.get("scenes") or []
    if not scenes:
        raise RuntimeError("Reference mimic mode requires analyzed scenes.")
    durations = [float(s.get("duration", 0.0)) for s in scenes]
    if any(d <= 0 for d in durations):
        raise RuntimeError("Reference mimic mode requires positive analyzed scene durations.")
    os.makedirs(work_dir, exist_ok=True)
    source_info = []
    for p in source_paths:
        d = _probe_duration(p)
        if d > 0:
            source_info.append({"path": p, "duration": d})
    if not source_info:
        raise RuntimeError("No valid source clips available for reference mimic mode.")

    timeline = []
    used_paths = set()
    for idx, scene in enumerate(scenes, start=1):
        target_duration = float(scene.get("duration", 0.0))
        chosen = next((s for s in source_info if s["path"] not in used_paths and s["duration"] + 0.02 >= target_duration), None)
        if chosen is None:
            chosen = next((s for s in source_info if s["duration"] + 0.02 >= target_duration), None)
        if chosen is None:
            raise RuntimeError(
                f"Reference mimic assignment failed for scene {idx}: no clip long enough for {target_duration:.2f}s."
            )
        used_paths.add(chosen["path"])
        out_path = os.path.join(work_dir, f"ref_scene_{idx:03d}.mp4")
        clip_video(chosen["path"], out_path, 0.0, target_duration)
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
                "videoSrc": out_path,
                "video_src": out_path,
                "trim": 0.0,
                "transitionIn": None,
                "transitionOut": None,
                "text": "",
                "text_start": start,
                "text_end": end,
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
    if use_reference_audio and reference_audio_duration is not None:
        if abs(reference_audio_duration - generated_total) > 0.2:
            errors.append(
                f"reference_audio_duration mismatch: audio={reference_audio_duration:.3f}, timeline={generated_total:.3f}"
            )
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
    requirements["generation_mode"] = str(requirements.get("generation_mode", "free_generation_mode")).lower()
    if requirements["generation_mode"] not in {"free_generation_mode", "reference_mimic_mode"}:
        requirements["generation_mode"] = "free_generation_mode"
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
        if folder_id:
            adapter = DriveStorageAdapter()
            assets = adapter.list_videos(folder_id)
            if not assets:
                raise RuntimeError("No video files found in provided Google Drive folder.")
            for i, asset in enumerate(assets, start=1):
                dst = os.path.join(dirs["media"], f"source_raw_{i:03d}.mp4")
                local = adapter.download(asset, dst)
                ctx.artifacts.register_file(f"sources.raw.{i}", local, {"backend": "drive", "asset_id": asset.id}, "video/mp4")
                ctx.artifacts.register_url(f"sources.fetch.{i}", adapter.get_fetchable_url(asset), {"backend": "drive", "asset_id": asset.id}, "video/mp4")
            ctx.runtime["drive_adapter"] = adapter
            ctx.runtime["drive_folder_id"] = folder_id
        else:
            # Preserve current behavior by using existing clip downloader.
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
        done_check=lambda: ctx.artifacts.exists("sources.raw.1"),
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
        raw_keys = sorted(k for k in ctx.artifacts.items if k.startswith("sources.raw."))
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
        done_check=lambda: ctx.artifacts.exists("sources.aligned.1") or ctx.state.stages[StageName.ALIGN_SOURCES.value].status in {StageStatus.SUCCEEDED, StageStatus.SKIPPED},
    )
    if ctx.runtime.get("failed"):
        return _build_failure_response(ctx)

    # AUDIO_PLAN
    def stage_audio_plan():
        soundtrack_url = None
        music_mode = requirements.get("music_mode", "original")
        custom_music_url = requirements.get("custom_music_url")
        use_reference_audio_bed = False
        mute_source_audio = False
        if music_mode == "custom" and custom_music_url:
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

        source_keys = sorted(k for k in ctx.artifacts.items if k.startswith("sources.aligned."))
        if not source_keys:
            source_keys = sorted(k for k in ctx.artifacts.items if k.startswith("sources.raw."))
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

        if generation_mode == "reference_mimic_mode":
            canonical_timeline = _build_reference_timeline(
                analysis=analysis,
                source_paths=src_paths,
                work_dir=os.path.join(dirs["media"], "mimic"),
            )
            script = overlay_plan.get("overlay_script") or {}
            script_texts = []
            if isinstance(script, dict):
                if script.get("title"):
                    script_texts.append(str(script.get("title")))
                script_texts.extend([str(x) for x in (script.get("items") or []) if str(x)])
            if not script_texts:
                script_texts = [str(o.get("text", "")).strip() for o in (overlay_plan.get("overlays") or []) if str(o.get("text", "")).strip()]
            overlay_timing = []
            # Strict mimic policy: overlay timing always inherits scene timing exactly.
            for i, scene in enumerate(canonical_timeline):
                text = script_texts[i] if i < len(script_texts) else ""
                start = float(scene["start"])
                end = float(scene["end"])
                overlay_timing.append(
                    {
                        "index": i + 1,
                        "text": text,
                        "start": start,
                        "end": end,
                        "length": max(0.0, end - start),
                    }
                )
                scene["text"] = text
                scene["text_start"] = start
                scene["text_end"] = end
            reference_audio_duration = None
            if audio_plan.get("use_reference_audio_bed") and ctx.artifacts.exists("audio.soundtrack"):
                reference_audio_duration = _probe_duration(ctx.artifacts.get("audio.soundtrack").path_or_url)
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

        write_plan(dirs["job"], "overlay_plan.json", overlay_plan)
        write_plan(
            dirs["job"],
            "overlay_script.json",
            overlay_plan.get("overlay_script") or {"title": "", "items": [], "source": ""},
        )
        if generation_mode == "reference_mimic_mode":
            write_plan(
                dirs["job"],
                "canonical_timeline.json",
                {"mode": generation_mode, "timeline": render_spec.get("canonical_timeline", [])},
            )
            write_plan(
                dirs["job"],
                "overlay_timing.json",
                {"mode": generation_mode, "overlays": render_spec.get("overlay_timing", [])},
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
        generation_mode = str(spec.get("generation_mode", requirements.get("generation_mode", "free_generation_mode"))).lower()
        if generation_mode == "reference_mimic_mode" and not canonical_timeline:
            raise RuntimeError(
                "reference_mimic_mode requires canonical_timeline in render_spec; refusing non-canonical render."
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
            fetch_keys = sorted(k for k in ctx.artifacts.items if k.startswith("sources.fetch."))
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
            if generation_mode == "reference_mimic_mode" and len(canonical_timeline) != len(analyzed_scenes):
                raise RuntimeError(
                    f"reference_mimic_mode clip-count mismatch: canonical={len(canonical_timeline)} analyzed={len(analyzed_scenes)}"
                )

        probe_keys = sorted(k for k in ctx.artifacts.items if k.startswith("sources.aligned."))
        if not probe_keys:
            probe_keys = sorted(k for k in ctx.artifacts.items if k.startswith("sources.raw."))
        duration_probe_urls = None if generation_mode == "reference_mimic_mode" else [
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
