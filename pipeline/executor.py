from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

log = logging.getLogger(__name__)

from ai_editor.analyzer import analyze_video_content_with_results
from ai_editor.analysis.analysis_schema import MotionEffectManifest
from ai_editor.semantic_edit.edit_event_classifier import classify_semantic_edit_events
from ai_editor.semantic_edit.layer_stack import build_layer_stack
from ai_editor.semantic_edit.object_detector import detect_objects
from ai_editor.semantic_edit.object_segmenter import segment_objects
from ai_editor.semantic_edit.object_tracker import track_objects
from ai_editor.semantic_edit.scene_graph import build_semantic_video_graph
from ai_editor.semantic_edit.template_integration import attach_semantic_graph_to_template
from ai_editor.semantic_edit.schemas import SemanticVideoGraph
from ai_editor.vision_template.renderer_adapter import build_render_spec_from_vision_template
from ai_editor.vision_template.frame_sampler import sample_video_frames
from ai_editor.vision_template.schemas import EditTemplate, SlotMapping
from ai_editor.vision_template.train_reference import train_reference_adapter
from ai_editor.rendering.motion_effect_applier import MotionEffectApplier
from ai_editor.downloader import (
    VideoDownloadError,
    _is_youtube_url,
    download_and_clip,
    download_video,
    download_video_section,
    extract_audio,
    extract_audio_segment,
)
from ai_editor.editing import EditSession, InstructionParser
from ai_editor.generation_modes import (
    FREE_GENERATION_MODE,
    REFERENCE_STYLE_TRANSFER_MODE,
    VISION_TEMPLATE_LEARNING_MODE,
    REFERENCE_EDIT_AGENT_MODE,
    normalize_generation_mode,
)
from ai_editor.reference_learning import build_reference_edit_template
from ai_editor.source_inventory import build_source_inventory
from ai_editor.edit_agent import ReferenceEditAgentError, run_edit_agent_compile_stage
from ai_editor.google_auth import GoogleCredentialError
from ai_editor.planning import PlanRewriter, PlanValidator

from .artifacts import ArtifactRegistry
from .decision_engine import PipelineDecision
from .provider_errors import ProviderFailure, normalize_provider_exception
from .plans import (
    build_audio_plan,
    build_overlay_plan,
    build_postprocess_plan,
    build_render_spec,
    build_timeline_plan,
    write_plan,
)
from .state import (
    ControllerStatus,
    JobState,
    JobStatus,
    StageName,
    StageStatus,
    add_error,
    add_warning,
    apply_analysis,
    apply_plan,
    apply_plan_validation,
    build_controller_status_payload,
    clear_plan_validation,
    clear_requested_user_input,
    extract_edit_requests,
    mark_terminal,
    mark_edit_requests_applied,
    pending_edit_requests,
    set_render_summary,
    set_controller_status,
    set_requested_user_input,
    set_source_status,
    summarize_plan,
    touch,
    update_stage,
)
@dataclass
class ExecutionContext:
    job_id: str
    request_payload: Dict[str, Any]
    requirements: Dict[str, Any]
    dirs: Dict[str, str]
    state: JobState
    artifacts: ArtifactRegistry
    runtime: Dict[str, Any] = field(default_factory=dict)


def _write_debug_json(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


class PipelineExecutor:
    """Deterministic executor for bounded pipeline actions."""

    def __init__(
        self,
        *,
        save_hook: Optional[Callable[[ExecutionContext], None]] = None,
        validator: Optional[PlanValidator] = None,
        rewriter: Optional[PlanRewriter] = None,
        instruction_parser: Optional[InstructionParser] = None,
        minimum_validation_score: float = 0.5,
        provider_requirements: Optional[Dict[str, bool]] = None,
    ) -> None:
        self._save_hook = save_hook or (lambda _ctx: None)
        self.validator = validator or PlanValidator()
        self.rewriter = rewriter or PlanRewriter()
        self.instruction_parser = instruction_parser or InstructionParser()
        self.minimum_validation_score = minimum_validation_score
        self._provider_requirements = {"render": True, "drive": True}
        if provider_requirements:
            self._provider_requirements.update(provider_requirements)
        self._routes: Dict[str, Callable[[ExecutionContext, PipelineDecision], None]] = {
            "run_analysis": self._handle_run_analysis,
            "generate_plan": self._handle_generate_plan,
            "revise_plan": self._handle_revise_plan,
            "validate_plan": self._handle_validate_plan,
            "render_preview": self._handle_render_preview,
            "render_final": self._handle_render_final,
            "request_user_input": self._handle_request_user_input,
            "abort_job": self._handle_abort_job,
            "finish": self._handle_finish,
        }
        self._action_stages: Dict[str, StageName] = {
            "run_analysis": StageName.RUN_ANALYSIS,
            "generate_plan": StageName.GENERATE_PLAN,
            "revise_plan": StageName.REVISE_PLAN,
            "validate_plan": StageName.VALIDATE_PLAN,
            "render_preview": StageName.RENDER_PREVIEW,
            "render_final": StageName.RENDER_FINAL,
            "request_user_input": StageName.REQUEST_USER_INPUT,
            "abort_job": StageName.ABORT_JOB,
            "finish": StageName.FINISH,
        }
        self._action_controller_status: Dict[str, ControllerStatus] = {
            "run_analysis": ControllerStatus.ANALYZING,
            "generate_plan": ControllerStatus.PLANNING,
            "revise_plan": ControllerStatus.REVISING,
            "validate_plan": ControllerStatus.VALIDATING,
            "render_preview": ControllerStatus.RENDERING,
            "render_final": ControllerStatus.RENDERING,
        }

    def provider_requirements(self) -> Dict[str, bool]:
        return dict(self._provider_requirements)

    def execute(self, ctx: ExecutionContext, decision: PipelineDecision) -> None:
        handler = self._routes.get(decision.next_action)
        if handler is None:
            raise ValueError(f"Unsupported action: {decision.next_action}")

        if decision.next_action != "request_user_input":
            clear_requested_user_input(ctx.state)
            ctx.state.status = JobStatus.RUNNING
            ctx.state.terminal_status = None
            controller_status = self._action_controller_status.get(decision.next_action)
            if controller_status is not None:
                set_controller_status(ctx.state, controller_status, detail=decision.rationale)

        action_stage = self._action_stages[decision.next_action]
        update_stage(
            ctx.state,
            action_stage,
            StageStatus.RUNNING,
            {
                "confidence": round(float(decision.confidence), 4),
                "rationale": decision.rationale,
                "parameters": decision.parameters,
            },
        )
        self._save(ctx)
        try:
            handler(ctx, decision)
            update_stage(ctx.state, action_stage, StageStatus.SUCCEEDED)
            self._save(ctx)
        except ProviderFailure as exc:
            add_error(ctx.state, action_stage, exc.code, exc.user_message, exc.to_error_detail())
            update_stage(
                ctx.state,
                action_stage,
                StageStatus.FAILED,
                {"code": exc.code, "provider": exc.provider, "retryable": exc.retryable},
            )
            self._save(ctx)
            raise
        except Exception as exc:
            add_error(
                ctx.state,
                action_stage,
                "ACTION_FAILED",
                str(exc),
                {"exception": repr(exc), "action": decision.next_action},
            )
            update_stage(ctx.state, action_stage, StageStatus.FAILED, {"exception": repr(exc)})
            self._save(ctx)
            raise

    def _handle_run_analysis(self, ctx: ExecutionContext, decision: PipelineDecision) -> None:
        generation_mode = normalize_generation_mode(
            ctx.requirements.get("generation_mode"),
            default=FREE_GENERATION_MODE,
        )
        self._run_stage(ctx, StageName.INGEST, lambda: self._stage_ingest(ctx))
        self._run_stage(
            ctx,
            StageName.FETCH_PRIMARY,
            lambda: self._stage_fetch_primary(ctx),
            done_check=lambda: _artifact_path_exists(ctx.artifacts, "primary.video"),
        )
        if generation_mode == VISION_TEMPLATE_LEARNING_MODE:
            update_stage(
                ctx.state,
                StageName.ANALYZE_PRIMARY,
                StageStatus.SKIPPED,
                {"reason": "vision_template_learning"},
            )
            self._save(ctx)
        else:
            self._run_stage(
                ctx,
                StageName.ANALYZE_PRIMARY,
                lambda: self._stage_analyze_primary(ctx),
                done_check=lambda: bool(ctx.state.analysis_available and ctx.artifacts.exists("analysis.json")),
            )
        self._run_stage(
            ctx,
            StageName.FETCH_SOURCES,
            lambda: self._stage_fetch_sources(ctx),
            done_check=lambda: ctx.artifacts.exists("sources.raw.1") or ctx.artifacts.exists("sources.fetch.1"),
        )
        if generation_mode in {REFERENCE_STYLE_TRANSFER_MODE, VISION_TEMPLATE_LEARNING_MODE}:
            update_stage(
                ctx.state,
                StageName.ALIGN_SOURCES,
                StageStatus.SKIPPED,
                {"reason": generation_mode},
            )
            self._save(ctx)
        else:
            self._run_stage(
                ctx,
                StageName.ALIGN_SOURCES,
                lambda: self._stage_align_sources(ctx),
                done_check=lambda: ctx.artifacts.exists("sources.aligned.1"),
            )
        self._refresh_source_status(ctx)

    def _handle_generate_plan(self, ctx: ExecutionContext, decision: PipelineDecision) -> None:
        generation_mode = normalize_generation_mode(
            ctx.requirements.get("generation_mode"),
            default=FREE_GENERATION_MODE,
        )
        if generation_mode == REFERENCE_EDIT_AGENT_MODE:
            self._run_stage(
                ctx,
                StageName.AUDIO_PLAN,
                lambda: self._stage_audio_plan(ctx),
                done_check=lambda: bool(ctx.state.audio_plan),
            )
            self._run_stage(
                ctx,
                StageName.BUILD_REFERENCE_TEMPLATE,
                lambda: self._stage_build_reference_template(ctx),
                done_check=lambda: ctx.artifacts.exists("reference.edit_template"),
            )
            self._run_stage(
                ctx,
                StageName.ANALYZE_SOURCE_INVENTORY,
                lambda: self._stage_analyze_source_inventory(ctx),
                done_check=lambda: ctx.artifacts.exists("source.inventory"),
            )
            self._run_stage(
                ctx,
                StageName.EDIT_AGENT_COMPILE,
                lambda: self._stage_edit_agent_compile(ctx),
                done_check=lambda: ctx.artifacts.exists("render.compiled_spec"),
            )
            return

        if generation_mode == VISION_TEMPLATE_LEARNING_MODE:
            self._run_stage(
                ctx,
                StageName.AUDIO_PLAN,
                lambda: self._stage_audio_plan(ctx),
                done_check=lambda: bool(ctx.state.audio_plan),
            )
            self._run_stage(
                ctx,
                StageName.VISION_TEMPLATE_TRAIN,
                lambda: self._stage_vision_template_train(ctx),
                done_check=lambda: ctx.artifacts.exists("vision.template.json"),
            )
            self._run_stage(
                ctx,
                StageName.VISION_TEMPLATE_TRANSFER,
                lambda: self._stage_vision_template_transfer(ctx),
                done_check=lambda: bool((ctx.state.render_spec or {}).get("canonical_timeline")),
            )
            return
        if not ctx.state.analysis_available:
            raise RuntimeError("Analysis must complete before generating a plan.")
        self._run_stage(
            ctx,
            StageName.AUDIO_PLAN,
            lambda: self._stage_audio_plan(ctx),
            done_check=lambda: bool(ctx.state.audio_plan),
        )
        self._generate_plan_bundle(ctx)

    def _handle_validate_plan(self, ctx: ExecutionContext, decision: PipelineDecision) -> None:
        if not ctx.state.current_plan:
            raise RuntimeError("No plan is available to validate.")
        validation = self.validator.validate(
            ctx.state.current_plan,
            analysis=self._load_analysis(ctx),
            requirements=ctx.requirements,
        )
        apply_plan_validation(ctx.state, validation)
        updated_plan = dict(ctx.state.current_plan)
        updated_plan["plan_validation"] = validation
        ctx.state.current_plan = updated_plan
        ctx.state.plan_summary = summarize_plan(updated_plan)
        write_plan(ctx.dirs["job"], "timeline_plan.json", updated_plan)
        self._save(ctx)

    def _handle_revise_plan(self, ctx: ExecutionContext, decision: PipelineDecision) -> None:
        if not ctx.state.current_plan:
            raise RuntimeError("No plan is available to revise.")
        validation = ctx.state.plan_validation or self.validator.validate(
            ctx.state.current_plan,
            analysis=self._load_analysis(ctx),
            requirements=ctx.requirements,
        )
        rewritten = self.rewriter.apply(
            ctx.state.current_plan,
            validation,
            analysis=self._load_analysis(ctx),
            requirements=ctx.requirements,
        )
        rewritten = self._apply_edit_requests(
            ctx,
            rewritten,
            requests=pending_edit_requests(ctx.state),
        )
        ctx.state.revision_attempts += 1
        provisional_render_spec = build_render_spec(
            rewritten,
            ctx.state.overlay_plan or {"overlays": [], "overlay_script": None},
            ctx.state.audio_plan or {},
            ctx.requirements,
        )
        apply_plan(
            ctx.state,
            rewritten,
            overlay_plan=ctx.state.overlay_plan,
            audio_plan=ctx.state.audio_plan,
            render_spec=provisional_render_spec,
            needs_validation=True,
        )
        clear_plan_validation(ctx.state)
        write_plan(ctx.dirs["job"], "timeline_plan.json", rewritten)
        write_plan(ctx.dirs["job"], "render_spec.json", provisional_render_spec)
        self._save(ctx)

    def _handle_render_preview(self, ctx: ExecutionContext, decision: PipelineDecision) -> None:
        self._ensure_render_gate(ctx, decision, action_name="render_preview")
        self._render(ctx, render_mode="preview")

    def _handle_render_final(self, ctx: ExecutionContext, decision: PipelineDecision) -> None:
        self._ensure_render_gate(ctx, decision, action_name="render_final")
        self._render(ctx, render_mode="final")

    def _handle_request_user_input(self, ctx: ExecutionContext, decision: PipelineDecision) -> None:
        question = str(
            decision.parameters.get("question")
            or decision.parameters.get("message")
            or decision.rationale
            or "More input is needed to continue."
        ).strip()
        request = {
            "reason": decision.parameters.get("reason") or "clarification_required",
            "question": question,
            "parameters": decision.parameters,
        }
        set_requested_user_input(ctx.state, request)
        self._save(ctx)

    def _handle_abort_job(self, ctx: ExecutionContext, decision: PipelineDecision) -> None:
        reason = str(decision.parameters.get("reason") or decision.rationale or "The job was aborted.").strip()
        mark_terminal(ctx.state, JobStatus.ABORTED, reason=reason)
        self._save(ctx)

    def _handle_finish(self, ctx: ExecutionContext, decision: PipelineDecision) -> None:
        self._ensure_render_gate(ctx, decision, action_name="finish")
        render_url = (ctx.state.final_response or {}).get("url") or (ctx.state.render_summary or {}).get("url")
        if not render_url:
            raise RuntimeError("Cannot finish a job before a render result exists.")
        final_response = self._build_success_response(ctx, status="done")
        mark_terminal(ctx.state, JobStatus.SUCCEEDED, final_response=final_response)
        self._save(ctx)

    def _render(self, ctx: ExecutionContext, *, render_mode: str) -> None:
        if not ctx.state.current_plan:
            raise RuntimeError("No plan is available to render.")
        ctx.state.render_attempts += 1
        touch(ctx.state)
        self._save(ctx)
        self._run_stage(ctx, StageName.RENDER_PLAN, lambda: self._stage_render_plan(ctx))
        self._run_stage(ctx, StageName.SHOTSTACK_RENDER, lambda: self._stage_render_provider(ctx))
        self._run_stage(ctx, StageName.POSTPROCESS, lambda: self._stage_postprocess(ctx))
        self._run_stage(ctx, StageName.PUBLISH, lambda: self._stage_publish(ctx))
        response_status = "preview_ready" if render_mode == "preview" else "rendered"
        response = self._build_success_response(ctx, status=response_status)
        summary = {
            "mode": render_mode,
            "status": response_status,
            "url": response.get("url"),
            "render_id": response.get("render_id"),
            "preview_url": response.get("preview_url"),
            "preview_mode": response.get("preview_mode"),
        }
        set_render_summary(ctx.state, summary, final_response=response if render_mode == "final" else None)
        self._save(ctx)

    def _run_stage(
        self,
        ctx: ExecutionContext,
        stage: StageName,
        fn: Callable[[], None],
        *,
        done_check: Optional[Callable[[], bool]] = None,
    ) -> None:
        if done_check and done_check():
            update_stage(ctx.state, stage, StageStatus.SKIPPED, {"reused": True})
            self._save(ctx)
            return
        update_stage(ctx.state, stage, StageStatus.RUNNING)
        self._save(ctx)
        try:
            fn()
            update_stage(ctx.state, stage, StageStatus.SUCCEEDED)
            self._save(ctx)
        except ProviderFailure as exc:
            add_error(ctx.state, stage, exc.code, exc.user_message, exc.to_error_detail())
            update_stage(
                ctx.state,
                stage,
                StageStatus.FAILED,
                {"code": exc.code, "provider": exc.provider, "retryable": exc.retryable},
            )
            self._save(ctx)
            raise
        except Exception as exc:
            add_error(ctx.state, stage, "STAGE_FAILED", str(exc), {"exception": repr(exc)})
            update_stage(ctx.state, stage, StageStatus.FAILED, {"exception": repr(exc)})
            self._save(ctx)
            raise

    def _stage_ingest(self, ctx: ExecutionContext) -> None:
        self._write_json(os.path.join(ctx.dirs["debug"], "request_payload.json"), ctx.request_payload)
        self._write_json(os.path.join(ctx.dirs["job"], "requirements.json"), ctx.requirements)
        ctx.state.user_goal = str(ctx.requirements.get("prompt", "") or "")
        ctx.state.work_dir = ctx.dirs["job"]
        touch(ctx.state)

    def _stage_fetch_primary(self, ctx: ExecutionContext) -> None:
        primary_path = download_video(ctx.request_payload["primary_url"], ctx.dirs["media"], "primary.mp4")
        ctx.artifacts.register_file(
            "primary.video",
            primary_path,
            {"source": ctx.request_payload["primary_url"]},
            "video/mp4",
        )

    def _stage_analyze_primary(self, ctx: ExecutionContext) -> None:
        primary = ctx.artifacts.get("primary.video")
        if primary is None:
            raise RuntimeError("Primary video is missing.")
        summary, analysis = analyze_video_content_with_results(primary.path_or_url)
        analysis_path = os.path.join(ctx.dirs["job"], "analysis.json")
        summary_path = os.path.join(ctx.dirs["job"], "analysis_summary.txt")
        self._write_json(analysis_path, analysis)
        with open(summary_path, "w", encoding="utf-8") as handle:
            handle.write(summary)
        ctx.artifacts.register_file("analysis.json", analysis_path, {}, "application/json")
        ctx.artifacts.register_file("analysis.summary", summary_path, {}, "text/plain")
        motion_effects = analysis.get("motion_effects")
        if motion_effects:
            manifest_path = os.path.join(ctx.dirs["job"], "motion_effects.json")
            self._write_json(manifest_path, motion_effects)
            ctx.artifacts.register_file("motion_effects.json", manifest_path, {}, "application/json")
            ctx.state.set_motion_effects_path(manifest_path)
        apply_analysis(ctx.state, analysis, summary)

    def _stage_fetch_sources(self, ctx: ExecutionContext) -> None:
        folder_id = ctx.request_payload.get("gdrive_folder_id")
        sources = ctx.request_payload.get("sources") or []
        generation_mode = normalize_generation_mode(
            ctx.requirements.get("generation_mode"),
            default=FREE_GENERATION_MODE,
        )

        if folder_id:
            from .storage import DriveStorageAdapter

            try:
                adapter = DriveStorageAdapter()
                assets = adapter.list_videos(folder_id)
            except Exception as exc:
                raise normalize_provider_exception(
                    "drive_storage",
                    exc,
                    operation="fetch_sources.drive",
                    config_message="Google Drive is not configured correctly for source loading.",
                    timeout_message="Google Drive took too long to respond while loading source videos.",
                    auth_message="Google Drive access is not authorized. Reconnect or fix the configured credentials.",
                    network_message="Google Drive is temporarily unavailable while loading source videos.",
                    default_message="Google Drive source loading failed.",
                ) from exc
            if not assets:
                raise RuntimeError("No video files found in provided Google Drive folder.")
            try:
                if generation_mode == REFERENCE_STYLE_TRANSFER_MODE:
                    for index, asset in enumerate(assets, start=1):
                        fetch_url = adapter.get_fetchable_url(asset)
                        ctx.artifacts.register_url(
                            f"sources.fetch.{index}",
                            fetch_url,
                            {"backend": "drive", "asset_id": asset.id, "trim_start": 0.0},
                            "video/mp4",
                        )
                else:
                    for index, asset in enumerate(assets, start=1):
                        dst = os.path.join(ctx.dirs["media"], f"source_raw_{index:03d}.mp4")
                        local = adapter.download(asset, dst)
                        ctx.artifacts.register_file(
                            f"sources.raw.{index}",
                            local,
                            {"backend": "drive", "asset_id": asset.id},
                            "video/mp4",
                        )
                        ctx.artifacts.register_url(
                            f"sources.fetch.{index}",
                            adapter.get_fetchable_url(asset),
                            {"backend": "drive", "asset_id": asset.id},
                            "video/mp4",
                        )
            except Exception as exc:
                raise normalize_provider_exception(
                    "drive_storage",
                    exc,
                    operation="fetch_sources.drive_transfer",
                    config_message="Google Drive is not configured correctly for source transfers.",
                    timeout_message="Google Drive timed out while transferring source videos.",
                    auth_message="Google Drive access is not authorized for source transfers.",
                    network_message="Google Drive is temporarily unavailable while transferring source videos.",
                    default_message="Google Drive source transfer failed.",
                ) from exc
            ctx.runtime["drive_adapter"] = adapter
            ctx.runtime["drive_folder_id"] = folder_id
            return

        if generation_mode == REFERENCE_STYLE_TRANSFER_MODE:
            if not sources:
                raise RuntimeError(
                    "Reference style transfer requires explicit source URLs when Drive folder is not provided."
                )
            for index, source in enumerate(sources, start=1):
                url = str(source.get("url", "")).strip()
                if not url:
                    raise RuntimeError(f"Source {index} is missing URL.")
                trim_start = _extract_start_override(source)
                if _is_direct_shotstack_source_url(url):
                    ctx.artifacts.register_url(
                        f"sources.fetch.{index}",
                        url,
                        {"backend": "url", "trim_start": trim_start},
                        "video/mp4",
                    )
                    continue
                segment_bounds = _extract_bounded_segment(source)
                if segment_bounds and ("youtube.com" in url.lower() or "youtu.be" in url.lower()):
                    local = download_video_section(
                        url=url,
                        output_dir=ctx.dirs["media"],
                        filename=f"source_raw_{index:03d}.mp4",
                        start_time=segment_bounds[0],
                        end_time=segment_bounds[1],
                    )
                    trim_start = 0.0
                else:
                    local = download_video(url, ctx.dirs["media"], f"source_raw_{index:03d}.mp4")
                meta = {
                    "backend": "url",
                    "source_url": url,
                    "trim_start": trim_start,
                    "clip_id": source.get("clip_id") or source.get("id") or source.get("label") or str(index),
                }
                ctx.artifacts.register_file(
                    f"sources.raw.{index}",
                    local,
                    meta,
                    "video/mp4",
                )
                ctx.artifacts.register_file(
                    f"sources.fetch.{index}",
                    local,
                    {**meta, "backend": "local"},
                    "video/mp4",
                )
            return

        clip_result = download_and_clip(sources, os.path.join(ctx.dirs["media"], "source_work"))
        if not clip_result.get("success"):
            raise RuntimeError(f"Clipping failed: {clip_result.get('error')}")
        clips = clip_result.get("clips") or []
        if not clips:
            raise RuntimeError("No source clips found.")
        for index, clip in enumerate(clips, start=1):
            path = clip["path"]
            source = sources[index - 1] if index - 1 < len(sources) else {}
            clip_id = source.get("clip_id") or source.get("id") or source.get("label") or str(index)
            meta = {"backend": "url", "clip_id": clip_id, "source_url": source.get("url")}
            ctx.artifacts.register_file(f"sources.raw.{index}", path, meta, "video/mp4")
            ctx.artifacts.register_file(f"sources.fetch.{index}", path, {**meta, "backend": "local"}, "video/mp4")

    def _stage_align_sources(self, ctx: ExecutionContext) -> None:
        analysis = self._load_analysis(ctx)
        scene_durations = [
            float(scene.get("duration", 0.0))
            for scene in (analysis.get("scenes") or [])
            if float(scene.get("duration", 0.0)) > 0
        ]
        raw_keys = _sorted_indexed_artifact_keys(ctx.artifacts.items, "sources.raw.")
        raw_paths = [ctx.artifacts.get(key).path_or_url for key in raw_keys if ctx.artifacts.get(key)]
        aligned_paths, notice = _align_sources(raw_paths, scene_durations, os.path.join(ctx.dirs["media"], "aligned"))
        if notice:
            add_warning(ctx.state, "SOURCE_DURATION_SHORT", notice)
            return
        if not aligned_paths:
            return
        for index, path in enumerate(aligned_paths, start=1):
            ctx.artifacts.register_file(f"sources.aligned.{index}", path, {"aligned": True}, "video/mp4")

        drive_adapter = ctx.runtime.get("drive_adapter")
        drive_folder = ctx.runtime.get("drive_folder_id")
        if drive_adapter and drive_folder:
            try:
                for index, path in enumerate(aligned_paths, start=1):
                    uploaded = drive_adapter.upload(path, drive_folder)
                    ctx.artifacts.register_url(
                        f"sources.fetch.{index}",
                        drive_adapter.get_fetchable_url(uploaded),
                        {"backend": "drive", "aligned": True, "asset_id": uploaded.id},
                        "video/mp4",
                    )
            except Exception as exc:
                add_warning(
                    ctx.state,
                    "DRIVE_UPLOAD_TIMEOUT",
                    "Aligned clip upload to Drive failed; using original Drive links.",
                    str(exc),
                )
        else:
            for index, path in enumerate(aligned_paths, start=1):
                ctx.artifacts.register_file(
                    f"sources.fetch.{index}",
                    path,
                    {"backend": "local", "aligned": True},
                    "video/mp4",
                )

    def _stage_audio_plan(self, ctx: ExecutionContext) -> None:
        soundtrack_url = None
        music_mode = ctx.requirements.get("music_mode", "original")
        custom_music_url = ctx.requirements.get("custom_music_url")
        music_segment = _extract_music_segment(ctx.requirements)
        use_reference_audio_bed = False
        mute_source_audio = False

        if music_mode == "custom" and custom_music_url:
            custom_video = None
            if music_segment:
                segment_start, segment_end = music_segment
                if segment_end is not None and _is_youtube_url(custom_music_url):
                    try:
                        custom_video = download_video_section(
                            url=custom_music_url,
                            output_dir=ctx.dirs["media"],
                            filename="custom_music_source.mp4",
                            start_time=float(segment_start),
                            end_time=float(segment_end),
                        )
                    except VideoDownloadError:
                        custom_video = None
                if custom_video:
                    soundtrack_file = extract_audio(custom_video, ctx.dirs["media"], "custom_music.mp3")
                else:
                    full_video = download_video(custom_music_url, ctx.dirs["media"], "custom_music_source.mp4")
                    soundtrack_file = extract_audio_segment(
                        full_video,
                        ctx.dirs["media"],
                        "custom_music.mp3",
                        start_time=segment_start,
                        end_time=segment_end,
                    )
            else:
                custom_video = download_video(custom_music_url, ctx.dirs["media"], "custom_music_source.mp4")
                soundtrack_file = extract_audio(custom_video, ctx.dirs["media"], "custom_music.mp3")
            ctx.artifacts.register_file("audio.soundtrack", soundtrack_file, {"mode": "custom"}, "audio/mpeg")
            soundtrack_url = soundtrack_file
        elif music_mode == "original" and normalize_generation_mode(
            ctx.requirements.get("generation_mode"),
            default=FREE_GENERATION_MODE,
        ) in {REFERENCE_STYLE_TRANSFER_MODE, VISION_TEMPLATE_LEARNING_MODE, REFERENCE_EDIT_AGENT_MODE}:
            primary = ctx.artifacts.get("primary.video")
            if primary is None:
                raise RuntimeError("Primary video is required to extract reference audio.")
            soundtrack_file = extract_audio(primary.path_or_url, ctx.dirs["media"], "reference_audio.mp3")
            ctx.artifacts.register_file(
                "audio.soundtrack",
                soundtrack_file,
                {"mode": "reference_primary"},
                "audio/mpeg",
            )
            soundtrack_url = soundtrack_file
            use_reference_audio_bed = True
            mute_source_audio = True

        audio_plan = build_audio_plan(
            {
                "soundtrack_url": soundtrack_url,
                "use_reference_audio_bed": use_reference_audio_bed,
                "mute_source_audio": mute_source_audio,
            },
            ctx.requirements,
        )
        ctx.state.audio_plan = audio_plan
        touch(ctx.state)
        write_plan(ctx.dirs["job"], "audio_plan.json", audio_plan)

    def _generate_plan_bundle(self, ctx: ExecutionContext) -> None:
        analysis = self._load_analysis(ctx)
        summary = ctx.state.analysis_summary
        source_durations = self._source_durations_for_plan(ctx, analysis)
        render_duration = float(sum(duration for duration in source_durations if duration > 0))
        analysis_duration = max(
            max((float(scene.get("end_time", 0.0)) for scene in (analysis.get("scenes") or [])), default=0.0),
            max((float(frame.get("timestamp", 0.0)) for frame in (analysis.get("keyframes") or [])), default=0.0),
        )
        source_keys = self._source_keys_for_generation(ctx)
        overlay_plan = build_overlay_plan(
            analysis,
            ctx.requirements,
            summary,
            render_duration=render_duration if render_duration > 0 else None,
            analysis_duration=analysis_duration if analysis_duration > 0 else None,
            montage_mode=bool(source_keys and len(source_keys) > 1),
        )
        timeline_plan = build_timeline_plan(
            analysis.get("scenes") or [],
            source_durations,
            ctx.requirements,
            analysis=analysis,
            include_validation=False,
            include_rewrite=False,
        )
        timeline_plan = self._apply_edit_requests(
            ctx,
            timeline_plan,
            requests=extract_edit_requests(ctx.requirements),
        )
        audio_plan = ctx.state.audio_plan or self._load_json_if_exists(
            os.path.join(ctx.dirs["plans"], "audio_plan.json")
        )
        provisional_render_spec = build_render_spec(timeline_plan, overlay_plan, audio_plan, ctx.requirements)
        postprocess_plan = build_postprocess_plan(ctx.requirements)

        apply_plan(
            ctx.state,
            timeline_plan,
            overlay_plan=overlay_plan,
            audio_plan=audio_plan,
            render_spec=provisional_render_spec,
            needs_validation=True,
        )
        ctx.state.render_summary = {}
        touch(ctx.state)

        self._write_plan_bundle(
            ctx,
            timeline_plan=timeline_plan,
            overlay_plan=overlay_plan,
            audio_plan=audio_plan,
            render_spec=provisional_render_spec,
            postprocess_plan=postprocess_plan,
            analysis_duration=analysis_duration,
            render_duration=render_duration,
        )
        self._record_overlay_warnings(ctx, overlay_plan)
        self._save(ctx)

    def _stage_vision_template_train(self, ctx: ExecutionContext) -> None:
        primary = ctx.artifacts.get("primary.video")
        if primary is None:
            add_error(
                ctx.state,
                StageName.VISION_TEMPLATE_TRAIN,
                "VISION_TEMPLATE_VIDEO_READ_FAILED",
                "Primary reference video is missing for vision template training.",
            )
            raise RuntimeError("Primary reference video is missing.")
        config = dict(ctx.requirements.get("vision_template") or {})
        expected_slots = ctx.requirements.get("expected_slots")
        set_controller_status(
            ctx.state,
            ControllerStatus.VISION_TEMPLATE_TRAINING,
            detail="Training experimental vision edit template from reference video.",
        )
        try:
            result = train_reference_adapter(
                reference_video_path=primary.path_or_url,
                out_dir=ctx.dirs["plans"],
                epochs=int(config.get("epochs", 5) or 5),
                fps=float(config.get("fps", 8.0) or 8.0),
                size=int(config.get("size", 224) or 224),
                device=str(config.get("device", "auto") or "auto"),
                max_seconds=config.get("max_seconds"),
                expected_slots=int(expected_slots) if expected_slots is not None else None,
                use_pretrained_backbone=bool(config.get("use_pretrained_backbone", False)),
                synthetic_pretrain=bool(config.get("synthetic_pretrain", False)),
                synthetic_pretrain_samples=int(config.get("synthetic_pretrain_samples", 16) or 16),
                synthetic_pretrain_epochs=int(config.get("synthetic_pretrain_epochs", 1) or 1),
            )
        except Exception as exc:
            add_error(
                ctx.state,
                StageName.VISION_TEMPLATE_TRAIN,
                "VISION_TEMPLATE_TRAINING_FAILED",
                str(exc),
            )
            raise

        ctx.artifacts.register_file("vision.template.model", result.model_path, {}, "application/octet-stream")
        ctx.artifacts.register_file("vision.template.json", result.template_path, {}, "application/json")
        ctx.artifacts.register_file("vision.template.raw_output", result.raw_output_path, {}, "application/octet-stream")
        ctx.artifacts.register_file(
            "vision.template.training_summary",
            result.training_summary_path,
            {},
            "application/json",
        )
        for warning in result.template.warnings:
            code = "VISION_TEMPLATE_LOW_CONFIDENCE" if "low confidence" in warning.lower() else "VISION_TEMPLATE_WARNING"
            add_warning(ctx.state, code, warning)
        self._maybe_attach_semantic_edit(ctx, result.template_path)
        update_stage(ctx.state, StageName.VISION_TEMPLATE_DECODE, StageStatus.SUCCEEDED, {"slot_count": len(result.template.slots)})
        self._save(ctx)

    def _maybe_attach_semantic_edit(self, ctx: ExecutionContext, template_path: str) -> None:
        semantic_config = dict(ctx.requirements.get("semantic_edit") or {})
        if not semantic_config.get("enabled", False):
            return
        primary = ctx.artifacts.get("primary.video")
        if primary is None:
            add_warning(
                ctx.state,
                "SEMANTIC_EDIT_ANALYSIS_FAILED",
                "Primary video missing; semantic analysis could not run.",
            )
            return
        try:
            sampled = sample_video_frames(
                primary.path_or_url,
                fps=float((ctx.requirements.get("vision_template") or {}).get("fps", 8.0) or 8.0),
                size=int((ctx.requirements.get("vision_template") or {}).get("size", 224) or 224),
                max_seconds=(ctx.requirements.get("vision_template") or {}).get("max_seconds"),
            )
            detections = detect_objects(
                sampled.frames,
                sampled.timestamps,
                text_queries=list(semantic_config.get("text_queries") or []),
                backend=str(semantic_config.get("backend", "auto") or "auto"),
            )
            if not detections and str(semantic_config.get("backend", "auto")) not in {"auto", "synthetic_color", "mock"}:
                add_warning(
                    ctx.state,
                    "SEMANTIC_EDIT_BACKEND_UNAVAILABLE",
                    "Requested semantic backend returned no detections; continuing without semantic attachment.",
                )
                return
            segment_objects(sampled.frames, detections, backend="bbox_mask")
            tracks = track_objects(detections, sampled.timestamps)
            layers = build_layer_stack(tracks)
            graph = build_semantic_video_graph(
                primary.path_or_url,
                sampled.frames,
                sampled.timestamps,
                detections,
                tracks,
                layers,
            )
            classify_semantic_edit_events(graph)
            if not tracks:
                graph.warnings.append("Semantic analysis produced no tracked objects.")
                add_warning(
                    ctx.state,
                    "SEMANTIC_EDIT_LOW_CONFIDENCE",
                    "Semantic analysis produced no tracked objects.",
                )
            graph_path = os.path.join(ctx.dirs["plans"], "semantic_video_graph.json")
            graph.to_json_file(graph_path)
            ctx.artifacts.register_file("semantic.video_graph", graph_path, {}, "application/json")
            if semantic_config.get("attach_to_template", True):
                template = EditTemplate.from_json_file(template_path)
                attach_semantic_graph_to_template(template, graph)
                template.to_json_file(template_path)
                ctx.artifacts.register_file("vision.template.json", template_path, {"semantic_attached": True}, "application/json")
        except Exception as exc:
            add_warning(
                ctx.state,
                "SEMANTIC_EDIT_ANALYSIS_FAILED",
                f"Semantic analysis failed but the pipeline continued: {exc}",
                {"exception": repr(exc)},
            )

    def _resolve_slot_mapping(self, ctx: ExecutionContext) -> SlotMapping:
        payload = (
            ctx.request_payload.get("slot_mapping")
            or ctx.requirements.get("slot_mapping")
            or (ctx.requirements.get("vision_template") or {}).get("slot_mapping")
        )
        if not payload:
            add_error(
                ctx.state,
                StageName.VISION_TEMPLATE_TRANSFER,
                "VISION_TEMPLATE_SLOT_MAPPING_MISSING",
                "vision_template_learning requires slot_mapping.",
            )
            raise RuntimeError("vision_template_learning requires slot_mapping.")
        normalized = {"items": payload} if isinstance(payload, list) else payload
        if hasattr(SlotMapping, "model_validate"):
            return SlotMapping.model_validate(normalized)
        return SlotMapping.parse_obj(normalized)

    def _source_artifacts_by_clip_id(self, ctx: ExecutionContext) -> Dict[str, Any]:
        source_map: Dict[str, Any] = {}
        for index, source in enumerate(ctx.request_payload.get("sources") or [], start=1):
            clip_id = source.get("clip_id") or source.get("id") or source.get("label") or str(index)
            artifact = (
                ctx.artifacts.get(f"sources.aligned.{index}")
                or ctx.artifacts.get(f"sources.raw.{index}")
                or ctx.artifacts.get(f"sources.fetch.{index}")
            )
            if artifact is not None:
                source_map[str(clip_id)] = artifact
        return source_map

    def _stage_vision_template_transfer(self, ctx: ExecutionContext) -> None:
        template_artifact = ctx.artifacts.get("vision.template.json")
        if template_artifact is None:
            add_error(
                ctx.state,
                StageName.VISION_TEMPLATE_TRANSFER,
                "VISION_TEMPLATE_DECODE_FAILED",
                "Missing decoded vision template artifact.",
            )
            raise RuntimeError("Missing decoded vision template artifact.")
        set_controller_status(
            ctx.state,
            ControllerStatus.VISION_TEMPLATE_TRANSFERRING,
            detail="Transferring learned edit template onto replacement clips.",
        )
        template = EditTemplate.from_json_file(template_artifact.path_or_url)
        slot_mapping = self._resolve_slot_mapping(ctx)
        source_artifacts = self._source_artifacts_by_clip_id(ctx)
        try:
            canonical_timeline, overlay_timing, edit_summary = build_render_spec_from_vision_template(
                template,
                slot_mapping,
                source_artifacts,
                ctx.requirements,
                existing_overlay_plan=ctx.state.overlay_plan or None,
                existing_audio_plan=ctx.state.audio_plan or None,
            )
        except Exception as exc:
            add_error(
                ctx.state,
                StageName.VISION_TEMPLATE_TRANSFER,
                "VISION_TEMPLATE_TRANSFER_FAILED",
                str(exc),
            )
            raise

        timeline_plan = {
            "planning_strategy": "vision_template_learning",
            "target_pacing": template.global_style.pacing_label,
            "target_segment_duration": template.global_style.avg_slot_duration,
            "target_segment_count": len(template.slots),
            "selected_segments": [],
            "support_segments": [],
            "rejected_segments": [],
            "scene_durations": [slot.duration for slot in template.slots],
            "source_durations": [],
            "edit_directives": [],
            "plan_validation": {
                "validation_score": 1.0,
                "checks": {"vision_template": True},
                "warnings": [],
                "recommendations": [],
                "rewrite_actions": [],
                "validator_strategy": "vision_template_learning",
            },
            "planning_debug": {
                "strategy_label": "vision_template_learning",
                "vision_template_slot_count": len(template.slots),
                "validation_ran": True,
                "validator_strategy": "vision_template_learning",
                "rewrite_applied": False,
                "rewrite_actions_applied": [],
            },
        }
        overlay_plan = {
            "overlays": overlay_timing.get("overlays", []),
            "text_segments": [],
            "warnings": [],
            "overlay_script": None,
            "timing_mode": "vision_template",
            "montage_mode": False,
        }
        audio_plan = ctx.state.audio_plan or {}
        render_spec = build_render_spec(timeline_plan, overlay_plan, audio_plan, ctx.requirements)
        render_spec["canonical_timeline"] = canonical_timeline
        render_spec["overlay_timing"] = overlay_timing.get("overlays", [])
        render_spec["edit_summary"] = edit_summary
        render_spec["generation_mode"] = "vision_template_learning"
        render_spec["vision_template_path"] = template_artifact.path_or_url
        apply_plan(
            ctx.state,
            timeline_plan,
            overlay_plan=overlay_plan,
            audio_plan=audio_plan,
            render_spec=render_spec,
            needs_validation=False,
        )
        apply_plan_validation(ctx.state, timeline_plan["plan_validation"])
        self._write_plan_bundle(
            ctx,
            timeline_plan=timeline_plan,
            overlay_plan=overlay_plan,
            audio_plan=audio_plan,
            render_spec=render_spec,
            postprocess_plan=build_postprocess_plan(ctx.requirements),
            analysis_duration=float(template.total_duration),
            render_duration=float(template.total_duration),
        )
        write_plan(ctx.dirs["job"], "vision_template.json", template.model_dump() if hasattr(template, "model_dump") else template.dict())
        write_plan(
            ctx.dirs["job"],
            "vision_template_timeline.json",
            {"generation_mode": "vision_template_learning", "timeline": canonical_timeline},
        )
        self._save(ctx)

    def _stage_render_plan(self, ctx: ExecutionContext) -> None:
        if not ctx.state.current_plan:
            raise RuntimeError("No plan is available to render.")

        generation_mode = normalize_generation_mode(
            ctx.requirements.get("generation_mode"),
            default=FREE_GENERATION_MODE,
        )
        if generation_mode == REFERENCE_EDIT_AGENT_MODE:
            render_spec = ctx.state.render_spec or self._load_json_if_exists(os.path.join(ctx.dirs["plans"], "render_spec.json"))
            if not render_spec.get("canonical_timeline"):
                raise RuntimeError("reference_edit_agent requires a canonical_timeline before rendering.")
            if (ctx.state.plan_validation or {}).get("validator_strategy") != "edit_graph_validator":
                raise RuntimeError("reference_edit_agent requires a validated edit graph before rendering.")
            
            canonical_timeline = render_spec.get("canonical_timeline") or []
            total_duration = float(sum(row.get("duration", 0.0) for row in canonical_timeline))
            
            render_spec = self._apply_motion_effects_to_render_spec(ctx, render_spec)
            ctx.state.render_spec = render_spec
            touch(ctx.state)
            
            self._write_plan_bundle(
                ctx,
                timeline_plan=ctx.state.current_plan,
                overlay_plan=ctx.state.overlay_plan or {"overlays": [], "text_segments": [], "warnings": [], "overlay_script": None},
                audio_plan=ctx.state.audio_plan or {},
                render_spec=render_spec,
                postprocess_plan=build_postprocess_plan(ctx.requirements),
                analysis_duration=total_duration,
                render_duration=total_duration,
            )
            return

        if generation_mode == VISION_TEMPLATE_LEARNING_MODE:
            render_spec = ctx.state.render_spec or self._load_json_if_exists(os.path.join(ctx.dirs["plans"], "render_spec.json"))
            if not render_spec.get("canonical_timeline"):
                raise RuntimeError("vision_template_learning requires a canonical_timeline before rendering.")
            render_spec = self._apply_motion_effects_to_render_spec(ctx, render_spec)
            ctx.state.render_spec = render_spec
            touch(ctx.state)
            self._write_plan_bundle(
                ctx,
                timeline_plan=ctx.state.current_plan,
                overlay_plan=ctx.state.overlay_plan or {"overlays": [], "text_segments": [], "warnings": [], "overlay_script": None},
                audio_plan=ctx.state.audio_plan or {},
                render_spec=render_spec,
                postprocess_plan=build_postprocess_plan(ctx.requirements),
                analysis_duration=float(render_spec.get("edit_summary", {}).get("preserved_total_duration", 0.0) or 0.0),
                render_duration=float(render_spec.get("edit_summary", {}).get("preserved_total_duration", 0.0) or 0.0),
            )
            return

        analysis = self._load_analysis(ctx)
        overlay_plan = ctx.state.overlay_plan
        audio_plan = ctx.state.audio_plan
        if not overlay_plan:
            self._generate_plan_bundle(ctx)
            overlay_plan = ctx.state.overlay_plan
        if not audio_plan:
            self._stage_audio_plan(ctx)
            audio_plan = ctx.state.audio_plan

        render_spec = build_render_spec(ctx.state.current_plan, overlay_plan, audio_plan, ctx.requirements)
        postprocess_plan = build_postprocess_plan(ctx.requirements)
        generation_mode = normalize_generation_mode(
            ctx.requirements.get("generation_mode"),
            default=FREE_GENERATION_MODE,
        )
        edit_mode = str(ctx.requirements.get("edit_mode", "scene")).lower().strip()
        if edit_mode not in {"scene", "ocr"}:
            edit_mode = "scene"

        source_keys = self._source_keys_for_generation(ctx)
        render_duration = float(
            sum(duration for duration in self._source_durations_for_plan(ctx, analysis) if duration > 0)
        )
        analysis_duration = max(
            max((float(scene.get("end_time", 0.0)) for scene in (analysis.get("scenes") or [])), default=0.0),
            max((float(frame.get("timestamp", 0.0)) for frame in (analysis.get("keyframes") or [])), default=0.0),
        )

        if edit_mode == "ocr":
            canonical_timeline, overlay_timing, edit_summary, edit_ops = self._build_ocr_render_timeline(
                ctx,
                analysis,
                overlay_plan,
                generation_mode,
            )
            render_spec["canonical_timeline"] = canonical_timeline
            render_spec["overlay_timing"] = overlay_timing
            if edit_summary:
                render_spec["edit_summary"] = edit_summary
                render_spec["edit_ops"] = edit_ops
        elif generation_mode == REFERENCE_STYLE_TRANSFER_MODE:
            canonical_timeline, overlay_timing, edit_summary, edit_ops = self._build_reference_render_timeline(
                ctx,
                analysis,
                overlay_plan,
                audio_plan,
                source_keys,
            )
            render_spec["canonical_timeline"] = canonical_timeline
            render_spec["overlay_timing"] = overlay_timing
            if edit_summary:
                render_spec["edit_summary"] = edit_summary
                render_spec["edit_ops"] = edit_ops

        render_spec = self._apply_motion_effects_to_render_spec(ctx, render_spec)
        filter_plan = self._build_render_filter_plan(render_spec)
        _write_render_filter_plan(ctx.dirs["debug"], filter_plan)
        ctx.state.render_spec = render_spec
        touch(ctx.state)
        self._write_plan_bundle(
            ctx,
            timeline_plan=ctx.state.current_plan,
            overlay_plan=overlay_plan,
            audio_plan=audio_plan,
            render_spec=render_spec,
            postprocess_plan=postprocess_plan,
            analysis_duration=analysis_duration,
            render_duration=render_duration,
        )
        self._record_overlay_warnings(ctx, overlay_plan)

    def _build_ocr_render_timeline(
        self,
        ctx: ExecutionContext,
        analysis: Dict[str, Any],
        overlay_plan: Dict[str, Any],
        generation_mode: str,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        source_keys = _sorted_indexed_artifact_keys(ctx.artifacts.items, "sources.fetch.")
        if not source_keys:
            source_keys = self._source_keys_for_generation(ctx)
        if not source_keys:
            raise RuntimeError("OCR mode requires at least one source clip.")

        source_rows = []
        for index, key in enumerate(source_keys, start=1):
            art = ctx.artifacts.get(key)
            if art is None:
                continue
            meta = art.meta or {}
            trim_start = float(meta.get("trim_start", 0.0) or 0.0)
            if generation_mode == REFERENCE_STYLE_TRANSFER_MODE:
                trim_start = 0.0
            probe_src = art.path_or_url
            raw_art = ctx.artifacts.get(f"sources.raw.{index}")
            if raw_art and raw_art.type == "file" and os.path.exists(raw_art.path_or_url):
                probe_src = raw_art.path_or_url
            source_rows.append(
                {"index": index, "video_src": art.path_or_url, "probe_src": probe_src, "trim": trim_start}
            )

        ocr_segments = overlay_plan.get("text_segments") or []
        canonical_timeline = _build_ocr_timeline(
            text_segments=ocr_segments,
            sources=source_rows,
            strict_index_alignment=(generation_mode == REFERENCE_STYLE_TRANSFER_MODE),
        )
        edit_ops = _parse_edit_ops(ctx.requirements)
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
        skip_validation = bool(
            edit_summary and (edit_summary.get("timing_changed") or edit_summary.get("count_changed"))
        )
        if not skip_validation:
            errors = _validate_ocr_timeline(
                text_segments=ocr_segments,
                timeline=canonical_timeline,
                overlay_timing=overlay_timing,
            )
            if errors:
                raise RuntimeError("OCR timing validation failed:\n" + "\n".join(errors))
        return canonical_timeline, overlay_timing, edit_summary, edit_ops

    def _build_reference_render_timeline(
        self,
        ctx: ExecutionContext,
        analysis: Dict[str, Any],
        overlay_plan: Dict[str, Any],
        audio_plan: Dict[str, Any],
        source_keys: List[str],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        source_rows = []
        for index, key in enumerate(source_keys, start=1):
            art = ctx.artifacts.get(key)
            if art is None:
                continue
            probe_src = art.path_or_url
            raw_art = ctx.artifacts.get(f"sources.raw.{index}")
            if raw_art and raw_art.type == "file" and os.path.exists(raw_art.path_or_url):
                probe_src = raw_art.path_or_url
            source_rows.append(
                {"index": index, "video_src": art.path_or_url, "probe_src": probe_src, "trim": 0.0}
            )

        canonical_timeline = _build_reference_timeline(analysis=analysis, sources=source_rows)

        # Do not auto-render OCR/overlay script text; only user-confirmed overlays render.
        text_overlays = ctx.requirements.get("text_overlays") or []
        if text_overlays:
            _apply_confirmed_text_overlays_to_timeline(canonical_timeline, text_overlays)

        edit_ops = _parse_edit_ops(ctx.requirements)
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
            soundtrack_artifact = ctx.artifacts.get("audio.soundtrack")
            if soundtrack_artifact is not None:
                reference_audio_duration = _probe_duration(soundtrack_artifact.path_or_url)
        skip_validation = bool(
            edit_summary and (edit_summary.get("timing_changed") or edit_summary.get("count_changed"))
        )
        if not skip_validation:
            errors = _validate_reference_timeline(
                analysis=analysis,
                timeline=canonical_timeline,
                overlay_timing=overlay_timing,
                use_reference_audio=bool(audio_plan.get("use_reference_audio_bed")),
                reference_audio_duration=reference_audio_duration,
            )
            if errors:
                raise RuntimeError("Reference style transfer validation failed:\n" + "\n".join(errors))
        return canonical_timeline, overlay_timing, edit_summary, edit_ops

    def _stage_render_provider(self, ctx: ExecutionContext) -> None:
        """Render video using configured provider (FFmpeg or Shotstack)."""
        render_provider = str(os.getenv("RENDER_PROVIDER", "ffmpeg")).strip().lower()
        
        if render_provider == "ffmpeg":
            return self._stage_ffmpeg_render(ctx)
        elif render_provider == "shotstack":
            return self._stage_shotstack_render(ctx)
        else:
            raise ProviderFailure(
                provider="render_provider",
                code="INVALID_RENDER_PROVIDER",
                user_message=f"Invalid RENDER_PROVIDER: {render_provider}. Supported: ffmpeg, shotstack",
                detail={"env_value": render_provider},
                retryable=False,
            )

    def _stage_ffmpeg_render(self, ctx: ExecutionContext) -> None:
        """Render video locally using FFmpeg."""
        from ai_editor.renderers import FFmpegRenderer

        spec = ctx.state.render_spec or self._load_json_if_exists(os.path.join(ctx.dirs["plans"], "render_spec.json"))
        if not spec or not spec.get("canonical_timeline"):
            raise ProviderFailure(
                provider="render_provider",
                code="RENDER_SPEC_MISSING",
                user_message="Rendering requires canonical_timeline in render_spec.",
                detail={"has_render_spec": bool(spec), "has_canonical_timeline": bool(spec and spec.get("canonical_timeline"))},
                retryable=False,
            )

        try:
            renderer = FFmpegRenderer()
            result = renderer.render(
                render_spec=spec,
                job_id=ctx.job_id,
                job_dir=ctx.dirs["job"],
            )
        except Exception as exc:
            raise normalize_provider_exception(
                "render_provider",
                exc,
                operation="ffmpeg_render.render",
                config_message="The FFmpeg renderer is not configured correctly.",
                timeout_message="The FFmpeg render operation timed out.",
                auth_message="The FFmpeg render operation failed (not applicable).",
                network_message="The FFmpeg render operation failed.",
                default_message="The FFmpeg render operation failed.",
            ) from exc

        if not result.get("success"):
            raise ProviderFailure(
                provider="render_provider",
                code="FFMPEG_RENDER_FAILED",
                user_message=result.get("error", "FFmpeg render failed."),
                detail={
                    "error": result.get("error"),
                    "debug_info": result.get("debug_info"),
                },
                retryable=False,
            )

        # Register output artifacts
        output_path = result.get("output_path")
        if output_path and os.path.exists(output_path):
            ctx.artifacts.register_file(
                "render.master_16x9",
                output_path,
                {"render_id": result.get("render_id"), "provider": "ffmpeg"},
                "video/mp4",
            )

        # Register preview URL
        ctx.artifacts.register_url(
            "render.ffmpeg_url",
            result.get("url", ""),
            {"render_id": result.get("render_id"), "provider": "ffmpeg"},
            "video/mp4",
        )

        ctx.artifacts.register_url(
            "render.output_url",
            result.get("url", ""),
            {"render_id": result.get("render_id"), "provider": "ffmpeg"},
            "video/mp4",
        )

        ctx.runtime["render_result"] = result

    def _stage_shotstack_render(self, ctx: ExecutionContext) -> None:
        from ai_editor.shotstack_renderer import create_and_render_video

        shotstack_key = str(os.getenv("SHOTSTACK_KEY", "") or "").strip()
        if not shotstack_key:
            raise ProviderFailure(
                provider="render_provider",
                code="RENDER_PROVIDER_NOT_CONFIGURED",
                user_message="Rendering is not configured. Set SHOTSTACK_KEY before running final renders.",
                detail={"env_key": "SHOTSTACK_KEY"},
                retryable=False,
            )

        spec = ctx.state.render_spec or self._load_json_if_exists(os.path.join(ctx.dirs["plans"], "render_spec.json"))
        canonical_timeline = spec.get("canonical_timeline") or []
        edit_summary = spec.get("edit_summary") or {}
        generation_mode = normalize_generation_mode(
            spec.get("generation_mode", ctx.requirements.get("generation_mode", FREE_GENERATION_MODE)),
            default=FREE_GENERATION_MODE,
        )
        edit_mode = str(spec.get("edit_mode", ctx.requirements.get("edit_mode", "scene"))).lower().strip()
        if edit_mode not in {"scene", "ocr"}:
            edit_mode = "scene"
        if generation_mode == REFERENCE_STYLE_TRANSFER_MODE and edit_mode == "scene" and not canonical_timeline:
            raise RuntimeError(
                "reference_style_transfer requires canonical_timeline in render_spec; refusing non-canonical render."
            )
        if edit_mode == "ocr" and not canonical_timeline:
            raise RuntimeError("OCR mode requires canonical_timeline in render_spec; refusing scene-timed fallback.")

        fetch_entries = []
        if canonical_timeline:
            for index, row in enumerate(canonical_timeline, start=1):
                fetch_entries.append(
                    {"key": f"timeline.scene.{index}", "path": row.get("video_src"), "meta": {"timeline": True}}
                )
        else:
            fetch_keys = _sorted_indexed_artifact_keys(ctx.artifacts.items, "sources.fetch.")
            if not fetch_keys:
                raise RuntimeError("No fetchable sources available for rendering.")
            for key in fetch_keys:
                art = ctx.artifacts.get(key)
                if art is None:
                    continue
                fetch_entries.append({"key": key, "path": art.path_or_url, "meta": art.meta or {}})

        local_uploads = [
            os.path.normpath(entry["path"])
            for entry in fetch_entries
            if entry["path"] and not _is_http_url(entry["path"])
        ]
        shotstack_links = _upload_assets_for_shotstack(ctx.job_id, local_uploads) if local_uploads else []
        links_path = os.path.join(ctx.dirs["plans"], "shotstack_asset_links.json")
        self._write_json(links_path, shotstack_links)
        ctx.artifacts.register_file(
            "sources.aligned.drive_links",
            links_path,
            {"uploaded": bool(shotstack_links)},
            "application/json",
        )
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
                        {
                            "backend": "drive",
                            **({"aligned": entry["meta"].get("aligned")} if entry["meta"].get("aligned") else {}),
                        },
                        "video/mp4",
                    )
            entry["public_url"] = public_url
        video_urls = [entry["public_url"] for entry in fetch_entries if entry["public_url"]]

        if canonical_timeline:
            for index, row in enumerate(canonical_timeline):
                local_src = os.path.normpath(str(row.get("video_src", "")))
                if local_src in upload_map:
                    canonical_timeline[index]["video_src"] = upload_map[local_src]["public_url"]
                elif _is_http_url(row.get("video_src")):
                    canonical_timeline[index]["video_src"] = row.get("video_src")
                else:
                    raise RuntimeError(f"Canonical timeline source is not fetchable: {row.get('video_src')}")

            analysis = self._load_analysis(ctx)
            analyzed_scenes = analysis.get("scenes") or []
            if (
                generation_mode == REFERENCE_STYLE_TRANSFER_MODE
                and edit_mode == "scene"
                and len(canonical_timeline) != len(analyzed_scenes)
                and not (edit_summary.get("count_changed") or edit_summary.get("timing_changed"))
            ):
                raise RuntimeError(
                    f"reference_style_transfer clip-count mismatch: canonical={len(canonical_timeline)} analyzed={len(analyzed_scenes)}"
                )

        probe_keys = _sorted_indexed_artifact_keys(ctx.artifacts.items, "sources.aligned.")
        if not probe_keys:
            probe_keys = _sorted_indexed_artifact_keys(ctx.artifacts.items, "sources.raw.")
        duration_probe_urls = None if canonical_timeline else [
            ctx.artifacts.get(key).path_or_url for key in probe_keys if ctx.artifacts.get(key)
        ]

        for index, url in enumerate(video_urls, start=1):
            if not _is_http_url(url):
                raise RuntimeError(f"Shotstack asset URL invalid: {url} (entry {index})")

        soundtrack_url = spec.get("soundtrack_url")
        if soundtrack_url and not _is_http_url(soundtrack_url):
            uploads = _upload_assets_for_shotstack(ctx.job_id, [soundtrack_url])
            if not uploads:
                raise RuntimeError("Failed to upload local soundtrack for Shotstack.")
            soundtrack_url = uploads[0]["public_url"]
            spec["soundtrack_url"] = soundtrack_url
            ctx.state.render_spec = spec

        shotstack_payload_path = os.path.join(ctx.dirs["plans"], "shotstack_request_payload.json")
        shotstack_debug_path = os.path.join(ctx.dirs["debug"], "shotstack_error.json")

        try:
            render_result = create_and_render_video(
                api_key=shotstack_key,
                video_urls=video_urls,
                duration_probe_urls=duration_probe_urls,
                project_title=f"Auto-Edit ({ctx.job_id})",
                overlay_text=[ctx.requirements.get("prompt", "")[:50]],
                soundtrack_url=soundtrack_url,
                music_mode=spec.get("music_mode", "original"),
                resolution=spec.get("resolution", "1080x1920"),
                wait_for_render=True,
                overlay_plan=spec.get("overlay_plan") or None,
                overlay_timing=spec.get("overlay_timing") or None,
                overlay_script=spec.get("overlay_script") or None,
                timing_mode=str(spec.get("timing_mode", "ocr_keyframe")),
                generation_mode=normalize_generation_mode(
                    spec.get("generation_mode", ctx.requirements.get("generation_mode", FREE_GENERATION_MODE)),
                    default=FREE_GENERATION_MODE,
                ),
                canonical_timeline=canonical_timeline or None,
                force_mobile_safe_text=bool(spec.get("force_mobile_safe_text")),
                mobile_safe_text_mode=bool(spec.get("mobile_safe_text_mode", False)),
                caption_density_mode=str(spec.get("caption_density_mode", "normal")),
                caption_style_preset=str(spec.get("caption_style_preset", "default")),
                overlay_density_cap=spec.get("overlay_density_cap"),
                text_placement_policy=str(spec.get("text_placement_policy", "default")),
                text_readability_mode=str(spec.get("text_readability_mode", "balanced")),
                overlay_full_clip=bool(spec.get("overlay_full_clip")),
                mute_source_audio=bool(spec.get("mute_source_audio", False)),
                disable_auto_transitions=bool(spec.get("disable_auto_transitions", False)),
                refit_mode=str(spec.get("refit_mode", ctx.requirements.get("refit_mode", "crop_center"))),
                output_mode=str(spec.get("output_mode", ctx.requirements.get("output_mode", "crop_to_9x16"))),
                debug_text_visibility=bool(ctx.requirements.get("debug_text_visibility", False)),
                debug_render_spec_path=os.path.join(ctx.dirs["plans"], "render_spec.json"),
                debug_overlay_timing_path=os.path.join(ctx.dirs["plans"], "overlay_timing.json"),
                debug_shotstack_payload_path=shotstack_payload_path,
                debug_shotstack_error_path=shotstack_debug_path,
            )
        except Exception as exc:
            if not os.path.exists(shotstack_debug_path):
                _write_debug_json(
                    shotstack_debug_path,
                    {
                        "stage": "shotstack_create",
                        "status_code": None,
                        "response_text": None,
                        "response_json": None,
                        "error": "The render provider failed while creating the video render.",
                        "exception": repr(exc),
                        "render_id": None,
                        "request_url": f"{os.getenv('SHOTSTACK_HOST', 'https://api.shotstack.io/stage').strip() or 'https://api.shotstack.io/stage'}/render",
                        "payload_path": shotstack_payload_path,
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    },
                )
            failure = normalize_provider_exception(
                "render_provider",
                exc,
                operation="shotstack_render.create_and_render_video",
                config_message="The render provider is not configured correctly.",
                timeout_message="The render provider timed out while producing the video.",
                auth_message="The render provider rejected authentication. Check SHOTSTACK_KEY.",
                network_message="The render provider is temporarily unavailable.",
                default_message="The render provider failed while creating the video render.",
            )
            detail = dict(failure.detail or {})
            detail.update(
                {
                    "failure_code": failure.code,
                    "provider": failure.provider,
                    "retryable": failure.retryable,
                    "operation": "shotstack_render.create_and_render_video",
                    "shotstack_debug_path": shotstack_debug_path,
                    "short_error_message": failure.user_message,
                }
            )
            raise ProviderFailure(
                provider=failure.provider,
                code=failure.code,
                user_message=failure.user_message,
                detail=detail,
                retryable=failure.retryable,
            ) from exc
        if not render_result.get("success"):
            error_detail = dict(render_result.get("debug") or render_result.get("error_detail") or {})
            if render_result.get("status"):
                error_detail.setdefault("status", render_result.get("status"))
            if render_result.get("render_id"):
                error_detail.setdefault("render_id", render_result.get("render_id"))
            if render_result.get("error"):
                error_detail.setdefault("message", render_result.get("error"))
            _write_debug_json(shotstack_debug_path, error_detail or {"message": "Unknown Shotstack render failure."})
            ctx.artifacts.register_file(
                "debug.shotstack_error",
                shotstack_debug_path,
                {"render_id": render_result.get("render_id")},
                "application/json",
            )
            error_detail.update(
                {
                    "failure_code": "RENDER_PROVIDER_FAILED",
                    "provider": "render_provider",
                    "retryable": bool(render_result.get("status") == "timeout"),
                    "operation": "shotstack_render.create_and_render_video",
                    "shotstack_debug_path": shotstack_debug_path,
                    "short_error_message": str(
                        render_result.get("error") or "The render provider failed while creating the video render."
                    ),
                }
            )
            raise ProviderFailure(
                provider="render_provider",
                code="RENDER_PROVIDER_FAILED",
                user_message=str(render_result.get("error") or "The render provider failed while creating the video render."),
                detail=error_detail or {"shotstack_debug_path": shotstack_debug_path},
                retryable=bool(render_result.get("status") == "timeout"),
            )
        if not render_result.get("success") or not render_result.get("url"):
            raise RuntimeError(f"Render failed: {render_result.get('error') or 'No output URL returned.'}")

        master_path = os.path.join(ctx.dirs["outputs"], "master_16x9.mp4")
        try:
            _download_file(render_result["url"], master_path)
        except Exception as exc:
            raise normalize_provider_exception(
                "render_provider",
                exc,
                operation="shotstack_render.download_result",
                config_message="The render output could not be downloaded because the render provider is misconfigured.",
                timeout_message="Downloading the render output timed out.",
                auth_message="The render output could not be downloaded due to authorization failure.",
                network_message="The render output is temporarily unavailable for download.",
                default_message="Downloading the render output failed.",
            ) from exc
        ctx.artifacts.register_file(
            "render.master_16x9",
            master_path,
            {"render_id": render_result.get("render_id")},
            "video/mp4",
        )
        ctx.artifacts.register_url(
            "render.shotstack_url",
            render_result["url"],
            {"render_id": render_result.get("render_id")},
            "video/mp4",
        )
        ctx.runtime["render_result"] = render_result

    def _stage_postprocess(self, ctx: ExecutionContext) -> None:
        plan = self._load_json_if_exists(os.path.join(ctx.dirs["plans"], "postprocess_plan.json"))
        if not plan.get("create_shorts"):
            update_stage(ctx.state, StageName.POSTPROCESS, StageStatus.SKIPPED, {"reason": "intent_mode=video"})
            self._save(ctx)
            return
        master = ctx.artifacts.get("render.master_16x9")
        if master is None:
            raise RuntimeError("Rendered master video is missing.")
        short_path = os.path.join(ctx.dirs["outputs"], "short_9x16.mp4")
        try:
            _run_shorts_refit(master.path_or_url, short_path, plan.get("refit_mode", "crop_center"))
            ctx.artifacts.register_file(
                "render.short_9x16",
                short_path,
                {"refit_mode": plan.get("refit_mode", "crop_center")},
                "video/mp4",
            )
        except Exception as exc:
            add_warning(
                ctx.state,
                "FFMPEG_POSTPROCESS_FAILED",
                "Shorts conversion failed; using master preview fallback.",
                str(exc),
            )

    def _stage_publish(self, ctx: ExecutionContext) -> None:
        plan = self._load_json_if_exists(os.path.join(ctx.dirs["plans"], "postprocess_plan.json"))
        create_shorts = bool(plan.get("create_shorts"))
        if create_shorts and _artifact_path_exists(ctx.artifacts, "render.short_9x16"):
            preview_mode = "shorts"
            preview_name = "short_9x16.mp4"
        else:
            preview_mode = "video"
            preview_name = "master_16x9.mp4"
        ctx.runtime["preview_url"] = f"/files/{ctx.job_id}/outputs/{preview_name}"
        ctx.runtime["preview_mode"] = preview_mode

    def _stage_build_reference_template(self, ctx: ExecutionContext) -> None:
        analysis = self._load_analysis(ctx)
        primary = ctx.artifacts.get("primary.video")
        if primary is None:
            raise RuntimeError("Primary reference video artifact is missing.")
        
        template = build_reference_edit_template(
            analysis,
            primary.path_or_url,
            ctx.job_id,
            ctx.requirements,
        )
        
        template_path = os.path.join(ctx.dirs["plans"], "reference_edit_template.json")
        self._write_json(template_path, template)
        ctx.artifacts.register_file("reference.edit_template", template_path, {}, "application/json")
        self._save(ctx)

    def _stage_analyze_source_inventory(self, ctx: ExecutionContext) -> None:
        raw_keys = _sorted_indexed_artifact_keys(ctx.artifacts.items, "sources.raw.")
        fetch_keys = _sorted_indexed_artifact_keys(ctx.artifacts.items, "sources.fetch.")
        
        source_artifacts = []
        for index in range(1, max(len(raw_keys), len(fetch_keys)) + 1):
            art = ctx.artifacts.get(f"sources.raw.{index}") or ctx.artifacts.get(f"sources.fetch.{index}")
            if art is not None:
                clip_id = art.meta.get("clip_id") or str(index)
                source_artifacts.append({
                    "source_index": index,
                    "clip_id": clip_id,
                    "path": art.path_or_url,
                })
        
        inventory = build_source_inventory(
            source_artifacts,
            ctx.job_id,
            ctx.dirs["plans"],
            lightweight=True,
        )
        
        inventory_path = os.path.join(ctx.dirs["plans"], "source_inventory.json")
        self._write_json(inventory_path, inventory)
        ctx.artifacts.register_file("source.inventory", inventory_path, {}, "application/json")
        self._save(ctx)

    def _stage_edit_agent_compile(self, ctx: ExecutionContext) -> None:
        template_art = ctx.artifacts.get("reference.edit_template")
        inventory_art = ctx.artifacts.get("source.inventory")
        
        if template_art is None or inventory_art is None:
            raise RuntimeError("reference.edit_template and source.inventory artifacts are required.")
            
        reference_template = self._load_json_if_exists(template_art.path_or_url)
        source_inventory = self._load_json_if_exists(inventory_art.path_or_url)
        
        try:
            compile_res = run_edit_agent_compile_stage(
                job_id=ctx.job_id,
                job_dir=ctx.dirs["job"],
                requirements=ctx.requirements,
                request_payload=ctx.request_payload,
                reference_template=reference_template,
                source_inventory=source_inventory,
                audio_plan=ctx.state.audio_plan or None,
                overlay_plan=ctx.state.overlay_plan or None,
            )
        except ReferenceEditAgentError as exc:
            error_path = os.path.join(ctx.dirs["plans"], "edit_agent_error.json")
            if os.path.exists(error_path):
                ctx.artifacts.register_file(
                    "edit.agent_error",
                    error_path,
                    {"code": exc.code},
                    "application/json",
                )
            raise ProviderFailure(
                provider="reference_edit_agent",
                code=exc.code,
                user_message=exc.message,
                detail=exc.detail,
                retryable=False,
            ) from exc
        
        ctx.artifacts.register_file(
            "user.patched_plan",
            os.path.join(ctx.dirs["plans"], "user_patched_plan.json"),
            {},
            "application/json",
        )
        ctx.artifacts.register_file(
            "edit.agent_graph",
            os.path.join(ctx.dirs["plans"], "executable_edit_graph.json"),
            {},
            "application/json",
        )
        ctx.artifacts.register_file(
            "edit.graph_validation",
            os.path.join(ctx.dirs["plans"], "edit_graph_validation.json"),
            {},
            "application/json",
        )
        ctx.artifacts.register_file(
            "render.compiled_spec",
            os.path.join(ctx.dirs["plans"], "compiled_render_spec.json"),
            {},
            "application/json",
        )
        training_sample_path = compile_res.get("training_sample_path")
        if training_sample_path:
            ctx.artifacts.register_file(
                "training.edit_agent_sample",
                training_sample_path,
                {},
                "application/json",
            )

        render_spec = compile_res["render_spec"]
        ctx.state.render_spec = render_spec
        
        canonical_timeline = render_spec.get("canonical_timeline") or []
        durations = [float(row.get("duration", 0.0)) for row in canonical_timeline]
        
        ctx.state.current_plan = {
            "planning_strategy": "reference_edit_agent",
            "scene_durations": durations,
            "selected_segments": [],
            "support_segments": [],
            "plan_validation": {
                "validation_score": float(compile_res["validation"].get("score", 1.0)),
                "validator_strategy": "edit_graph_validator",
            },
            "planning_debug": {
                "edit_agent_backend": os.getenv("EDIT_AGENT_BACKEND", "llm_json") or "llm_json",
                "edit_graph_version": "edit_graph_v1",
            }
        }
        
        apply_plan_validation(ctx.state, ctx.state.current_plan["plan_validation"])
        
        if compile_res["validation"].get("valid") is True:
            ctx.state.plan_needs_validation = False
            
        write_plan(ctx.dirs["job"], "timeline_plan.json", ctx.state.current_plan)
        write_plan(ctx.dirs["job"], "render_spec.json", render_spec)
        
        self._save(ctx)

    def _load_analysis(self, ctx: ExecutionContext) -> Dict[str, Any]:
        if ctx.state.analysis:
            return ctx.state.analysis
        artifact = ctx.artifacts.get("analysis.json")
        if artifact and os.path.exists(artifact.path_or_url):
            analysis = self._load_json_if_exists(artifact.path_or_url)
            ctx.state.analysis = analysis
            return analysis
        return {}

    def _source_keys_for_generation(self, ctx: ExecutionContext) -> List[str]:
        generation_mode = normalize_generation_mode(
            ctx.requirements.get("generation_mode"),
            default=FREE_GENERATION_MODE,
        )
        if generation_mode in {REFERENCE_STYLE_TRANSFER_MODE, VISION_TEMPLATE_LEARNING_MODE, REFERENCE_EDIT_AGENT_MODE}:
            return _sorted_indexed_artifact_keys(ctx.artifacts.items, "sources.fetch.")
        source_keys = _sorted_indexed_artifact_keys(ctx.artifacts.items, "sources.aligned.")
        if not source_keys:
            source_keys = _sorted_indexed_artifact_keys(ctx.artifacts.items, "sources.raw.")
        return source_keys

    def _source_durations_for_plan(self, ctx: ExecutionContext, analysis: Dict[str, Any]) -> List[float]:
        generation_mode = normalize_generation_mode(
            ctx.requirements.get("generation_mode"),
            default=FREE_GENERATION_MODE,
        )
        if generation_mode in {REFERENCE_STYLE_TRANSFER_MODE, VISION_TEMPLATE_LEARNING_MODE, REFERENCE_EDIT_AGENT_MODE}:
            return []
        source_keys = self._source_keys_for_generation(ctx)
        source_paths = [ctx.artifacts.get(key).path_or_url for key in source_keys if ctx.artifacts.get(key)]
        return [_probe_duration(path) for path in source_paths]

    def _refresh_source_status(self, ctx: ExecutionContext) -> None:
        raw_count = len(_sorted_indexed_artifact_keys(ctx.artifacts.items, "sources.raw."))
        fetch_count = len(_sorted_indexed_artifact_keys(ctx.artifacts.items, "sources.fetch."))
        aligned_count = len(_sorted_indexed_artifact_keys(ctx.artifacts.items, "sources.aligned."))
        status = {
            "generation_mode": normalize_generation_mode(
                ctx.requirements.get("generation_mode"),
                default=FREE_GENERATION_MODE,
            ),
            "primary_ready": _artifact_path_exists(ctx.artifacts, "primary.video"),
            "raw_source_count": raw_count,
            "fetch_source_count": fetch_count,
            "aligned_source_count": aligned_count,
            "sources_ready": fetch_count > 0 or aligned_count > 0 or raw_count > 0,
            "drive_folder_connected": bool(ctx.request_payload.get("gdrive_folder_id")),
        }
        set_source_status(ctx.state, status)
        self._save(ctx)

    def _record_overlay_warnings(self, ctx: ExecutionContext, overlay_plan: Dict[str, Any]) -> None:
        for warning in overlay_plan.get("warnings", []):
            add_warning(
                ctx.state,
                warning.get("code", "OVERLAY_WARNING"),
                warning.get("message", "Overlay warning"),
                warning.get("detail"),
            )

    def _apply_motion_effects_to_render_spec(
        self,
        ctx: ExecutionContext,
        render_spec: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Applies motion effects from the manifest to each clip in the canonical
        timeline using scene_id -> shot_index alignment.
        """
        if not ctx.state.motion_effects_path or not ctx.state.is_vision_mode():
            return render_spec
        canonical_timeline = list(render_spec.get("canonical_timeline") or [])
        if not canonical_timeline or not os.path.exists(ctx.state.motion_effects_path):
            return render_spec

        manifest = MotionEffectManifest.from_dict(
            self._load_json_if_exists(ctx.state.motion_effects_path)
        )
        effects_by_shot: Dict[int, List[Any]] = {}
        for effect in manifest.effects:
            if effect.effect_type.value == "static":
                continue
            effects_by_shot.setdefault(effect.shot_index, []).append(effect)

        if not effects_by_shot:
            log.debug("No non-static effects in manifest; skipping motion effect application")
            return render_spec

        applier = MotionEffectApplier()
        updated_timeline: List[Dict[str, Any]] = []
        stylized_count = 0

        for row in canonical_timeline:
            entry = dict(row)
            clip_path = str(entry.get("video_src") or entry.get("videoSrc") or "").strip()
            scene_id = entry.get("scene_id")
            if scene_id is not None:
                shot_index = int(scene_id) - 1
            else:
                shot_index = int(entry.get("index", 1)) - 1

            if shot_index not in effects_by_shot:
                updated_timeline.append(entry)
                continue
            if not clip_path or _is_http_url(clip_path) or not os.path.exists(clip_path):
                updated_timeline.append(entry)
                continue

            base, ext = os.path.splitext(clip_path)
            output_path = f"{base}_stylized{ext or '.mp4'}"

            shot_manifest = MotionEffectManifest(
                video_path=manifest.video_path,
                fps=manifest.fps,
                total_frames=manifest.total_frames,
                effects=effects_by_shot[shot_index],
                rhythm_pattern=manifest.rhythm_pattern,
                global_motion_budget=manifest.global_motion_budget,
            )
            for effect in shot_manifest.effects:
                effect.shot_index = 0

            applied_path = applier.apply_to_clip(clip_path, 0, shot_manifest, output_path)
            entry["video_src"] = applied_path
            entry["videoSrc"] = applied_path
            if applied_path != clip_path:
                stylized_count += 1
                entry.setdefault("metadata", {})
                entry["metadata"]["motion_effects_applied"] = True
                entry["metadata"]["original_video_src"] = clip_path
                entry["metadata"]["shot_index_used"] = shot_index
            updated_timeline.append(entry)

        if manifest.transitions_detected and _should_bake_reference_transitions(render_spec):
            for transition in manifest.transitions_detected:
                out_idx = transition.outgoing_shot_index
                in_idx = transition.incoming_shot_index

                if out_idx < len(updated_timeline):
                    row = updated_timeline[out_idx]
                    clip = str(row.get("video_src") or "").strip()
                    if clip and not _is_http_url(clip) and os.path.exists(clip):
                        base, ext = os.path.splitext(clip)
                        tail_out = f"{base}_trans_tail{ext or '.mp4'}"
                        applied = applier.apply_transition_to_clip(clip, transition, tail_out, position="end")
                        if applied != clip:
                            updated_timeline[out_idx]["video_src"] = applied
                            updated_timeline[out_idx]["videoSrc"] = applied
                            updated_timeline[out_idx].setdefault("metadata", {})
                            updated_timeline[out_idx]["metadata"]["transition_out"] = transition.transition_type.value

                if in_idx < len(updated_timeline):
                    updated_timeline[in_idx].setdefault("metadata", {})
                    updated_timeline[in_idx]["metadata"]["transition_in"] = transition.transition_type.value
        elif manifest.transitions_detected:
            log.warning(
                "Skipping reference transition baking (FFMPEG_DISABLE_TRANSITIONS or disable_auto_transitions)."
            )

        updated_spec = dict(render_spec)
        updated_spec["canonical_timeline"] = updated_timeline
        updated_spec.setdefault("edit_summary", {})
        updated_spec["edit_summary"]["motion_effect_clips_stylized"] = stylized_count
        return updated_spec

    def _build_render_filter_plan(self, render_spec: Dict[str, Any]) -> Dict[str, Any]:
        clips = []
        for index, row in enumerate(render_spec.get("canonical_timeline") or []):
            metadata = row.get("metadata") or {}
            clips.append(
                {
                    "index": index,
                    "start": float(row.get("start", 0.0)),
                    "end": float(row.get("end", row.get("start", 0.0))),
                    "duration": float(row.get("duration", row.get("length", 0.0)) or 0.0),
                    "text": row.get("text"),
                    "text_start": row.get("text_start"),
                    "text_end": row.get("text_end"),
                    "transition_in": metadata.get("transition_in"),
                    "transition_out": metadata.get("transition_out"),
                    "transition_applied": bool(
                        metadata.get("transition_in") or metadata.get("transition_out")
                    ),
                    "motion_effects_applied": bool(metadata.get("motion_effects_applied")),
                }
            )
        return {
            "transitions_disabled": not _should_bake_reference_transitions(render_spec),
            "disable_auto_transitions": bool(render_spec.get("disable_auto_transitions")),
            "clips": clips,
        }

    def _write_plan_bundle(
        self,
        ctx: ExecutionContext,
        *,
        timeline_plan: Dict[str, Any],
        overlay_plan: Dict[str, Any],
        audio_plan: Dict[str, Any],
        render_spec: Dict[str, Any],
        postprocess_plan: Dict[str, Any],
        analysis_duration: float,
        render_duration: float,
    ) -> None:
        write_plan(ctx.dirs["job"], "audio_plan.json", audio_plan)
        write_plan(ctx.dirs["job"], "overlay_plan.json", overlay_plan)
        write_plan(
            ctx.dirs["job"],
            "overlay_script.json",
            overlay_plan.get("overlay_script") or {"title": "", "items": [], "source": ""},
        )
        write_plan(
            ctx.dirs["job"],
            "text_segments.json",
            {
                "segments": overlay_plan.get("text_segments", []),
                "warnings": overlay_plan.get("warnings", []),
                "analysis_duration": analysis_duration,
                "render_duration": render_duration,
            },
        )
        write_plan(ctx.dirs["job"], "timeline_plan.json", timeline_plan)
        write_plan(ctx.dirs["job"], "render_spec.json", render_spec)
        write_plan(ctx.dirs["job"], "postprocess_plan.json", postprocess_plan)
        if render_spec.get("canonical_timeline"):
            write_plan(
                ctx.dirs["job"],
                "canonical_timeline.json",
                {
                    "generation_mode": render_spec.get("generation_mode"),
                    "edit_mode": render_spec.get("edit_mode"),
                    "timeline": render_spec.get("canonical_timeline", []),
                },
            )
            write_plan(
                ctx.dirs["job"],
                "overlay_timing.json",
                {
                    "generation_mode": render_spec.get("generation_mode"),
                    "edit_mode": render_spec.get("edit_mode"),
                    "overlays": render_spec.get("overlay_timing", []),
                },
            )

    def _get_edit_operations_from_state(self, ctx: ExecutionContext) -> List[EditOperation]:
        """
        Returns EditOperation objects from the current job state.

        Priority order:
        1. state.parsed_operations — freshly parsed by IntentParser this turn
        2. state.edit_requests     — accumulated history (may be dicts or legacy strings)
        """
        from ai_editor.editing.edit_operations import EditOperation, TimeWindowTarget
        from ai_editor.editing.instruction_parser import InstructionParser

        operations: List[EditOperation] = []

        # 1. Freshly parsed operations from this turn (already EditOperation dicts)
        requirements = {}
        if isinstance(ctx.requirements, dict):
            requirements = ctx.requirements
        elif isinstance(getattr(ctx.state, "requirements", None), dict):
            requirements = ctx.state.requirements

        parsed = requirements.get("parsed_operations") or []
        for item in parsed:
            if isinstance(item, dict) and item.get("operation"):
                try:
                    tw_raw = item.get("time_window")
                    tw = None
                    if isinstance(tw_raw, dict):
                        tw = TimeWindowTarget(
                            start=tw_raw.get("start"),
                            end=tw_raw.get("end"),
                            label=str(tw_raw.get("label") or "global"),
                        )
                    operations.append(EditOperation(
                        operation=str(item.get("operation") or "custom"),
                        target=item.get("target"),
                        value=item.get("value"),
                        intensity=float(item.get("intensity") or 1.0),
                        scope=str(item.get("scope") or "global"),
                        time_window=tw,
                        source_target=item.get("source_target"),
                        segment_target=item.get("segment_target"),
                        section_label=item.get("section_label"),
                        position=item.get("position"),
                        metadata=dict(item.get("metadata") or {}),
                    ))
                except Exception as exc:
                    log.warning("Executor: failed to reconstruct EditOperation from %r: %s", item, exc)

        if operations:
            return operations

        # 2. Fall back to accumulated edit_requests history
        # Handles both new-style dicts and legacy strings
        _parser = InstructionParser()
        for request in (requirements.get("edit_requests") or []):
            if isinstance(request, dict) and request.get("operation"):
                # New-style dict — reconstruct directly (same as above)
                try:
                    tw_raw = request.get("time_window")
                    tw = None
                    if isinstance(tw_raw, dict):
                        tw = TimeWindowTarget(
                            start=tw_raw.get("start"),
                            end=tw_raw.get("end"),
                            label=str(tw_raw.get("label") or "global"),
                        )
                    operations.append(EditOperation(
                        operation=str(request.get("operation") or "custom"),
                        target=request.get("target"),
                        value=request.get("value"),
                        intensity=float(request.get("intensity") or 1.0),
                        scope=str(request.get("scope") or "global"),
                        time_window=tw,
                        source_target=request.get("source_target"),
                        segment_target=request.get("segment_target"),
                        section_label=request.get("section_label"),
                        position=request.get("position"),
                        metadata=dict(request.get("metadata") or {}),
                    ))
                except Exception:
                    pass
            elif isinstance(request, str) and request.strip():
                # Legacy string format — parse with InstructionParser
                parsed_legacy = _parser.parse(request)
                operations.extend(parsed_legacy)

        return operations

    def _apply_edit_requests(
        self,
        ctx: ExecutionContext,
        timeline_plan: Dict[str, Any],
        *,
        requests: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        requests = list(requests or [])
        if not timeline_plan:
            return timeline_plan
        requirements = ctx.requirements if isinstance(ctx.requirements, dict) else {}
        if not requests and not (requirements.get("parsed_operations") or []):
            return timeline_plan

        session = EditSession.from_payloads(
            timeline_plan=timeline_plan,
            analysis=self._load_analysis(ctx),
            requirements=ctx.requirements,
        )
        processed_requests: List[str] = []
        unstructured_requests: List[str] = []
        
        operations = self._get_edit_operations_from_state(ctx)

        if not operations:
            for request in requests:
                unstructured_requests.append(request)
        else:
            for request in requests:
                processed_requests.append(request)
            for operation in operations:
                session.apply_operations([operation], raw_instruction=operation.operation)

        if processed_requests:
            mark_edit_requests_applied(ctx.state, processed_requests)

        for request in unstructured_requests:
            add_warning(
                ctx.state,
                "UNSTRUCTURED_EDIT_REQUEST",
                "An edit request could not be mapped to deterministic plan operations, so it was kept as qualitative guidance only.",
                {"request": request},
            )

        if not session.history:
            return timeline_plan

        patched_plan = dict(session.timeline_plan)
        patch_history = [
            {
                "instruction": entry.get("instruction", ""),
                "operation_count": int((entry.get("result") or {}).get("operation_count", 0) or 0),
            }
            for entry in session.history
        ]
        applied_operations = []
        deferred_operations = []
        for entry in session.history:
            result = entry.get("result") or {}
            applied_operations.extend(list(result.get("applied_operations") or []))
            deferred_operations.extend(list(result.get("deferred_operations") or []))

        debug = dict(patched_plan.get("planning_debug") or {})
        debug["controller_feedback_requests_applied"] = processed_requests
        debug["controller_feedback_patch_history"] = patch_history
        patched_plan["planning_debug"] = debug
        patched_plan["plan_patch"] = {
            "applied_requests": processed_requests,
            "applied_operations": applied_operations,
            "deferred_operations": deferred_operations,
            "operation_count": len(applied_operations),
            "patch_strategy": "controller_feedback_edit_patch",
        }
        return patched_plan

    def _ensure_render_gate(
        self,
        ctx: ExecutionContext,
        decision: PipelineDecision,
        *,
        action_name: str,
    ) -> None:
        if pending_edit_requests(ctx.state):
            raise RuntimeError(f"{action_name} blocked: pending edit requests remain unapplied.")
        if not ctx.state.current_plan:
            raise RuntimeError(f"{action_name} blocked: no current plan is available.")
        if ctx.state.plan_needs_validation or not ctx.state.plan_validation or ctx.state.plan_validation_score is None:
            raise RuntimeError(f"{action_name} blocked: plan validation is missing or stale.")
        override_reason = _validation_override_reason(decision.parameters)
        if ctx.state.plan_validation_score < self.minimum_validation_score and not override_reason:
            raise RuntimeError(
                f"{action_name} blocked: validation score {ctx.state.plan_validation_score:.3f} is below "
                f"minimum {self.minimum_validation_score:.3f}."
            )
        if override_reason:
            add_warning(
                ctx.state,
                "VALIDATION_GATE_BYPASSED",
                f"{action_name} was allowed because an explicit validation override reason was recorded.",
                {
                    "action": action_name,
                    "override_reason": override_reason,
                    "validation_score": ctx.state.plan_validation_score,
                },
            )

    def _build_success_response(self, ctx: ExecutionContext, *, status: str) -> Dict[str, Any]:
        render_url_artifact = (
            ctx.artifacts.get("render.output_url")
            or ctx.artifacts.get("render.ffmpeg_url")
            or ctx.artifacts.get("render.shotstack_url")
        )
        render_url = render_url_artifact.path_or_url if render_url_artifact else None
        render_id = (render_url_artifact.meta or {}).get("render_id") if render_url_artifact else None
        render_spec = ctx.state.render_spec or self._load_json_if_exists(os.path.join(ctx.dirs["plans"], "render_spec.json"))
        resolution = str(render_spec.get("resolution", "1080x1920"))
        render_aspect = "16:9" if resolution == "1920x1080" else ("1:1" if resolution == "1080x1080" else "9:16")
        user_notice = next(
            (warning["message"] for warning in ctx.state.warnings if warning.get("code") == "SOURCE_DURATION_SHORT"),
            None,
        )
        ffmpeg_error = next(
            (warning.get("detail") for warning in ctx.state.warnings if warning.get("code") == "FFMPEG_POSTPROCESS_FAILED"),
            None,
        )
        return {
            "success": True,
            "url": render_url,
            "render_id": render_id,
            "status": status,
            "project_id": ctx.job_id,
            "intent_mode": ctx.requirements.get("intent_mode", "video"),
            "refit_mode": ctx.requirements.get("refit_mode", "crop_center"),
            "output_mode": ctx.requirements.get("output_mode", "crop_to_9x16"),
            "render_aspect": render_aspect,
            "preview_url": ctx.runtime.get("preview_url"),
            "preview_mode": ctx.runtime.get("preview_mode", "video"),
            "user_notice": user_notice,
            "ffmpeg_error": ffmpeg_error,
            "warnings": ctx.state.warnings,
            "errors": ctx.state.errors,
            **build_controller_status_payload(ctx.state),
        }

    def _load_json_if_exists(self, path: str) -> Dict[str, Any]:
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def _write_json(self, path: str, payload: Any) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

    def _save(self, ctx: ExecutionContext) -> None:
        self._save_hook(ctx)


def _is_http_url(value: Any) -> bool:
    return isinstance(value, str) and value.strip().lower().startswith(("http://", "https://"))


def _default_drive_folder() -> Optional[str]:
    return os.getenv("DRIVE_UPLOAD_FOLDER_ID") or os.getenv("DRIVE_DEFAULT_FOLDER_ID") or os.getenv("VIDEO_FOLDER")


def _upload_assets_for_shotstack(job_id: str, local_paths: List[str]) -> List[Dict[str, Any]]:
    if not local_paths:
        return []
    from .storage import DriveStorageAdapter

    try:
        adapter = DriveStorageAdapter()
    except Exception as exc:
        raise normalize_provider_exception(
            "drive_storage",
            exc,
            operation="shotstack_asset_upload.init",
            config_message="Google Drive is not configured correctly for render asset uploads.",
            timeout_message="Google Drive timed out while preparing render asset uploads.",
            auth_message="Google Drive access is not authorized for render asset uploads.",
            network_message="Google Drive is temporarily unavailable for render asset uploads.",
            default_message="Preparing Google Drive uploads for rendering failed.",
        ) from exc
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
                message = str(exc)
                if current_folder and (
                    "insufficientParentPermissions" in message or "Insufficient permissions" in message
                ):
                    current_folder = None
                    continue
                if attempt == attempts - 1:
                    raise
                time.sleep(2**attempt)
        if asset is None:
            if last_exc is not None:
                raise normalize_provider_exception(
                    "drive_storage",
                    last_exc,
                    operation="shotstack_asset_upload.upload",
                    config_message="Google Drive is not configured correctly for render asset uploads.",
                    timeout_message="Google Drive timed out while uploading render assets.",
                    auth_message="Google Drive access is not authorized for render asset uploads.",
                    network_message="Google Drive is temporarily unavailable for render asset uploads.",
                    default_message="Uploading render assets to Google Drive failed.",
                ) from last_exc
            raise RuntimeError(f"Failed to upload {normalized}")
        try:
            adapter.drive.permissions().create(
                fileId=asset.id,
                body={"type": "anyone", "role": "reader"},
                fields="id",
            ).execute()
        except Exception as exc:
            raise normalize_provider_exception(
                "drive_storage",
                exc,
                operation="shotstack_asset_upload.permissions",
                config_message="Google Drive is not configured correctly for public asset sharing.",
                timeout_message="Google Drive timed out while sharing render assets.",
                auth_message="Google Drive access is not authorized for asset sharing.",
                network_message="Google Drive is temporarily unavailable for asset sharing.",
                default_message="Sharing uploaded render assets failed.",
            ) from exc
        public_url = adapter.get_fetchable_url(asset)
        try:
            response = requests.head(public_url, timeout=10)
            if response.status_code >= 400:
                print(f"Warning: HEAD {public_url} returned {response.status_code}")
        except requests.RequestException as exc:
            print(f"Warning: could not verify {public_url}: {exc}")
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

        capture = cv2.VideoCapture(path)
        if not capture.isOpened():
            return 0.0
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        frames = float(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
        capture.release()
        return (frames / fps) if fps > 0 else 0.0
    except Exception:
        return 0.0


def _probe_duration_any(path_or_url: str) -> float:
    if not path_or_url:
        return 0.0
    duration = _probe_duration(path_or_url)
    if duration > 0:
        return duration
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
    lowered = str(url).lower().strip()
    if "drive.google.com/uc?" in lowered:
        return True
    return any(lowered.endswith(ext) for ext in [".mp4", ".mov", ".m4v", ".webm", ".mkv"])


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
    try:
        return float(raw)
    except ValueError:
        pass
    if ":" not in raw:
        return None
    parts = raw.split(":")
    if len(parts) not in {2, 3}:
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
    return float(hours * 3600 + minutes * 60 + seconds)


def _extract_music_segment(requirements: Dict[str, Any]) -> Optional[Tuple[float, Optional[float]]]:
    segment = requirements.get("custom_music_segment") or requirements.get("custom_music_segments")
    if isinstance(segment, list) and segment:
        segment = segment[0]
    if isinstance(segment, str):
        cleaned = segment.strip()
        if "-" in cleaned and "http" not in cleaned.lower():
            parts = [part.strip() for part in cleaned.split("-", 1)]
            if len(parts) == 2:
                start = _parse_timestamp_seconds(parts[0])
                end = _parse_timestamp_seconds(parts[1])
                if start is not None and (end is None or end > start):
                    return max(0.0, start), end
    if isinstance(segment, dict):
        start = _parse_timestamp_seconds(segment.get("start"))
        end = _parse_timestamp_seconds(segment.get("end")) if segment.get("end") is not None else None
        if start is not None:
            if end is not None and end <= start:
                return None
            return max(0.0, start), end

    start = requirements.get("custom_music_start")
    end = requirements.get("custom_music_end")
    start_value = _parse_timestamp_seconds(start)
    end_value = _parse_timestamp_seconds(end) if end is not None else None
    if start_value is not None:
        if end_value is not None and end_value <= start_value:
            return None
        return max(0.0, start_value), end_value
    return None


def _download_file(url: str, out_path: str) -> None:
    with requests.get(url, stream=True, timeout=180) as response:
        response.raise_for_status()
        with open(out_path, "wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)
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
    sources = []
    for path in raw_paths:
        duration = _probe_duration(path)
        if duration > 0:
            sources.append({"path": path, "dur": duration})
    if not sources or not scene_durations:
        return [], None
    total_source = sum(source["dur"] for source in sources)
    total_target = sum(scene_durations)
    if total_source + 0.05 < total_target:
        return [], (
            f"Uploaded source duration ({total_source:.1f}s) is shorter than analyzed timeline ({total_target:.1f}s). "
            "Proceeding with sources as-is. Re-upload if this is not your intent."
        )
    os.makedirs(out_dir, exist_ok=True)
    aligned = []
    for index, _target_duration in enumerate(scene_durations, start=1):
        source_index = index - 1
        if source_index >= len(sources):
            return [], f"Not enough source clips for strict index alignment: need source {index} for scene {index}."
        current = sources[source_index]
        if current["dur"] <= 0.05:
            return [], f"Source {index} has invalid duration ({current['dur']:.2f}s)."
        dst = os.path.join(out_dir, f"aligned_{index:03d}.mp4")
        shutil.copy2(current["path"], dst)
        aligned.append(dst)
    return aligned, None


def _sorted_indexed_artifact_keys(items: Dict[str, Any], prefix: str) -> List[str]:
    keys = []
    for key in items:
        if not key.startswith(prefix):
            continue
        suffix = key[len(prefix) :]
        if suffix.isdigit():
            keys.append(key)
    return sorted(keys, key=lambda item: int(item[len(prefix) :]))


def _collect_edit_request_lines(requirements: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    for key in ("edit_requests", "user_requests"):
        values = requirements.get(key) or []
        if isinstance(values, list):
            lines.extend([str(value) for value in values if str(value).strip()])
    return lines


def _should_bake_reference_transitions(render_spec: Dict[str, Any]) -> bool:
    """Reference transition baking is opt-in; FFmpeg uses safe hard cuts by default."""
    if bool(render_spec.get("disable_auto_transitions")):
        return False
    flag = os.getenv("FFMPEG_DISABLE_TRANSITIONS", "1").strip().lower()
    return flag not in {"1", "true", "yes", "on"}


def _apply_confirmed_text_overlays_to_timeline(
    timeline: List[Dict[str, Any]],
    text_overlays: List[Dict[str, Any]],
) -> None:
    """Apply only user-confirmed text overlays to canonical timeline rows."""
    for overlay in text_overlays or []:
        action = str(overlay.get("action", "ask_user")).strip().lower()
        if action in {"remove", "ask_user", "skip", ""}:
            continue

        render_text = str(overlay.get("render_text", "")).strip()
        if action == "keep":
            render_text = str(overlay.get("detected_text", render_text)).strip()
        if not render_text:
            continue

        overlay_start = float(overlay.get("start", 0.0))
        overlay_end = float(overlay.get("end", overlay_start + 0.5))
        position = str(overlay.get("position", "center")).strip().lower() or "center"
        style = overlay.get("style") or {"box": False, "stroke": True, "shadow": False}

        for row in timeline:
            row_start = float(row.get("start", 0.0))
            row_end = float(row.get("end", row_start + float(row.get("duration", 0.0) or 0.0)))
            if overlay_end <= row_start or overlay_start >= row_end:
                continue
            row["text"] = _sanitize_overlay_text(render_text)
            row["text_start"] = max(overlay_start, row_start)
            row["text_end"] = min(overlay_end, row_end)
            row["position"] = position
            row["text_style"] = style
            row.setdefault("metadata", {})
            row["metadata"]["text_action"] = "render"
            break


def _write_render_filter_plan(debug_dir: str, plan: Dict[str, Any]) -> None:
    os.makedirs(debug_dir, exist_ok=True)
    path = os.path.join(debug_dir, "render_filter_plan.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(plan, handle, indent=2, ensure_ascii=False)


def _sanitize_overlay_text(text: str) -> str:
    cleaned = str(text or "")
    cleaned = re.sub(r"\((?:top|bottom|middle|center)\)", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("|", " ")
    cleaned = cleaned.replace("'", "")
    return " ".join(cleaned.split()).strip()


def _parse_edit_ops(requirements: Dict[str, Any]) -> List[Dict[str, Any]]:
    ops: List[Dict[str, Any]] = []
    for raw in _collect_edit_request_lines(requirements):
        line = raw.strip()
        if not line:
            continue
        prefix = line.split(":", 1)[0].strip().lower()
        if prefix in {"remove", "cut", "delete", "trim", "add", "replace", "swap", "edit"} and ":" in line:
            line = line.split(":", 1)[1].strip()
        lowered = line.lower()

        match = re.search(r"(?:trim|remove|cut)\s+(?:the\s+)?(?:end|last)\s+(\d+(?:\.\d+)?)", lowered)
        if not match:
            match = re.search(r"last\s+(\d+(?:\.\d+)?)\s*(?:s|sec|secs|seconds)", lowered)
        if match:
            ops.append({"op": "trim_end", "seconds": float(match.group(1)), "raw": raw})
            continue

        match = re.search(r"(?:remove|delete|cut)\s+(?:clip|scene)\s*(\d+)", lowered)
        if match:
            ops.append({"op": "remove_clip", "index": int(match.group(1)), "raw": raw})
            continue

        match = re.search(r"swap\s+(?:clip|scene)?\s*(\d+)\s*(?:and|with)\s*(\d+)", lowered)
        if not match:
            match = re.search(r"swap\s+(\d+)\s+(\d+)", lowered)
        if match:
            ops.append({"op": "swap", "a": int(match.group(1)), "b": int(match.group(2)), "raw": raw})
            continue

        match = re.search(
            r"replace\s+(?:clip|scene)?\s*(\d+)\s+(?:with|from)\s*(?:clip|scene)?\s*(\d+)",
            lowered,
        )
        if match:
            ops.append(
                {"op": "replace_clip", "index": int(match.group(1)), "source": int(match.group(2)), "raw": raw}
            )
            continue

        match = re.search(
            r"(?:add\s+)?overlay\s+text(?:\s+for)?\s*(?:clip|scene)?\s*(\d+)?\s*(?:is|=|:)?\s*(.+)$",
            line,
            flags=re.IGNORECASE,
        )
        if match:
            index = int(match.group(1)) if match.group(1) else None
            text = _sanitize_overlay_text(match.group(2))
            if text:
                ops.append({"op": "set_overlay_text", "index": index, "text": text, "raw": raw})
    return ops


def _reflow_timeline(timeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    output: List[Dict[str, Any]] = []
    cursor = 0.0
    for index, row in enumerate(timeline, start=1):
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
        row["index"] = index
        row["scene_id"] = int(row.get("scene_id", index))
        row["label"] = f"{prefix}_{index:03d}"
        row["start"] = cursor
        row["end"] = cursor + duration
        row["duration"] = duration
        row["length"] = duration
        row["text_start"] = row.get("text_start", row["start"])
        row["text_end"] = row.get("text_end", row["end"])
        cursor = row["end"]
        output.append(row)
    return output


def _apply_edit_ops_to_timeline(
    timeline: List[Dict[str, Any]],
    ops: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if not timeline or not ops:
        return timeline, {"applied": [], "timing_changed": False, "count_changed": False}

    rows = [dict(row) for row in timeline]
    applied: List[Dict[str, Any]] = []
    timing_changed = False
    count_changed = False
    overlay_queue: List[str] = []

    def _valid_index(index: int) -> bool:
        return 1 <= index <= len(rows)

    for op in ops:
        if op["op"] == "trim_end":
            seconds = max(0.0, float(op.get("seconds", 0.0)))
            if seconds <= 0 or not rows:
                continue
            last = rows[-1]
            duration = float(last.get("duration", last.get("length", 0.0)) or 0.0)
            new_duration = max(0.0, duration - seconds)
            last["duration"] = new_duration
            last["length"] = new_duration
            timing_changed = True
            if new_duration <= 0:
                rows.pop()
                count_changed = True
            applied.append(op)
            continue

        if op["op"] == "remove_clip":
            index = int(op.get("index", 0) or 0)
            if _valid_index(index):
                rows.pop(index - 1)
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
            index = int(op.get("index", 0) or 0)
            source_index = int(op.get("source", 0) or 0)
            if _valid_index(index) and _valid_index(source_index) and index != source_index:
                source_row = rows[source_index - 1]
                dest_row = rows[index - 1]
                for key in ("video_src", "videoSrc", "trim", "source_duration", "source_index"):
                    if key in source_row:
                        dest_row[key] = source_row.get(key)
                applied.append(op)
            continue

        if op["op"] == "set_overlay_text":
            index = op.get("index")
            text = _sanitize_overlay_text(op.get("text", ""))
            if not text:
                continue
            if index and _valid_index(int(index)):
                row = rows[int(index) - 1]
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


def _build_reference_timeline(analysis: Dict[str, Any], sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    scenes = analysis.get("scenes") or []
    if not scenes:
        raise RuntimeError("Reference style transfer requires analyzed scenes.")
    durations = [float(scene.get("duration", 0.0)) for scene in scenes]
    if any(duration <= 0 for duration in durations):
        raise RuntimeError("Reference style transfer requires positive analyzed scene durations.")
    if not sources:
        raise RuntimeError("No valid source clips available for reference style transfer.")
    if len(sources) < len(scenes):
        raise RuntimeError(
            f"Reference style transfer requires at least {len(scenes)} sources; received {len(sources)}."
        )

    timeline = []
    for index, scene in enumerate(scenes, start=1):
        target_duration = float(scene.get("duration", 0.0))
        source = sources[index - 1]
        video_src = str(source.get("video_src", "")).strip()
        probe_src = str(source.get("probe_src", "")).strip() or video_src
        trim_start = max(0.0, float(source.get("trim", 0.0)))
        source_duration = -1.0
        if probe_src and not _is_http_url(probe_src):
            source_duration = _probe_duration_any(probe_src)
            if source_duration <= 0.0:
                raise RuntimeError(
                    f"Reference style transfer source {index} duration could not be determined: {probe_src}"
                )
            if source_duration + 0.02 < trim_start + target_duration:
                raise RuntimeError(
                    f"Reference style transfer assignment failed for scene {index}: source too short "
                    f"(source={source_duration:.2f}s, trim={trim_start:.2f}s, required={target_duration:.2f}s)."
                )
        start = float(scene.get("start_time", sum(durations[: index - 1])))
        end = float(scene.get("end_time", start + target_duration))
        timeline.append(
            {
                "index": index,
                "scene_id": int(scene.get("scene_id", index)),
                "label": f"scene_{index:03d}",
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
    tolerance = 0.05
    if len(timeline) != len(scenes):
        errors.append(f"scene_count mismatch: generated={len(timeline)} analyzed={len(scenes)}")
    analyzed_durations = [float(scene.get("duration", 0.0)) for scene in scenes]
    generated_durations = [float(row.get("duration", 0.0)) for row in timeline]
    for index, (generated, analyzed) in enumerate(zip(generated_durations, analyzed_durations), start=1):
        if abs(generated - analyzed) > tolerance:
            errors.append(f"scene_duration mismatch at {index}: generated={generated:.3f}, analyzed={analyzed:.3f}")
    analyzed_total = sum(analyzed_durations)
    generated_total = sum(generated_durations)
    if abs(generated_total - analyzed_total) > tolerance:
        errors.append(f"total_duration mismatch: generated={generated_total:.3f}, analyzed={analyzed_total:.3f}")
    for index, overlay in enumerate(overlay_timing, start=1):
        start = float(overlay.get("start", 0.0))
        end = float(overlay.get("end", start))
        if end < start:
            errors.append(f"overlay timing invalid at {index}: start={start:.3f}, end={end:.3f}")
            continue

        containing_scene = None
        for scene_index, scene_row in enumerate(timeline, start=1):
            scene_start = float(scene_row.get("start", 0.0))
            scene_end = float(scene_row.get("end", scene_start + float(scene_row.get("duration", 0.0))))
            if scene_start - tolerance <= start and end <= scene_end + tolerance:
                containing_scene = (scene_index, scene_start, scene_end)
                break

        if containing_scene is None:
            errors.append(
                f"overlay containment mismatch at {index}: overlay={start:.3f}-{end:.3f} not within any scene"
            )
            continue

        scene_index, scene_start, scene_end = containing_scene
        if start < scene_start - tolerance:
            errors.append(
                f"overlay_start mismatch at {index}: overlay={start:.3f}, scene={scene_start:.3f}, scene_index={scene_index}"
            )
        if end > scene_end + tolerance:
            errors.append(
                f"overlay_end mismatch at {index}: overlay={end:.3f}, scene={scene_end:.3f}, scene_index={scene_index}"
            )
    if timeline:
        final_scene_end = float(timeline[-1].get("end", 0.0))
        if abs(final_scene_end - generated_total) > tolerance:
            errors.append(f"final_scene_end mismatch: final_end={final_scene_end:.3f}, total={generated_total:.3f}")
    return errors


def _build_overlay_timing_from_timeline(timeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    overlays = []
    for index, row in enumerate(timeline, start=1):
        start = float(row.get("text_start", row.get("start", 0.0)))
        end = float(row.get("text_end", row.get("end", start)))
        if end <= start:
            continue
        overlays.append(
            {"index": index, "text": str(row.get("text", "")).strip(), "start": start, "end": end, "length": end - start}
        )
    return overlays


def _build_ocr_timeline(
    text_segments: List[Dict[str, Any]],
    sources: List[Dict[str, Any]],
    strict_index_alignment: bool = False,
) -> List[Dict[str, Any]]:
    if not text_segments:
        raise RuntimeError("OCR mode selected but no OCR text segments were produced from analysis keyframes.")
    if not sources:
        raise RuntimeError("OCR mode requires at least one source clip URL/path.")
    ordered_segments = sorted(text_segments, key=lambda segment: float(segment.get("start", 0.0)))
    if strict_index_alignment and len(sources) < len(ordered_segments):
        raise RuntimeError(
            f"OCR mode in reference style transfer requires at least {len(ordered_segments)} sources; received {len(sources)}."
        )
    timeline: List[Dict[str, Any]] = []
    duration_cache: Dict[str, float] = {}
    for index, segment in enumerate(ordered_segments, start=1):
        start = float(segment.get("start", 0.0))
        end = float(segment.get("end", start))
        duration = end - start
        if duration <= 0.0:
            continue
        source = sources[index - 1] if strict_index_alignment else sources[min(index - 1, len(sources) - 1)]
        video_src = str(source.get("video_src", "")).strip()
        probe_src = str(source.get("probe_src", "")).strip() or video_src
        trim_start = max(0.0, float(source.get("trim", 0.0) or 0.0))
        if not video_src:
            raise RuntimeError(f"OCR timeline source {index} has no usable URL/path.")
        cache_key = probe_src or video_src
        if cache_key not in duration_cache:
            if cache_key and _is_http_url(cache_key):
                duration_cache[cache_key] = -1.0
            else:
                duration_cache[cache_key] = _probe_duration_any(cache_key)
        source_duration = float(duration_cache.get(cache_key, 0.0))
        if source_duration <= 0.0:
            source_duration = -1.0
        elif source_duration + 0.02 < trim_start + duration:
            raise RuntimeError(
                f"OCR timeline assignment failed for segment {index}: source too short "
                f"(source={source_duration:.2f}s, trim={trim_start:.2f}s, required={duration:.2f}s)."
            )
        text = str(segment.get("text", "")).strip()
        timeline.append(
            {
                "index": index,
                "scene_id": index,
                "label": f"ocr_{index:03d}",
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
            }
        )
    return timeline


def _validate_ocr_timeline(
    text_segments: List[Dict[str, Any]],
    timeline: List[Dict[str, Any]],
    overlay_timing: List[Dict[str, Any]],
) -> List[str]:
    errors: List[str] = []
    tolerance = 0.05
    ordered_segments = sorted(text_segments, key=lambda segment: float(segment.get("start", 0.0)))
    if len(ordered_segments) != len(timeline):
        errors.append(f"segment_count mismatch: text_segments={len(ordered_segments)} timeline={len(timeline)}")
    for index, (segment, row) in enumerate(zip(ordered_segments, timeline), start=1):
        segment_start = float(segment.get("start", 0.0))
        segment_end = float(segment.get("end", segment_start))
        row_start = float(row.get("start", 0.0))
        row_end = float(row.get("end", row_start))
        if abs(segment_start - row_start) > tolerance:
            errors.append(f"segment_start mismatch at {index}: segment={segment_start:.3f}, timeline={row_start:.3f}")
        if abs(segment_end - row_end) > tolerance:
            errors.append(f"segment_end mismatch at {index}: segment={segment_end:.3f}, timeline={row_end:.3f}")
    if len(overlay_timing) != len(timeline):
        errors.append(f"overlay_count mismatch: overlays={len(overlay_timing)} timeline={len(timeline)}")
    else:
        for index, (overlay, row) in enumerate(zip(overlay_timing, timeline), start=1):
            start = float(overlay.get("start", 0.0))
            end = float(overlay.get("end", 0.0))
            row_start = float(row.get("start", 0.0))
            row_end = float(row.get("end", row_start))
            if abs(start - row_start) > tolerance:
                errors.append(f"overlay_start mismatch at {index}: overlay={start:.3f}, timeline={row_start:.3f}")
            if abs(end - row_end) > tolerance:
                errors.append(f"overlay_end mismatch at {index}: overlay={end:.3f}, timeline={row_end:.3f}")
        total_timeline = sum(max(0.0, float(row.get("end", 0.0)) - float(row.get("start", 0.0))) for row in timeline)
        total_ocr = sum(max(0.0, float(segment.get("end", 0.0)) - float(segment.get("start", 0.0))) for segment in ordered_segments)
        if abs(total_timeline - total_ocr) > tolerance:
            errors.append(f"total_duration mismatch: timeline={total_timeline:.3f}, ocr={total_ocr:.3f}")
        timeline_end = max(float(row.get("end", 0.0)) for row in timeline)
        overlay_end = max((float(row.get("end", 0.0)) for row in overlay_timing), default=0.0)
        if abs(overlay_end - timeline_end) > tolerance:
            errors.append(f"final_end mismatch: overlay_end={overlay_end:.3f}, timeline_end={timeline_end:.3f}")
    return errors


def _artifact_path_exists(registry: ArtifactRegistry, key: str) -> bool:
    artifact = registry.get(key)
    return bool(artifact and artifact.type == "file" and os.path.exists(artifact.path_or_url))


def _validation_override_reason(parameters: Dict[str, Any]) -> str:
    for key in ("validation_override_reason", "render_gate_override_reason"):
        value = str((parameters or {}).get(key, "") or "").strip()
        if value:
            return value
    return ""
