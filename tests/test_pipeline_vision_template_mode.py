import shutil
from pathlib import Path
from uuid import uuid4

from pipeline.artifacts import ArtifactRegistry
from pipeline.decision_engine import PipelineDecision
from pipeline.executor import ExecutionContext, PipelineExecutor
from pipeline.state import StageName, new_state


def _ctx() -> ExecutionContext:
    job_dir = Path("tmp") / "tests" / f"vision-template-{uuid4().hex[:8]}" / "job"
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
        "prompt": "Learn the reference edit structure and transfer it",
        "intent_mode": "video",
        "edit_mode": "scene",
        "generation_mode": "vision_template_learning",
        "vision_template": {"fps": 8.0, "size": 96, "epochs": 1, "device": "cpu", "max_seconds": None, "use_pretrained_backbone": False},
        "slot_mapping": [{"slot_id": 1, "clip_id": "clip_1"}],
        "expected_slots": 1,
    }
    state = new_state(
        "vision-template-job",
        input_summary={"primary_url": "https://example.com/ref.mp4", "sources_count": 1},
        requirements=requirements,
    )
    return ExecutionContext(
        job_id="vision-template-job",
        request_payload={
            "primary_url": "https://example.com/ref.mp4",
            "sources": [{"label": 1, "clip_id": "clip_1", "url": "https://example.com/source.mp4"}],
            "slot_mapping": [{"slot_id": 1, "clip_id": "clip_1"}],
        },
        requirements=requirements,
        dirs=dirs,
        state=state,
        artifacts=ArtifactRegistry(),
        runtime={},
    )


def test_executor_routes_vision_template_learning_through_new_stages(monkeypatch):
    ctx = _ctx()
    try:
        executor = PipelineExecutor()

        def fake_audio_plan(inner_ctx):
            inner_ctx.state.audio_plan = {"music_mode": "original"}

        def fake_train(inner_ctx):
            inner_ctx.artifacts.register_file("vision.template.json", str(Path(inner_ctx.dirs["plans"]) / "edit_template.json"), {}, "application/json")

        def fake_transfer(inner_ctx):
            inner_ctx.state.current_plan = {
                "planning_strategy": "vision_template_learning",
                "plan_validation": {"validation_score": 1.0},
            }
            inner_ctx.state.plan_validation = {"validation_score": 1.0}
            inner_ctx.state.plan_validation_score = 1.0
            inner_ctx.state.plan_needs_validation = False
            inner_ctx.state.render_spec = {
                "generation_mode": "vision_template_learning",
                "canonical_timeline": [
                    {"video_src": "local.mp4", "start": 0.0, "end": 1.0, "duration": 1.0}
                ],
            }

        monkeypatch.setattr(executor, "_stage_audio_plan", fake_audio_plan)
        monkeypatch.setattr(executor, "_stage_vision_template_train", fake_train)
        monkeypatch.setattr(executor, "_stage_vision_template_transfer", fake_transfer)

        decision = PipelineDecision(next_action="generate_plan", confidence=0.95, rationale="plan", parameters={})
        executor.execute(ctx, decision)

        assert ctx.state.stages[StageName.VISION_TEMPLATE_TRAIN.value].status.value == "SUCCEEDED"
        assert ctx.state.stages[StageName.VISION_TEMPLATE_TRANSFER.value].status.value == "SUCCEEDED"
        assert ctx.state.render_spec["canonical_timeline"][0]["duration"] == 1.0
    finally:
        shutil.rmtree(Path(ctx.dirs["job"]).parent, ignore_errors=True)


def test_semantic_edit_disabled_is_silent(monkeypatch):
    ctx = _ctx()
    ctx.requirements["semantic_edit"] = {"enabled": False}
    template_path = Path(ctx.dirs["plans"]) / "edit_template.json"
    template_path.write_text(
        '{"version":"0.1","fps":8.0,"total_duration":1.0,"slots":[],"global_style":{"avg_slot_duration":0.0,"rhythm":[],"pacing_label":"medium","dominant_transition":"cut"},"warnings":[]}',
        encoding="utf-8",
    )
    try:
        executor = PipelineExecutor()
        executor._maybe_attach_semantic_edit(ctx, str(template_path))
        assert not any(item.get("code") == "SEMANTIC_EDIT_DISABLED" for item in ctx.state.warnings)
    finally:
        shutil.rmtree(Path(ctx.dirs["job"]).parent, ignore_errors=True)
