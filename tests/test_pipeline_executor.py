from pathlib import Path
import shutil
from uuid import uuid4

from pipeline.artifacts import ArtifactRegistry
from pipeline.decision_engine import PipelineDecision
from pipeline.executor import ExecutionContext, PipelineExecutor
from pipeline.state import apply_plan_validation, new_state


def _analysis() -> dict:
    return {
        "scenes": [
            {"scene_id": 1, "start_time": 0.0, "end_time": 2.0, "duration": 2.0},
            {"scene_id": 2, "start_time": 2.0, "end_time": 4.4, "duration": 2.4},
            {"scene_id": 3, "start_time": 4.4, "end_time": 7.0, "duration": 2.6},
        ],
        "segments": [
            {
                "label": "intro",
                "scene_id": 1,
                "start": 0.0,
                "end": 2.0,
                "editorial_score": 0.82,
                "hook_score": 0.7,
                "broll_score": 0.12,
                "novelty_score": 0.4,
                "visual_cluster_id": "cluster_1",
                "has_transcript": True,
            },
            {
                "label": "middle",
                "scene_id": 2,
                "start": 2.1,
                "end": 4.6,
                "editorial_score": 0.79,
                "hook_score": 0.48,
                "broll_score": 0.16,
                "novelty_score": 0.5,
                "visual_cluster_id": "cluster_2",
                "has_transcript": True,
            },
            {
                "label": "ending",
                "scene_id": 3,
                "start": 4.7,
                "end": 7.0,
                "editorial_score": 0.76,
                "hook_score": 0.38,
                "broll_score": 0.2,
                "novelty_score": 0.46,
                "visual_cluster_id": "cluster_3",
                "has_transcript": True,
            },
        ],
        "style_profile": {
            "avg_shot_length": 2.4,
            "pacing_label": "medium",
            "intro_pacing_label": "medium",
            "short_form_likelihood": 0.38,
            "text_density": 0.18,
            "ocr_density": 0.1,
            "scene_count": 3,
        },
        "keyframes": [
            {"timestamp": 0.0, "detected_text": "Limited offer"},
            {"timestamp": 2.1, "detected_text": "Limited offer"},
            {"timestamp": 4.7, "detected_text": "Shop now"},
        ],
    }


def _ctx() -> ExecutionContext:
    job_dir = Path("tmp") / "tests" / f"executor-{uuid4().hex[:8]}" / "job"
    dirs = {
        "job": str(job_dir),
        "plans": str(job_dir / "plans"),
        "media": str(job_dir / "media"),
        "outputs": str(job_dir / "outputs"),
        "logs": str(job_dir / "logs"),
        "debug": str(job_dir / "debug"),
    }
    for path in dirs.values():
        Path(path).mkdir(parents=True, exist_ok=True)

    requirements = {
        "prompt": "Make it less cluttered in the middle",
        "intent_mode": "video",
        "edit_mode": "scene",
        "generation_mode": "free_generation_mode",
        "edit_requests": ["edit: make it less cluttered in the middle"],
    }
    state = new_state(
        "executor-job",
        input_summary={"primary_url": "https://example.com/ref.mp4", "sources_count": 1},
        requirements=requirements,
    )
    state.analysis_available = True
    state.analysis = _analysis()
    state.analysis_summary = "analysis ready"
    return ExecutionContext(
        job_id="executor-job",
        request_payload={"primary_url": "https://example.com/ref.mp4", "sources": []},
        requirements=requirements,
        dirs=dirs,
        state=state,
        artifacts=ArtifactRegistry(),
        runtime={},
    )

def test_generate_plan_can_run_twice_without_double_applying_edits():
    ctx = _ctx()
    try:
        executor = PipelineExecutor()

        executor._generate_plan_bundle(ctx)
        first_plan = dict(ctx.state.current_plan)

        executor._generate_plan_bundle(ctx)
        second_plan = dict(ctx.state.current_plan)

        assert len(first_plan.get("edit_directives", [])) == 1
        assert len(second_plan.get("edit_directives", [])) == 1
        assert second_plan.get("edit_directives") == first_plan.get("edit_directives")
        assert second_plan.get("plan_patch", {}).get("applied_requests") == [
            "edit: make it less cluttered in the middle"
        ]
    finally:
        shutil.rmtree(Path(ctx.dirs["job"]).parent, ignore_errors=True)


def test_revise_plan_can_run_twice_without_duplicating_edit_directives():
    ctx = _ctx()
    try:
        executor = PipelineExecutor()
        executor._generate_plan_bundle(ctx)
        apply_plan_validation(
            ctx.state,
            {
                "validation_score": 0.35,
                "warnings": [],
                "checks": {},
                "rewrite_actions": [],
                "recommendations": [],
            },
        )

        decision = PipelineDecision(next_action="revise_plan", confidence=0.9, rationale="revise", parameters={})
        executor._handle_revise_plan(ctx, decision)
        first_revised = dict(ctx.state.current_plan)

        executor._handle_revise_plan(ctx, decision)
        second_revised = dict(ctx.state.current_plan)

        assert len(first_revised.get("edit_directives", [])) == 1
        assert len(second_revised.get("edit_directives", [])) == 1
        assert second_revised.get("edit_directives") == first_revised.get("edit_directives")
        assert second_revised.get("plan_patch", {}).get("applied_requests") == [
            "edit: make it less cluttered in the middle"
        ]
    finally:
        shutil.rmtree(Path(ctx.dirs["job"]).parent, ignore_errors=True)
