from ai_editor.editing import EditSession
from pipeline.plans.builders import build_render_spec, build_timeline_plan


def _analysis(style_profile, segments, scenes=None):
    return {
        "scenes": scenes
        or [
            {"scene_id": 1, "start_time": 0.0, "end_time": 2.0, "duration": 2.0},
            {"scene_id": 2, "start_time": 2.0, "end_time": 5.0, "duration": 3.0},
            {"scene_id": 3, "start_time": 5.0, "end_time": 9.0, "duration": 4.0},
        ],
        "segments": segments,
        "style_profile": style_profile,
    }


def _audio_plan():
    return {
        "music_mode": "original",
        "soundtrack_url": None,
        "use_reference_audio_bed": False,
        "mute_source_audio": False,
    }


def test_supported_caption_directives_influence_render_settings():
    analysis = _analysis(
        {
            "avg_shot_length": 2.4,
            "pacing_label": "medium",
            "intro_pacing_label": "medium",
            "short_form_likelihood": 0.4,
            "text_density": 0.22,
            "ocr_density": 0.18,
        },
        [
            {"label": "intro", "scene_id": 1, "start": 0.0, "end": 2.0, "editorial_score": 0.82, "hook_score": 0.72, "broll_score": 0.12, "novelty_score": 0.42, "visual_cluster_id": "cluster_1", "has_transcript": True},
            {"label": "body", "scene_id": 2, "start": 2.1, "end": 4.4, "editorial_score": 0.79, "hook_score": 0.48, "broll_score": 0.14, "novelty_score": 0.46, "visual_cluster_id": "cluster_2", "has_transcript": True},
        ],
    )
    timeline_plan = build_timeline_plan(analysis["scenes"], [6.0], {"intent_mode": "video"}, analysis=analysis)
    patched = EditSession.from_payloads(timeline_plan, analysis=analysis, requirements={"intent_mode": "video"}).apply_instruction(
        "add more captions"
    )

    render_spec = build_render_spec(
        timeline_plan=patched,
        overlay_plan={
            "overlays": [{"timestamp": 0.0, "duration": 1.0, "text": "A", "position": "bottom"}],
            "text_segments": [{"start": 0.0, "end": 1.0, "text": "A"}, {"start": 1.1, "end": 2.0, "text": "B"}],
            "overlay_script": None,
            "timing_mode": "ocr_keyframe",
            "montage_mode": False,
        },
        audio_plan=_audio_plan(),
        requirements={"intent_mode": "video", "edit_mode": "scene"},
    )

    assert render_spec["caption_density_mode"] == "dense"
    assert any(item["operation"] == "increase_captions" for item in render_spec["style_directives_applied"])
    assert len(render_spec["overlay_plan"]) >= 2


def test_supported_overlay_directives_reduce_density_and_change_policy():
    analysis = _analysis(
        {
            "avg_shot_length": 2.4,
            "pacing_label": "medium",
            "intro_pacing_label": "medium",
            "short_form_likelihood": 0.38,
            "text_density": 0.2,
            "ocr_density": 0.12,
        },
        [
            {"label": "intro", "scene_id": 1, "start": 0.0, "end": 2.0, "editorial_score": 0.82, "hook_score": 0.68, "broll_score": 0.14, "novelty_score": 0.44, "visual_cluster_id": "cluster_1", "has_transcript": True},
            {"label": "middle", "scene_id": 2, "start": 2.1, "end": 4.6, "editorial_score": 0.79, "hook_score": 0.48, "broll_score": 0.16, "novelty_score": 0.51, "visual_cluster_id": "cluster_2", "has_transcript": True},
            {"label": "ending", "scene_id": 3, "start": 4.7, "end": 7.2, "editorial_score": 0.77, "hook_score": 0.39, "broll_score": 0.18, "novelty_score": 0.53, "visual_cluster_id": "cluster_3", "has_transcript": True},
        ],
    )
    timeline_plan = build_timeline_plan(analysis["scenes"], [8.0], {"intent_mode": "video"}, analysis=analysis)
    patched = EditSession.from_payloads(timeline_plan, analysis=analysis, requirements={"intent_mode": "video"}).apply_instruction(
        "make it less cluttered in the middle"
    )

    overlays = [
        {"timestamp": 0.0, "duration": 1.0, "text": "One", "position": "bottom"},
        {"timestamp": 1.1, "duration": 1.0, "text": "Two", "position": "bottom"},
        {"timestamp": 2.2, "duration": 1.0, "text": "Three", "position": "center"},
        {"timestamp": 3.3, "duration": 1.0, "text": "Four", "position": "bottom"},
    ]
    render_spec = build_render_spec(
        timeline_plan=patched,
        overlay_plan={"overlays": overlays, "text_segments": [], "overlay_script": None, "timing_mode": "ocr_keyframe", "montage_mode": False},
        audio_plan=_audio_plan(),
        requirements={"intent_mode": "video", "edit_mode": "scene"},
    )

    assert render_spec["caption_density_mode"] == "sparse"
    assert render_spec["text_placement_policy"] == "top_safe"
    assert len(render_spec["overlay_plan"]) < len(overlays)
    assert all(item["position"] == "top" for item in render_spec["overlay_plan"])


def test_unsupported_directives_remain_deferred():
    analysis = _analysis(
        {
            "avg_shot_length": 2.0,
            "pacing_label": "medium",
            "intro_pacing_label": "medium",
            "short_form_likelihood": 0.35,
            "text_density": 0.2,
            "ocr_density": 0.12,
        },
        [
            {"label": "intro", "scene_id": 1, "start": 0.0, "end": 2.0, "editorial_score": 0.82, "hook_score": 0.68, "broll_score": 0.14, "novelty_score": 0.44, "visual_cluster_id": "cluster_1", "has_transcript": True},
            {"label": "body", "scene_id": 2, "start": 2.1, "end": 4.4, "editorial_score": 0.79, "hook_score": 0.48, "broll_score": 0.16, "novelty_score": 0.51, "visual_cluster_id": "cluster_2", "has_transcript": True},
        ],
    )
    timeline_plan = build_timeline_plan(analysis["scenes"], [6.0], {"intent_mode": "video"}, analysis=analysis)
    patched = EditSession.from_payloads(timeline_plan, analysis=analysis, requirements={"intent_mode": "video"}).apply_instruction(
        "change caption style to neon glitch"
    )

    render_spec = build_render_spec(
        timeline_plan=patched,
        overlay_plan={"overlays": [], "text_segments": [], "overlay_script": None, "timing_mode": "ocr_keyframe", "montage_mode": False},
        audio_plan=_audio_plan(),
        requirements={"intent_mode": "video", "edit_mode": "scene"},
    )

    assert render_spec["caption_style_preset"] == "default"
    assert any(item["operation"] == "change_caption_style" for item in render_spec["deferred_style_directives"])


def test_one_shot_flow_remains_compatible_without_directives():
    timeline_plan = {
        "scene_durations": [2.0, 3.0],
        "source_durations": [5.0],
        "intent_mode": "video",
        "edit_mode": "scene",
        "planning_strategy": "legacy_scene_duration_fallback",
        "target_pacing": "medium",
        "target_segment_duration": None,
        "opening_segment_ids": [],
        "support_segment_ids": [],
        "selected_segments": [],
        "support_segments": [],
        "rejected_segments": [],
        "style_profile_snapshot": {},
        "plan_validation": {},
        "planning_debug": {},
    }

    render_spec = build_render_spec(
        timeline_plan=timeline_plan,
        overlay_plan={"overlays": [], "text_segments": [], "overlay_script": None, "timing_mode": "ocr_keyframe", "montage_mode": False},
        audio_plan=_audio_plan(),
        requirements={"intent_mode": "video", "edit_mode": "scene"},
    )

    assert render_spec["caption_density_mode"] == "normal"
    assert render_spec["caption_style_preset"] == "default"
    assert render_spec["deferred_style_directives"] == []


def test_patched_plan_render_compatibility_preserves_supported_style_settings():
    analysis = _analysis(
        {
            "avg_shot_length": 2.2,
            "pacing_label": "medium",
            "intro_pacing_label": "medium",
            "short_form_likelihood": 0.42,
            "text_density": 0.2,
            "ocr_density": 0.15,
        },
        [
            {"label": "intro", "scene_id": 1, "start": 0.0, "end": 2.0, "editorial_score": 0.82, "hook_score": 0.68, "broll_score": 0.14, "novelty_score": 0.44, "visual_cluster_id": "cluster_1", "has_transcript": True},
            {"label": "body", "scene_id": 2, "start": 2.1, "end": 4.4, "editorial_score": 0.79, "hook_score": 0.48, "broll_score": 0.16, "novelty_score": 0.51, "visual_cluster_id": "cluster_2", "has_transcript": True},
        ],
    )
    timeline_plan = build_timeline_plan(analysis["scenes"], [6.0], {"intent_mode": "video"}, analysis=analysis)
    patched = EditSession.from_payloads(timeline_plan, analysis=analysis, requirements={"intent_mode": "video"}).apply_instruction(
        "change caption style to bold minimal"
    )

    render_spec = build_render_spec(
        timeline_plan=patched,
        overlay_plan={"overlays": [{"timestamp": 0.0, "duration": 1.0, "text": "A", "position": "bottom"}], "text_segments": [], "overlay_script": None, "timing_mode": "ocr_keyframe", "montage_mode": False},
        audio_plan=_audio_plan(),
        requirements={"intent_mode": "video", "edit_mode": "scene"},
    )

    assert render_spec["timeline_plan"] == patched
    assert render_spec["caption_style_preset"] == "bold_minimal"
    assert any(item["operation"] == "change_caption_style" for item in render_spec["style_directives_applied"])
