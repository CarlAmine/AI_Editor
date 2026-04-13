from __future__ import annotations

import json
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from .artifacts import ArtifactRegistry
from .decision_engine import DecisionOutcome, PipelineDecision
from .executor import ExecutionContext, PipelineExecutor
from .plans import build_audio_plan, write_plan
from .runner import _save as _runner_save, run_job
from .state import apply_analysis


def build_smoke_request(job_id: Optional[str] = None) -> Dict[str, Any]:
    return {
        "primary_url": "smoke://primary",
        "sources": [
            {"label": 1, "url": "smoke://source-1"},
            {"label": 2, "url": "smoke://source-2"},
        ],
        "prompt": "Create a polished smoke-test highlight with cleaner pacing in the middle.",
        "music_mode": "original",
        "requirements_state": {
            "intent_mode": "video",
            "generation_mode": "free_generation_mode",
            "edit_mode": "scene",
            "edit_requests": ["edit: make it less cluttered in the middle"],
        },
        "job_id": job_id,
    }


class SmokeDecisionEngine:
    def __init__(self) -> None:
        self._outcomes = [
            DecisionOutcome(PipelineDecision(next_action="run_analysis", confidence=0.95, rationale="Analyze smoke sources.", parameters={})),
            DecisionOutcome(PipelineDecision(next_action="generate_plan", confidence=0.95, rationale="Generate the first draft plan.", parameters={})),
            DecisionOutcome(PipelineDecision(next_action="validate_plan", confidence=0.95, rationale="Validate the draft plan.", parameters={})),
            DecisionOutcome(PipelineDecision(next_action="revise_plan", confidence=0.9, rationale="Revise based on the validation feedback.", parameters={})),
            DecisionOutcome(PipelineDecision(next_action="validate_plan", confidence=0.95, rationale="Confirm the revised plan is safe to render.", parameters={})),
            DecisionOutcome(PipelineDecision(next_action="render_final", confidence=0.95, rationale="Render the smoke-test output.", parameters={})),
            DecisionOutcome(PipelineDecision(next_action="finish", confidence=0.95, rationale="Finish the smoke-test job.", parameters={})),
        ]

    def provider_requirements(self) -> Dict[str, bool]:
        return {"llm": False}

    def decide(self, state) -> DecisionOutcome:
        if self._outcomes:
            return self._outcomes.pop(0)
        return DecisionOutcome(
            PipelineDecision(next_action="finish", confidence=0.95, rationale="Smoke flow complete.", parameters={})
        )

    def repair_decide(self, state, *, error: str, invalid_payload: Optional[Dict[str, Any]] = None) -> DecisionOutcome:
        return DecisionOutcome(
            decision=None,
            source="repair_invalid",
            error=error,
            invalid_payload=invalid_payload,
            repair_attempted=True,
        )


class _SmokeValidator:
    def __init__(self) -> None:
        self._calls = 0

    def validate(self, plan, analysis=None, requirements=None):
        self._calls += 1
        score = 0.42 if self._calls == 1 else 0.93
        return {
            "validation_score": score,
            "warnings": [],
            "checks": {"smoke_validation": True},
            "rewrite_actions": [] if score >= 0.9 else [{"action": "tighten_middle"}],
            "recommendations": [] if score >= 0.9 else ["Reduce clutter in the middle section."],
            "validator_strategy": "smoke_validator",
        }


class SmokePipelineExecutor(PipelineExecutor):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            validator=_SmokeValidator(),
            provider_requirements={"render": False, "drive": False},
            **kwargs,
        )

    def _stage_fetch_primary(self, ctx: ExecutionContext) -> None:
        primary_path = os.path.join(ctx.dirs["media"], "primary.mp4")
        self._write_binary(primary_path, b"smoke-primary-video")
        ctx.artifacts.register_file("primary.video", primary_path, {"source": "smoke"}, "video/mp4")

    def _stage_analyze_primary(self, ctx: ExecutionContext) -> None:
        analysis = _smoke_analysis()
        summary = "Smoke analysis: intro, middle, and ending segments detected."
        analysis_path = os.path.join(ctx.dirs["job"], "analysis.json")
        summary_path = os.path.join(ctx.dirs["job"], "analysis_summary.txt")
        self._write_json(analysis_path, analysis)
        with open(summary_path, "w", encoding="utf-8") as handle:
            handle.write(summary)
        ctx.artifacts.register_file("analysis.json", analysis_path, {}, "application/json")
        ctx.artifacts.register_file("analysis.summary", summary_path, {}, "text/plain")
        apply_analysis(ctx.state, analysis, summary)

    def _stage_fetch_sources(self, ctx: ExecutionContext) -> None:
        for index in range(1, 3):
            source_path = os.path.join(ctx.dirs["media"], f"source_raw_{index:03d}.mp4")
            self._write_binary(source_path, f"smoke-source-{index}".encode("utf-8"))
            ctx.artifacts.register_file(f"sources.raw.{index}", source_path, {"backend": "smoke"}, "video/mp4")
            ctx.artifacts.register_file(f"sources.fetch.{index}", source_path, {"backend": "smoke"}, "video/mp4")
        self._refresh_source_status(ctx)

    def _stage_align_sources(self, ctx: ExecutionContext) -> None:
        for index in range(1, 3):
            artifact = ctx.artifacts.get(f"sources.raw.{index}")
            if artifact is None:
                continue
            aligned_path = os.path.join(ctx.dirs["media"], f"aligned_{index:03d}.mp4")
            shutil.copyfile(artifact.path_or_url, aligned_path)
            ctx.artifacts.register_file(f"sources.aligned.{index}", aligned_path, {"aligned": True}, "video/mp4")
            ctx.artifacts.register_file(f"sources.fetch.{index}", aligned_path, {"backend": "smoke", "aligned": True}, "video/mp4")
        self._refresh_source_status(ctx)

    def _stage_audio_plan(self, ctx: ExecutionContext) -> None:
        audio_plan = build_audio_plan(
            {
                "soundtrack_url": None,
                "use_reference_audio_bed": False,
                "mute_source_audio": False,
            },
            ctx.requirements,
        )
        ctx.state.audio_plan = audio_plan
        write_plan(ctx.dirs["job"], "audio_plan.json", audio_plan)

    def _source_durations_for_plan(self, ctx: ExecutionContext, analysis: Dict[str, Any]):
        return [2.4, 2.8]

    def _stage_shotstack_render(self, ctx: ExecutionContext) -> None:
        master_path = os.path.join(ctx.dirs["outputs"], "master_16x9.mp4")
        self._write_binary(master_path, b"smoke-render-output")
        render_url = f"https://example.test/renders/{ctx.job_id}.mp4"
        ctx.artifacts.register_file("render.master_16x9", master_path, {"provider": "smoke"}, "video/mp4")
        ctx.artifacts.register_url("render.shotstack_url", render_url, {"render_id": f"smoke-{ctx.job_id}"}, "video/mp4")
        ctx.runtime["render_result"] = {"success": True, "render_id": f"smoke-{ctx.job_id}", "url": render_url}

    def _stage_postprocess(self, ctx: ExecutionContext) -> None:
        return None

    @staticmethod
    def _write_binary(path: str, data: bytes) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(data)


def run_smoke_job(job_id: Optional[str] = None) -> Dict[str, Any]:
    resolved_job_id = job_id or f"smoke-{uuid.uuid4().hex[:8]}"
    request = build_smoke_request(job_id=resolved_job_id)
    result = run_job(
        resolved_job_id,
        request,
        decision_engine=SmokeDecisionEngine(),
        executor=SmokePipelineExecutor(save_hook=_runner_save),
    )
    job_dir = Path("tmp") / "jobs" / resolved_job_id
    artifact_manifest = job_dir / "artifacts.json"
    state_path = job_dir / "state.json"
    decision_trace_path = job_dir / "decision_trace.json"
    return {
        "job_id": resolved_job_id,
        "result": result,
        "job_dir": str(job_dir),
        "state_path": str(state_path),
        "artifacts_path": str(artifact_manifest),
        "decision_trace_path": str(decision_trace_path),
        "artifacts_exists": artifact_manifest.exists(),
        "state_exists": state_path.exists(),
        "decision_trace_exists": decision_trace_path.exists(),
    }


def main() -> None:
    payload = run_smoke_job()
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _smoke_analysis() -> Dict[str, Any]:
    return {
        "scenes": [
            {"scene_id": 1, "start_time": 0.0, "end_time": 2.4, "duration": 2.4},
            {"scene_id": 2, "start_time": 2.4, "end_time": 5.2, "duration": 2.8},
            {"scene_id": 3, "start_time": 5.2, "end_time": 7.4, "duration": 2.2},
        ],
        "segments": [
            {
                "label": "intro",
                "scene_id": 1,
                "start": 0.0,
                "end": 2.4,
                "editorial_score": 0.88,
                "hook_score": 0.74,
                "broll_score": 0.22,
                "novelty_score": 0.45,
                "visual_cluster_id": "cluster_1",
                "has_transcript": True,
            },
            {
                "label": "middle",
                "scene_id": 2,
                "start": 2.4,
                "end": 5.2,
                "editorial_score": 0.76,
                "hook_score": 0.48,
                "broll_score": 0.18,
                "novelty_score": 0.4,
                "visual_cluster_id": "cluster_2",
                "has_transcript": True,
            },
            {
                "label": "ending",
                "scene_id": 3,
                "start": 5.2,
                "end": 7.4,
                "editorial_score": 0.84,
                "hook_score": 0.58,
                "broll_score": 0.2,
                "novelty_score": 0.5,
                "visual_cluster_id": "cluster_3",
                "has_transcript": True,
            },
        ],
        "style_profile": {
            "avg_shot_length": 2.46,
            "pacing_label": "medium",
            "intro_pacing_label": "fast",
            "short_form_likelihood": 0.42,
            "text_density": 0.21,
            "ocr_density": 0.16,
            "scene_count": 3,
        },
        "keyframes": [
            {"timestamp": 0.0, "detected_text": "Big launch"},
            {"timestamp": 2.6, "detected_text": "Main message"},
            {"timestamp": 5.5, "detected_text": "Call to action"},
        ],
        "transcript": {"spans": [{"start": 0.1, "end": 6.9, "text": "Smoke transcript content."}]},
    }


if __name__ == "__main__":
    main()
