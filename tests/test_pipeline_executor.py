from pathlib import Path
import shutil
from uuid import uuid4

from ai_editor.analysis.analysis_schema import EffectType, MotionCurve, MotionEffect, MotionEffectManifest
from pipeline.artifacts import ArtifactRegistry
from pipeline.decision_engine import PipelineDecision
from pipeline.executor import ExecutionContext, PipelineExecutor, _validate_reference_timeline
from pipeline.provider_errors import ProviderFailure
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


def test_get_edit_operations_from_state_reads_requirements_dict_entries():
    ctx = _ctx()
    try:
        executor = PipelineExecutor()
        ctx.requirements["parsed_operations"] = [
            {
                "operation": "remove_segment",
                "target": "shot_2",
                "scope": "global",
                "segment_target": "shot_2",
            }
        ]

        operations = executor._get_edit_operations_from_state(ctx)

        assert len(operations) == 1
        assert operations[0].operation == "remove_segment"
        assert operations[0].target == "shot_2"
    finally:
        shutil.rmtree(Path(ctx.dirs["job"]).parent, ignore_errors=True)


def test_stage_render_plan_uses_reference_timeline_for_style_transfer(monkeypatch):
    ctx = _ctx()
    try:
        executor = PipelineExecutor()
        ctx.requirements["generation_mode"] = "reference_style_transfer"
        ctx.state.requirements["generation_mode"] = "reference_style_transfer"
        ctx.state.current_plan = {
            "planning_strategy": "test_plan",
            "selected_segments": [],
            "support_segments": [],
        }
        ctx.state.overlay_plan = {"overlays": [], "text_segments": [], "warnings": []}
        ctx.state.audio_plan = {"music_mode": "original"}

        called = {"reference": 0}

        def fake_reference_timeline(_ctx, _analysis, _overlay_plan, _audio_plan, _source_keys):
            called["reference"] += 1
            return (
                [{"scene_id": 1, "start": 0.0, "end": 2.0, "duration": 2.0, "video_src": "clip.mp4"}],
                [{"index": 1, "start": 0.0, "end": 2.0, "text": ""}],
                {"preserved_total_duration": 2.0},
                [],
            )

        monkeypatch.setattr(executor, "_build_reference_render_timeline", fake_reference_timeline)
        monkeypatch.setattr(executor, "_source_keys_for_generation", lambda _ctx: ["sources.fetch.1"])
        monkeypatch.setattr(executor, "_source_durations_for_plan", lambda _ctx, _analysis: [])
        monkeypatch.setattr(executor, "_apply_motion_effects_to_render_spec", lambda _ctx, spec: spec)
        monkeypatch.setattr(executor, "_write_plan_bundle", lambda *args, **kwargs: None)
        monkeypatch.setattr(executor, "_record_overlay_warnings", lambda *args, **kwargs: None)

        executor._stage_render_plan(ctx)

        assert called["reference"] == 1
        assert ctx.state.render_spec["canonical_timeline"][0]["scene_id"] == 1
    finally:
        shutil.rmtree(Path(ctx.dirs["job"]).parent, ignore_errors=True)


def test_apply_motion_effects_to_render_spec_updates_timeline_for_style_transfer(monkeypatch):
    ctx = _ctx()
    try:
        executor = PipelineExecutor()
        ctx.requirements["generation_mode"] = "reference_style_transfer"
        ctx.state.requirements["generation_mode"] = "reference_style_transfer"

        clip_path = Path(ctx.dirs["media"]) / "clip.mp4"
        clip_path.write_bytes(b"fake")
        manifest_path = Path(ctx.dirs["job"]) / "motion_effects.json"
        manifest = MotionEffectManifest(
            video_path="ref.mp4",
            fps=25.0,
            total_frames=10,
            effects=[
                MotionEffect(
                    shot_index=0,
                    effect_type=EffectType.SHAKE,
                    onset_frac=0.0,
                    offset_frac=1.0,
                    intensity=0.8,
                    curve=MotionCurve(dx_norm=[0.02], dy_norm=[0.01]),
                )
            ],
        )
        manifest_path.write_text("{}", encoding="utf-8")
        ctx.state.motion_effects_path = str(manifest_path)

        monkeypatch.setattr(executor, "_load_json_if_exists", lambda _path: manifest.to_dict())
        monkeypatch.setattr(
            "pipeline.executor.MotionEffectApplier.apply_to_clip",
            lambda self, clip_path, shot_index, manifest, output_path: output_path,
        )

        render_spec = {
            "canonical_timeline": [
                {"scene_id": 1, "video_src": str(clip_path), "videoSrc": str(clip_path)}
            ]
        }

        updated = executor._apply_motion_effects_to_render_spec(ctx, render_spec)

        assert updated["canonical_timeline"][0]["video_src"].endswith("_stylized.mp4")
        assert updated["edit_summary"]["motion_effect_clips_stylized"] == 1
    finally:
        shutil.rmtree(Path(ctx.dirs["job"]).parent, ignore_errors=True)


def test_stage_shotstack_render_writes_debug_error_details(monkeypatch):
    ctx = _ctx()
    try:
        executor = PipelineExecutor()
        ctx.requirements["generation_mode"] = "reference_style_transfer"
        ctx.state.requirements["generation_mode"] = "reference_style_transfer"

        clip_path = Path(ctx.dirs["media"]) / "clip.mp4"
        clip_path.write_bytes(b"clip")
        ctx.state.render_spec = {
            "generation_mode": "reference_style_transfer",
            "edit_mode": "scene",
            "canonical_timeline": [
                {"scene_id": 1, "video_src": str(clip_path), "duration": 2.0, "start": 0.0, "end": 2.0}
            ],
            "overlay_plan": [],
            "resolution": "1080x1920",
            "music_mode": "original",
        }
        ctx.state.analysis = {"scenes": [{"scene_id": 1, "duration": 2.0, "start_time": 0.0, "end_time": 2.0}]}
        ctx.state.analysis_available = True

        monkeypatch.setenv("SHOTSTACK_KEY", "test-key")
        monkeypatch.setattr(
            "pipeline.executor._upload_assets_for_shotstack",
            lambda job_id, local_paths: [
                {"local_path": local_paths[0], "public_url": "https://example.com/clip.mp4"}
            ],
        )
        captured = {}

        def fake_render(**kwargs):
            captured.update(kwargs)
            return {
                "success": False,
                "error": "invalid payload",
                "status": "failed",
                "debug": {"status_code": 400, "response_json": {"message": "bad payload"}},
            }

        monkeypatch.setattr("ai_editor.shotstack_renderer.create_and_render_video", fake_render)

        try:
            executor._stage_shotstack_render(ctx)
            assert False, "expected ProviderFailure"
        except ProviderFailure as exc:
            assert exc.code == "RENDER_PROVIDER_FAILED"
            assert exc.detail["status_code"] == 400
            assert exc.detail["shotstack_debug_path"].endswith("shotstack_error.json")
            assert exc.detail["operation"] == "shotstack_render.create_and_render_video"

        assert captured["debug_shotstack_error_path"].endswith("shotstack_error.json")
        assert captured["debug_shotstack_payload_path"].endswith("shotstack_request_payload.json")

        debug_path = Path(ctx.dirs["debug"]) / "shotstack_error.json"
        assert debug_path.exists()
        assert "bad payload" in debug_path.read_text(encoding="utf-8")
    finally:
        shutil.rmtree(Path(ctx.dirs["job"]).parent, ignore_errors=True)


def test_stage_shotstack_render_backfills_debug_file_when_renderer_raises(monkeypatch):
    ctx = _ctx()
    try:
        executor = PipelineExecutor()
        ctx.requirements["generation_mode"] = "reference_style_transfer"
        ctx.state.requirements["generation_mode"] = "reference_style_transfer"

        clip_path = Path(ctx.dirs["media"]) / "clip.mp4"
        clip_path.write_bytes(b"clip")
        ctx.state.render_spec = {
            "generation_mode": "reference_style_transfer",
            "edit_mode": "scene",
            "canonical_timeline": [
                {"scene_id": 1, "video_src": str(clip_path), "duration": 2.0, "start": 0.0, "end": 2.0}
            ],
            "overlay_plan": [],
            "resolution": "1080x1920",
            "music_mode": "original",
        }
        ctx.state.analysis = {"scenes": [{"scene_id": 1, "duration": 2.0, "start_time": 0.0, "end_time": 2.0}]}
        ctx.state.analysis_available = True

        monkeypatch.setenv("SHOTSTACK_KEY", "test-key")
        monkeypatch.setattr(
            "pipeline.executor._upload_assets_for_shotstack",
            lambda job_id, local_paths: [
                {"local_path": local_paths[0], "public_url": "https://example.com/clip.mp4"}
            ],
        )
        monkeypatch.setattr(
            "ai_editor.shotstack_renderer.create_and_render_video",
            lambda **kwargs: (_ for _ in ()).throw(RuntimeError("kaboom")),
        )

        try:
            executor._stage_shotstack_render(ctx)
            assert False, "expected ProviderFailure"
        except ProviderFailure as exc:
            assert exc.detail["shotstack_debug_path"].endswith("shotstack_error.json")
            assert exc.detail["short_error_message"]

        debug_path = Path(ctx.dirs["debug"]) / "shotstack_error.json"
        assert debug_path.exists()
        assert "kaboom" in debug_path.read_text(encoding="utf-8")
    finally:
        shutil.rmtree(Path(ctx.dirs["job"]).parent, ignore_errors=True)


def test_reference_overlay_validation_allows_multiple_overlays_per_scene():
    analysis = {
        "scenes": [
            {"scene_id": 1, "start_time": 0.0, "end_time": 2.0, "duration": 2.0},
            {"scene_id": 2, "start_time": 2.0, "end_time": 4.0, "duration": 2.0},
        ]
    }
    timeline = [
        {"start": 0.0, "end": 2.0, "duration": 2.0},
        {"start": 2.0, "end": 4.0, "duration": 2.0},
    ]
    overlay_timing = [
        {"start": 0.1, "end": 0.6},
        {"start": 0.8, "end": 1.4},
        {"start": 2.1, "end": 2.7},
    ]

    errors = _validate_reference_timeline(
        analysis=analysis,
        timeline=timeline,
        overlay_timing=overlay_timing,
        use_reference_audio=False,
        reference_audio_duration=None,
    )

    assert errors == []
