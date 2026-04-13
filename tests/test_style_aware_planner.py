from ai_editor.planning.style_aware_planner import StyleAwarePlanner
from pipeline.plans.builders import build_render_spec, build_timeline_plan


def _analysis_with_segments(style_profile, segments, scenes=None):
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


def test_planner_uses_high_hook_segment_early():
    analysis = _analysis_with_segments(
        {
            "avg_shot_length": 2.2,
            "pacing_label": "fast",
            "intro_pacing_label": "fast",
            "short_form_likelihood": 0.82,
            "text_density": 0.4,
            "ocr_density": 0.25,
        },
        [
            {
                "label": "seg_mid",
                "start": 4.0,
                "end": 6.0,
                "editorial_score": 0.75,
                "hook_score": 0.55,
                "broll_score": 0.2,
                "novelty_score": 0.28,
                "visual_cluster_id": "cluster_2",
                "has_transcript": True,
                "has_ocr": False,
            },
            {
                "label": "seg_hook",
                "start": 0.5,
                "end": 2.0,
                "editorial_score": 0.74,
                "hook_score": 0.95,
                "broll_score": 0.25,
                "novelty_score": 0.83,
                "visual_cluster_id": "cluster_1",
                "has_transcript": True,
                "has_ocr": True,
            },
        ],
    )

    plan = build_timeline_plan(analysis["scenes"], [8.0, 8.0], {"intent_mode": "video"}, analysis=analysis)

    assert plan["planning_strategy"] == "style_aware_fast"
    assert plan["opening_segment_ids"][0] == "seg_hook"
    assert plan["selected_segments"][0]["planner_role"] == "opening_hook"
    assert plan["planning_debug"]["strategy_label"] == "hook_first_fast"
    assert plan["plan_validation"]["validation_score"] >= 0.0
    assert plan["planning_debug"]["validation_ran"] is True


def test_planner_pacing_shifts_between_fast_and_slow_styles():
    fast_analysis = _analysis_with_segments(
        {
            "avg_shot_length": 1.4,
            "pacing_label": "fast",
            "intro_pacing_label": "fast",
            "short_form_likelihood": 0.88,
            "text_density": 0.5,
            "ocr_density": 0.3,
        },
        [{"label": "fast_1", "start": 0.0, "end": 2.0, "editorial_score": 0.8, "hook_score": 0.7, "broll_score": 0.2, "novelty_score": 0.7, "visual_cluster_id": "cluster_1"}],
    )
    slow_analysis = _analysis_with_segments(
        {
            "avg_shot_length": 6.5,
            "pacing_label": "slow",
            "intro_pacing_label": "slow",
            "short_form_likelihood": 0.18,
            "text_density": 0.1,
            "ocr_density": 0.05,
        },
        [{"label": "slow_1", "start": 0.0, "end": 7.0, "editorial_score": 0.7, "hook_score": 0.3, "broll_score": 0.25, "novelty_score": 0.25, "visual_cluster_id": "cluster_1"}],
    )

    fast_plan = build_timeline_plan(fast_analysis["scenes"], [8.0], {"intent_mode": "shorts"}, analysis=fast_analysis)
    slow_plan = build_timeline_plan(slow_analysis["scenes"], [8.0], {"intent_mode": "video"}, analysis=slow_analysis)

    assert fast_plan["target_pacing"] == "fast"
    assert slow_plan["target_pacing"] == "slow"
    assert fast_plan["target_segment_duration"] < slow_plan["target_segment_duration"]
    assert fast_plan["target_segment_count"] > slow_plan["target_segment_count"]


def test_high_broll_segment_becomes_support_candidate():
    planner = StyleAwarePlanner()
    analysis = _analysis_with_segments(
        {
            "avg_shot_length": 3.0,
            "pacing_label": "medium",
            "intro_pacing_label": "medium",
            "short_form_likelihood": 0.42,
            "text_density": 0.2,
            "ocr_density": 0.15,
        },
        [
            {
                "label": "primary_story",
                "start": 0.0,
                "end": 3.0,
                "editorial_score": 0.82,
                "hook_score": 0.72,
                "broll_score": 0.25,
                "novelty_score": 0.35,
                "visual_cluster_id": "cluster_1",
                "has_transcript": True,
                "has_ocr": False,
            },
            {
                "label": "visual_cutaway",
                "start": 3.1,
                "end": 4.8,
                "editorial_score": 0.38,
                "hook_score": 0.22,
                "broll_score": 0.92,
                "novelty_score": 0.88,
                "visual_cluster_id": "cluster_2",
                "has_transcript": False,
                "has_ocr": True,
            },
        ],
    )

    plan = planner.build_plan(analysis, [10.0], {"intent_mode": "video"})

    assert any(seg["label"] == "primary_story" for seg in plan["selected_segments"])
    assert any(seg["label"] == "visual_cutaway" for seg in plan["support_segments"])
    assert all(seg["label"] != "visual_cutaway" for seg in plan["selected_segments"])
    assert plan["planning_debug"]["support_segment_ids"] == ["visual_cutaway"]


def test_dense_short_form_style_pushes_shorter_and_more_numerous_segments():
    planner = StyleAwarePlanner()
    fast_dense_analysis = _analysis_with_segments(
        {
            "avg_shot_length": 1.7,
            "pacing_label": "medium",
            "intro_pacing_label": "medium",
            "short_form_likelihood": 0.76,
            "text_density": 0.62,
            "ocr_density": 0.41,
        },
        [
            {"label": "seg_1", "scene_id": 1, "start": 0.0, "end": 1.8, "editorial_score": 0.66, "hook_score": 0.72, "broll_score": 0.15, "novelty_score": 0.81, "visual_cluster_id": "cluster_1", "has_transcript": True},
            {"label": "seg_2", "scene_id": 2, "start": 1.9, "end": 3.7, "editorial_score": 0.7, "hook_score": 0.64, "broll_score": 0.12, "novelty_score": 0.75, "visual_cluster_id": "cluster_2", "has_transcript": True},
            {"label": "seg_3", "scene_id": 3, "start": 3.8, "end": 5.5, "editorial_score": 0.69, "hook_score": 0.59, "broll_score": 0.18, "novelty_score": 0.7, "visual_cluster_id": "cluster_3", "has_transcript": True, "has_ocr": True},
            {"label": "seg_4", "scene_id": 4, "start": 5.6, "end": 7.4, "editorial_score": 0.65, "hook_score": 0.54, "broll_score": 0.14, "novelty_score": 0.68, "visual_cluster_id": "cluster_4", "has_transcript": True},
            {"label": "seg_5", "scene_id": 5, "start": 7.5, "end": 9.2, "editorial_score": 0.64, "hook_score": 0.52, "broll_score": 0.16, "novelty_score": 0.66, "visual_cluster_id": "cluster_5", "has_transcript": True},
        ],
    )
    slow_light_analysis = _analysis_with_segments(
        {
            "avg_shot_length": 6.2,
            "pacing_label": "slow",
            "intro_pacing_label": "slow",
            "short_form_likelihood": 0.18,
            "text_density": 0.08,
            "ocr_density": 0.04,
        },
        fast_dense_analysis["segments"],
    )

    dense_plan = planner.build_plan(fast_dense_analysis, [10.0], {"intent_mode": "video"})
    slow_plan = planner.build_plan(slow_light_analysis, [10.0], {"intent_mode": "video"})

    assert dense_plan["density_profile"] == "dense"
    assert dense_plan["target_pacing"] == "fast"
    assert dense_plan["target_segment_duration"] < slow_plan["target_segment_duration"]
    assert dense_plan["target_segment_count"] > slow_plan["target_segment_count"]


def test_planner_filters_low_score_and_redundant_segments_deterministically():
    planner = StyleAwarePlanner()
    analysis = _analysis_with_segments(
        {
            "avg_shot_length": 3.1,
            "pacing_label": "medium",
            "intro_pacing_label": "fast",
            "short_form_likelihood": 0.42,
            "text_density": 0.21,
            "ocr_density": 0.11,
        },
        [
            {"label": "hook_a", "scene_id": 1, "start": 0.0, "end": 2.0, "editorial_score": 0.82, "hook_score": 0.9, "broll_score": 0.12, "novelty_score": 0.78, "visual_cluster_id": "cluster_1", "has_transcript": True},
            {"label": "hook_a_duplicate", "scene_id": 1, "start": 0.3, "end": 2.1, "editorial_score": 0.8, "hook_score": 0.85, "broll_score": 0.12, "novelty_score": 0.1, "visual_cluster_id": "cluster_1", "has_transcript": True},
            {"label": "mid_story", "scene_id": 2, "start": 3.0, "end": 5.0, "editorial_score": 0.75, "hook_score": 0.5, "broll_score": 0.18, "novelty_score": 0.61, "visual_cluster_id": "cluster_2", "has_transcript": True},
            {"label": "weak_filler", "scene_id": 3, "start": 5.2, "end": 6.4, "editorial_score": 0.05, "hook_score": 0.08, "broll_score": 0.1, "novelty_score": 0.09, "visual_cluster_id": "cluster_3"},
        ],
    )

    plan = planner.build_plan(analysis, [8.0], {"intent_mode": "video"})

    selected_ids = [seg["label"] for seg in plan["selected_segments"]]
    assert "hook_a" in selected_ids
    assert "hook_a_duplicate" not in selected_ids
    assert "weak_filler" in plan["planning_debug"]["rejected_low_score_ids"]


def test_weak_opening_gets_improved_by_validation_rewrite():
    analysis = _analysis_with_segments(
        {
            "avg_shot_length": 2.6,
            "pacing_label": "medium",
            "intro_pacing_label": "medium",
            "short_form_likelihood": 0.32,
            "text_density": 0.22,
            "ocr_density": 0.1,
        },
        [
            {
                "label": "weak_open",
                "scene_id": 1,
                "start": 0.0,
                "end": 2.8,
                "editorial_score": 0.84,
                "hook_score": 0.22,
                "broll_score": 0.12,
                "novelty_score": 0.12,
                "visual_cluster_id": "cluster_1",
                "has_transcript": True,
            },
            {
                "label": "strong_hook",
                "scene_id": 2,
                "start": 3.0,
                "end": 5.0,
                "editorial_score": 0.78,
                "hook_score": 0.95,
                "broll_score": 0.2,
                "novelty_score": 0.93,
                "visual_cluster_id": "cluster_2",
                "has_transcript": True,
            },
        ],
    )

    plan = build_timeline_plan(analysis["scenes"], [8.0], {"intent_mode": "video"}, analysis=analysis)

    assert plan["selected_segments"][0]["label"] == "strong_hook"
    assert any(action["action"] == "replace_opening_with_best_hook" for action in plan["planning_debug"]["rewrite_actions_applied"])
    assert any(w["code"] == "OPENING_HOOK_WEAK" for w in plan["plan_validation"]["pre_rewrite"]["warnings"])


def test_redundant_same_scene_picks_are_flagged_or_reduced():
    analysis = _analysis_with_segments(
        {
            "avg_shot_length": 2.4,
            "pacing_label": "medium",
            "intro_pacing_label": "fast",
            "short_form_likelihood": 0.5,
            "text_density": 0.33,
            "ocr_density": 0.14,
        },
        [
            {"label": "scene1_a", "scene_id": 1, "start": 0.0, "end": 1.7, "editorial_score": 0.86, "hook_score": 0.88, "broll_score": 0.1, "novelty_score": 0.74, "visual_cluster_id": "cluster_1", "has_transcript": True},
            {"label": "scene1_b", "scene_id": 1, "start": 1.8, "end": 3.4, "editorial_score": 0.84, "hook_score": 0.52, "broll_score": 0.12, "novelty_score": 0.12, "visual_cluster_id": "cluster_1", "has_transcript": True},
            {"label": "scene2", "scene_id": 2, "start": 3.5, "end": 5.2, "editorial_score": 0.8, "hook_score": 0.45, "broll_score": 0.14, "novelty_score": 0.68, "visual_cluster_id": "cluster_2", "has_transcript": True},
            {"label": "scene3", "scene_id": 3, "start": 5.3, "end": 7.0, "editorial_score": 0.77, "hook_score": 0.41, "broll_score": 0.16, "novelty_score": 0.66, "visual_cluster_id": "cluster_3", "has_transcript": True},
        ],
    )

    plan = build_timeline_plan(analysis["scenes"], [8.0], {"intent_mode": "video"}, analysis=analysis)

    scene_ids = [seg.get("scene_id") for seg in plan["selected_segments"]]
    assert scene_ids.count(1) <= 1
    assert any(action["action"] == "drop_redundant_primary_indices" for action in plan["plan_validation"]["pre_rewrite"]["rewrite_actions"])


def test_support_heavy_plan_is_rebalanced():
    analysis = _analysis_with_segments(
        {
            "avg_shot_length": 1.8,
            "pacing_label": "fast",
            "intro_pacing_label": "fast",
            "short_form_likelihood": 0.84,
            "text_density": 0.48,
            "ocr_density": 0.38,
        },
        [
            {"label": "narrative_1", "scene_id": 1, "start": 0.0, "end": 1.4, "editorial_score": 0.84, "hook_score": 0.91, "broll_score": 0.12, "novelty_score": 0.8, "visual_cluster_id": "cluster_1", "has_transcript": True},
            {"label": "narrative_2", "scene_id": 2, "start": 1.6, "end": 3.0, "editorial_score": 0.8, "hook_score": 0.68, "broll_score": 0.18, "novelty_score": 0.73, "visual_cluster_id": "cluster_2", "has_transcript": True},
            {"label": "support_1", "scene_id": 3, "start": 3.1, "end": 4.0, "editorial_score": 0.32, "hook_score": 0.18, "broll_score": 0.96, "novelty_score": 0.88, "visual_cluster_id": "cluster_3", "has_ocr": True},
            {"label": "support_2", "scene_id": 4, "start": 4.1, "end": 5.0, "editorial_score": 0.31, "hook_score": 0.16, "broll_score": 0.94, "novelty_score": 0.18, "visual_cluster_id": "cluster_3", "has_ocr": True},
            {"label": "support_3", "scene_id": 5, "start": 5.1, "end": 5.9, "editorial_score": 0.29, "hook_score": 0.14, "broll_score": 0.93, "novelty_score": 0.16, "visual_cluster_id": "cluster_3", "has_ocr": True},
            {"label": "support_4", "scene_id": 6, "start": 6.0, "end": 6.8, "editorial_score": 0.28, "hook_score": 0.12, "broll_score": 0.91, "novelty_score": 0.81, "visual_cluster_id": "cluster_4", "has_ocr": True},
        ],
    )

    plan = build_timeline_plan(analysis["scenes"], [8.0], {"intent_mode": "shorts"}, analysis=analysis)

    assert len(plan["support_segments"]) <= 2
    assert any(action["action"] == "trim_support_segments" for action in plan["planning_debug"]["rewrite_actions_applied"])


def test_fast_style_profiles_flag_overly_slow_plan():
    analysis = _analysis_with_segments(
        {
            "avg_shot_length": 1.6,
            "pacing_label": "fast",
            "intro_pacing_label": "fast",
            "short_form_likelihood": 0.86,
            "text_density": 0.55,
            "ocr_density": 0.33,
        },
        [
            {"label": "slowish_1", "scene_id": 1, "start": 0.0, "end": 4.6, "editorial_score": 0.86, "hook_score": 0.91, "broll_score": 0.1, "novelty_score": 0.62, "visual_cluster_id": "cluster_1", "has_transcript": True},
            {"label": "slowish_2", "scene_id": 2, "start": 4.8, "end": 9.2, "editorial_score": 0.82, "hook_score": 0.62, "broll_score": 0.15, "novelty_score": 0.57, "visual_cluster_id": "cluster_2", "has_transcript": True},
        ],
    )

    plan = build_timeline_plan(analysis["scenes"], [12.0], {"intent_mode": "shorts"}, analysis=analysis)

    assert any(w["code"] == "PACING_MISMATCH" for w in plan["plan_validation"]["pre_rewrite"]["warnings"])
    assert plan["target_segment_duration"] < plan["plan_validation"]["pre_rewrite"]["checks"]["pacing_consistency"]["detail"]["average_selected_duration"]
    assert any(action["action"] == "tighten_target_duration" for action in plan["planning_debug"]["rewrite_actions_applied"])


def test_repetitive_adjacent_visual_picks_get_flagged_and_rewritten():
    analysis = _analysis_with_segments(
        {
            "avg_shot_length": 2.2,
            "pacing_label": "fast",
            "intro_pacing_label": "fast",
            "short_form_likelihood": 0.78,
            "text_density": 0.3,
            "ocr_density": 0.18,
        },
        [
            {"label": "open_a", "scene_id": 1, "start": 0.0, "end": 1.8, "editorial_score": 0.87, "hook_score": 0.93, "broll_score": 0.14, "novelty_score": 0.18, "visual_cluster_id": "cluster_1", "has_transcript": True},
            {"label": "open_b_same", "scene_id": 2, "start": 1.9, "end": 3.4, "editorial_score": 0.82, "hook_score": 0.61, "broll_score": 0.16, "novelty_score": 0.14, "visual_cluster_id": "cluster_1", "has_transcript": True},
            {"label": "open_c_distinct", "scene_id": 3, "start": 3.5, "end": 5.0, "editorial_score": 0.79, "hook_score": 0.58, "broll_score": 0.18, "novelty_score": 0.84, "visual_cluster_id": "cluster_2", "has_transcript": True},
        ],
    )

    plan = build_timeline_plan(analysis["scenes"], [8.0], {"intent_mode": "shorts"}, analysis=analysis)

    assert any(w["code"] == "VISUAL_DIVERSITY_LOW" for w in plan["plan_validation"]["pre_rewrite"]["warnings"])
    assert [seg["visual_cluster_id"] for seg in plan["selected_segments"][:2]] != ["cluster_1", "cluster_1"]
    assert any(action["action"] == "swap_in_visual_contrast" for action in plan["planning_debug"]["rewrite_actions_applied"])


def test_support_candidates_with_higher_novelty_are_preferred():
    analysis = _analysis_with_segments(
        {
            "avg_shot_length": 3.0,
            "pacing_label": "medium",
            "intro_pacing_label": "medium",
            "short_form_likelihood": 0.36,
            "text_density": 0.16,
            "ocr_density": 0.12,
        },
        [
            {"label": "story", "scene_id": 1, "start": 0.0, "end": 2.6, "editorial_score": 0.84, "hook_score": 0.71, "broll_score": 0.18, "novelty_score": 0.42, "visual_cluster_id": "cluster_1", "has_transcript": True},
            {"label": "support_same", "scene_id": 2, "start": 2.7, "end": 4.1, "editorial_score": 0.34, "hook_score": 0.18, "broll_score": 0.9, "novelty_score": 0.12, "visual_cluster_id": "cluster_1", "has_ocr": True},
            {"label": "support_distinct", "scene_id": 3, "start": 4.2, "end": 5.7, "editorial_score": 0.35, "hook_score": 0.2, "broll_score": 0.88, "novelty_score": 0.86, "visual_cluster_id": "cluster_2", "has_ocr": True},
        ],
    )

    plan = build_timeline_plan(analysis["scenes"], [8.0], {"intent_mode": "video"}, analysis=analysis)

    assert any(seg["label"] == "support_distinct" for seg in plan["support_segments"])
    assert all(seg["label"] != "support_same" for seg in plan["support_segments"])


def test_render_spec_preserves_backward_compatibility_with_additive_planner_fields():
    analysis = _analysis_with_segments(
        {
            "avg_shot_length": 2.0,
            "pacing_label": "fast",
            "intro_pacing_label": "fast",
            "short_form_likelihood": 0.8,
            "text_density": 0.4,
            "ocr_density": 0.2,
        },
        [{"label": "seg_1", "start": 0.0, "end": 2.0, "editorial_score": 0.7, "hook_score": 0.8, "broll_score": 0.2}],
    )
    timeline_plan = build_timeline_plan(analysis["scenes"], [7.0], {"intent_mode": "video"}, analysis=analysis)
    render_spec = build_render_spec(
        timeline_plan=timeline_plan,
        overlay_plan={"overlays": [], "overlay_script": None, "timing_mode": "ocr_keyframe", "montage_mode": False},
        audio_plan={"music_mode": "original", "soundtrack_url": None, "use_reference_audio_bed": False, "mute_source_audio": False},
        requirements={"intent_mode": "video", "edit_mode": "scene"},
    )

    assert "resolution" in render_spec
    assert render_spec["planning_strategy"] == timeline_plan["planning_strategy"]
    assert render_spec["selected_segments"] == timeline_plan["selected_segments"]
    assert render_spec["overlay_plan"] == []
    assert render_spec["planning_debug"] == timeline_plan["planning_debug"]
    assert render_spec["plan_validation"] == timeline_plan["plan_validation"]
