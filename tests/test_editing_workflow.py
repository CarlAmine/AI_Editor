from ai_editor.editing import EditSession, InstructionParser, PlanPatcher
from pipeline.plans.builders import build_render_spec, build_timeline_plan


def _analysis(style_profile, segments, scenes=None):
    return {
        "scenes": scenes
        or [
            {"scene_id": 1, "start_time": 0.0, "end_time": 2.0, "duration": 2.0},
            {"scene_id": 2, "start_time": 2.0, "end_time": 5.0, "duration": 3.0},
            {"scene_id": 3, "start_time": 5.0, "end_time": 9.0, "duration": 4.0},
            {"scene_id": 4, "start_time": 9.0, "end_time": 12.0, "duration": 3.0},
        ],
        "segments": segments,
        "style_profile": style_profile,
    }


def test_instruction_parser_maps_common_edit_requests():
    parser = InstructionParser()

    opening_ops = parser.parse("make the opening faster")
    repetition_ops = parser.parse("remove repetitive shots")
    broll_ops = parser.parse("use more B-roll in the middle")
    hook_ops = parser.parse("replace the intro with a stronger hook")
    clutter_ops = parser.parse("make it less cluttered")

    assert any(op.operation == "increase_pacing" and op.scope == "opening" for op in opening_ops)
    assert any(op.operation == "reduce_repetition" for op in repetition_ops)
    assert any(op.operation == "increase_broll" and op.scope == "middle" for op in broll_ops)
    assert any(op.operation == "promote_hook" for op in hook_ops)
    assert any(op.operation == "replace_segment" and op.target == "opening" for op in hook_ops)
    assert any(op.operation == "decrease_broll" for op in clutter_ops)


def test_instruction_parser_supports_richer_targets_and_operations():
    parser = InstructionParser()

    ending_ops = parser.parse("make the ending shorter")
    source_ops = parser.parse("use more clips from source b")
    caption_ops = parser.parse("add more captions")
    clutter_middle_ops = parser.parse("make it less cluttered in the middle")
    remove_end_ops = parser.parse("remove that repetitive part near the end")
    product_ops = parser.parse("put more product shots after the hook")

    assert any(op.operation == "shorten_ending" and op.scope == "ending" for op in ending_ops)
    assert any(op.operation == "prioritize_source" and op.source_target == "b" for op in source_ops)
    assert any(op.operation == "increase_captions" for op in caption_ops)
    assert any(op.operation == "increase_overlay_density" for op in caption_ops)
    assert any(op.operation == "decrease_overlay_density" and op.scope == "middle" for op in clutter_middle_ops)
    assert any(op.operation == "remove_segment" and op.scope == "ending" for op in remove_end_ops)
    assert any(op.operation == "increase_broll" and op.metadata.get("desired_content") == "product_shots" for op in product_ops)


def test_instruction_parser_understands_normalized_edit_request_prefixes():
    parser = InstructionParser()

    prefixed_edit_ops = parser.parse("edit: make it less cluttered in the middle")
    prefixed_remove_ops = parser.parse("remove: remove the ending")

    assert any(op.operation == "decrease_overlay_density" and op.scope == "middle" for op in prefixed_edit_ops)
    assert any(op.operation == "remove_segment" and op.scope == "ending" for op in prefixed_remove_ops)


def test_promote_hook_strengthens_existing_plan_opener():
    analysis = _analysis(
        {
            "avg_shot_length": 2.5,
            "pacing_label": "medium",
            "intro_pacing_label": "medium",
            "short_form_likelihood": 0.35,
            "text_density": 0.22,
            "ocr_density": 0.14,
        },
        [
            {"label": "weak_intro", "scene_id": 1, "start": 0.0, "end": 2.5, "editorial_score": 0.86, "hook_score": 0.28, "broll_score": 0.1, "novelty_score": 0.2, "visual_cluster_id": "cluster_1", "has_transcript": True},
            {"label": "strong_hook", "scene_id": 2, "start": 2.6, "end": 4.3, "editorial_score": 0.8, "hook_score": 0.95, "broll_score": 0.14, "novelty_score": 0.72, "visual_cluster_id": "cluster_2", "has_transcript": True, "source": "b"},
            {"label": "story", "scene_id": 3, "start": 4.4, "end": 6.8, "editorial_score": 0.76, "hook_score": 0.42, "broll_score": 0.18, "novelty_score": 0.48, "visual_cluster_id": "cluster_3", "has_transcript": True, "source": "a"},
        ],
    )
    plan = build_timeline_plan(analysis["scenes"], [10.0], {"intent_mode": "video"}, analysis=analysis)
    plan["selected_segments"] = [dict(seg) for seg in plan["selected_segments"]]
    if len(plan["selected_segments"]) >= 2:
        plan["selected_segments"][0], plan["selected_segments"][1] = plan["selected_segments"][1], plan["selected_segments"][0]
        plan["selected_segments"][0]["planner_role"] = "opening_hook"
        plan["selected_segments"][1]["planner_role"] = "primary_narrative"
        plan["opening_segment_ids"] = [seg["label"] for seg in plan["selected_segments"][:2]]
    session = EditSession.from_payloads(timeline_plan=plan, analysis=analysis, requirements={"intent_mode": "video"})

    patched = session.apply_instruction("replace the intro with a stronger hook")

    assert patched["selected_segments"][0]["label"] == "strong_hook"
    assert patched["plan_patch"]["operation_count"] >= 1


def test_reduce_repetition_lowers_visual_repetition():
    analysis = _analysis(
        {
            "avg_shot_length": 2.1,
            "pacing_label": "fast",
            "intro_pacing_label": "fast",
            "short_form_likelihood": 0.8,
            "text_density": 0.25,
            "ocr_density": 0.15,
        },
        [
            {"label": "rep_a", "scene_id": 1, "start": 0.0, "end": 1.8, "editorial_score": 0.84, "hook_score": 0.9, "broll_score": 0.1, "novelty_score": 0.15, "visual_cluster_id": "cluster_1", "has_transcript": True},
            {"label": "rep_b", "scene_id": 2, "start": 1.9, "end": 3.5, "editorial_score": 0.8, "hook_score": 0.58, "broll_score": 0.14, "novelty_score": 0.12, "visual_cluster_id": "cluster_1", "has_transcript": True},
            {"label": "distinct_c", "scene_id": 3, "start": 3.6, "end": 5.2, "editorial_score": 0.79, "hook_score": 0.5, "broll_score": 0.16, "novelty_score": 0.88, "visual_cluster_id": "cluster_2", "has_transcript": True},
        ],
    )
    plan = build_timeline_plan(analysis["scenes"], [8.0], {"intent_mode": "shorts"}, analysis=analysis)
    patcher = PlanPatcher()
    parser = InstructionParser()

    patched = patcher.apply_operations(plan, parser.parse("remove repetitive shots"), analysis=analysis, requirements={"intent_mode": "shorts"})

    opening_clusters = [segment["visual_cluster_id"] for segment in patched["selected_segments"][:2]]
    assert opening_clusters != ["cluster_1", "cluster_1"]
    assert patched["planning_debug"]["edit_patch_ran"] is True


def test_increase_broll_adds_more_support_to_existing_plan():
    analysis = _analysis(
        {
            "avg_shot_length": 2.9,
            "pacing_label": "medium",
            "intro_pacing_label": "medium",
            "short_form_likelihood": 0.42,
            "text_density": 0.16,
            "ocr_density": 0.1,
        },
        [
            {"label": "story_a", "scene_id": 1, "start": 0.0, "end": 2.6, "editorial_score": 0.84, "hook_score": 0.71, "broll_score": 0.2, "novelty_score": 0.45, "visual_cluster_id": "cluster_1", "has_transcript": True, "source": "a"},
            {"label": "story_b", "scene_id": 2, "start": 2.8, "end": 5.0, "editorial_score": 0.8, "hook_score": 0.5, "broll_score": 0.2, "novelty_score": 0.41, "visual_cluster_id": "cluster_2", "has_transcript": True, "source": "b"},
            {"label": "support_mid", "scene_id": 3, "start": 5.1, "end": 6.3, "editorial_score": 0.35, "hook_score": 0.18, "broll_score": 0.9, "novelty_score": 0.82, "visual_cluster_id": "cluster_3", "has_ocr": True},
            {"label": "support_end", "scene_id": 4, "start": 8.9, "end": 10.5, "editorial_score": 0.33, "hook_score": 0.2, "broll_score": 0.92, "novelty_score": 0.86, "visual_cluster_id": "cluster_4", "has_ocr": True},
        ],
    )
    plan = build_timeline_plan(analysis["scenes"], [10.0], {"intent_mode": "video"}, analysis=analysis)
    base_support_count = len(plan["support_segments"])

    patched = EditSession.from_payloads(plan, analysis=analysis, requirements={"intent_mode": "video"}).apply_instruction(
        "use more B-roll in the middle"
    )

    assert len(patched["support_segments"]) >= base_support_count
    assert any(seg["label"] == "support_mid" for seg in patched["support_segments"])


def test_time_window_targeted_patching_affects_middle_only():
    analysis = _analysis(
        {
            "avg_shot_length": 2.8,
            "pacing_label": "medium",
            "intro_pacing_label": "medium",
            "short_form_likelihood": 0.4,
            "text_density": 0.2,
            "ocr_density": 0.1,
        },
        [
            {"label": "open", "scene_id": 1, "start": 0.0, "end": 2.0, "editorial_score": 0.82, "hook_score": 0.7, "broll_score": 0.14, "novelty_score": 0.4, "visual_cluster_id": "cluster_1", "has_transcript": True},
            {"label": "mid_a", "scene_id": 2, "start": 2.1, "end": 4.4, "editorial_score": 0.8, "hook_score": 0.45, "broll_score": 0.16, "novelty_score": 0.42, "visual_cluster_id": "cluster_2", "has_transcript": True},
            {"label": "mid_b", "scene_id": 3, "start": 4.5, "end": 6.8, "editorial_score": 0.78, "hook_score": 0.43, "broll_score": 0.18, "novelty_score": 0.44, "visual_cluster_id": "cluster_3", "has_transcript": True},
            {"label": "end", "scene_id": 4, "start": 6.9, "end": 9.0, "editorial_score": 0.77, "hook_score": 0.39, "broll_score": 0.19, "novelty_score": 0.46, "visual_cluster_id": "cluster_4", "has_transcript": True},
        ],
    )
    plan = build_timeline_plan(analysis["scenes"], [9.0], {"intent_mode": "video"}, analysis=analysis)

    patched = EditSession.from_payloads(plan, analysis=analysis, requirements={"intent_mode": "video"}).apply_instruction(
        "make it less cluttered in the middle"
    )

    assert any(op["operation"] == "decrease_overlay_density" for op in patched["edit_directives"])
    assert patched["edit_directives"][-1]["scope"] == "middle"


def test_source_prioritization_reorders_existing_plan():
    analysis = _analysis(
        {
            "avg_shot_length": 2.7,
            "pacing_label": "medium",
            "intro_pacing_label": "medium",
            "short_form_likelihood": 0.34,
            "text_density": 0.14,
            "ocr_density": 0.08,
        },
        [
            {"label": "source_a_open", "scene_id": 1, "start": 0.0, "end": 2.4, "editorial_score": 0.84, "hook_score": 0.72, "broll_score": 0.14, "novelty_score": 0.42, "visual_cluster_id": "cluster_1", "has_transcript": True, "source": "a"},
            {"label": "source_b_hook", "scene_id": 2, "start": 2.5, "end": 4.3, "editorial_score": 0.82, "hook_score": 0.69, "broll_score": 0.16, "novelty_score": 0.44, "visual_cluster_id": "cluster_2", "has_transcript": True, "source": "b"},
            {"label": "source_b_story", "scene_id": 3, "start": 4.4, "end": 6.8, "editorial_score": 0.79, "hook_score": 0.46, "broll_score": 0.18, "novelty_score": 0.47, "visual_cluster_id": "cluster_3", "has_transcript": True, "source": "b"},
        ],
    )
    plan = build_timeline_plan(analysis["scenes"], [8.0], {"intent_mode": "video"}, analysis=analysis)

    patched = EditSession.from_payloads(plan, analysis=analysis, requirements={"intent_mode": "video"}).apply_instruction(
        "use more clips from source b"
    )

    assert patched["selected_segments"][0]["source"] == "b"


def test_ending_shortening_and_middle_trimming_work_together():
    analysis = _analysis(
        {
            "avg_shot_length": 2.5,
            "pacing_label": "medium",
            "intro_pacing_label": "medium",
            "short_form_likelihood": 0.33,
            "text_density": 0.18,
            "ocr_density": 0.1,
        },
        [
            {"label": "s1", "scene_id": 1, "start": 0.0, "end": 2.0, "editorial_score": 0.82, "hook_score": 0.7, "broll_score": 0.12, "novelty_score": 0.4, "visual_cluster_id": "cluster_1", "has_transcript": True},
            {"label": "s2", "scene_id": 2, "start": 2.1, "end": 4.2, "editorial_score": 0.8, "hook_score": 0.52, "broll_score": 0.15, "novelty_score": 0.43, "visual_cluster_id": "cluster_2", "has_transcript": True},
            {"label": "s3", "scene_id": 3, "start": 4.3, "end": 6.4, "editorial_score": 0.78, "hook_score": 0.44, "broll_score": 0.17, "novelty_score": 0.46, "visual_cluster_id": "cluster_3", "has_transcript": True},
            {"label": "s4", "scene_id": 4, "start": 6.5, "end": 8.8, "editorial_score": 0.76, "hook_score": 0.38, "broll_score": 0.19, "novelty_score": 0.48, "visual_cluster_id": "cluster_4", "has_transcript": True},
        ],
    )
    plan = build_timeline_plan(analysis["scenes"], [9.0], {"intent_mode": "video"}, analysis=analysis)
    session = EditSession.from_payloads(plan, analysis=analysis, requirements={"intent_mode": "video"})
    original_count = len(plan["selected_segments"])
    patched = session.apply_instruction("trim the middle")
    patched = session.apply_instruction("make the ending shorter")

    assert len(patched["selected_segments"]) <= original_count - 1
    assert len(session.history) == 2


def test_unsupported_style_operations_are_preserved_as_metadata():
    analysis = _analysis(
        {
            "avg_shot_length": 2.2,
            "pacing_label": "medium",
            "intro_pacing_label": "medium",
            "short_form_likelihood": 0.4,
            "text_density": 0.22,
            "ocr_density": 0.12,
        },
        [
            {"label": "intro", "scene_id": 1, "start": 0.0, "end": 2.0, "editorial_score": 0.82, "hook_score": 0.7, "broll_score": 0.12, "novelty_score": 0.4, "visual_cluster_id": "cluster_1", "has_transcript": True},
            {"label": "body", "scene_id": 2, "start": 2.1, "end": 4.4, "editorial_score": 0.8, "hook_score": 0.5, "broll_score": 0.15, "novelty_score": 0.44, "visual_cluster_id": "cluster_2", "has_transcript": True},
        ],
    )
    plan = build_timeline_plan(analysis["scenes"], [6.0], {"intent_mode": "video"}, analysis=analysis)

    patched = EditSession.from_payloads(plan, analysis=analysis, requirements={"intent_mode": "video"}).apply_instruction(
        "change caption style to bold minimal"
    )

    assert any(op["operation"] == "change_caption_style" for op in patched["edit_directives"])
    assert any(op["operation"] == "change_caption_style" for op in patched["plan_patch"]["deferred_operations"])


def test_revision_history_tracks_snapshots_and_validation():
    analysis = _analysis(
        {
            "avg_shot_length": 2.4,
            "pacing_label": "medium",
            "intro_pacing_label": "medium",
            "short_form_likelihood": 0.38,
            "text_density": 0.18,
            "ocr_density": 0.1,
        },
        [
            {"label": "intro", "scene_id": 1, "start": 0.0, "end": 2.0, "editorial_score": 0.82, "hook_score": 0.68, "broll_score": 0.14, "novelty_score": 0.44, "visual_cluster_id": "cluster_1", "has_transcript": True},
            {"label": "middle", "scene_id": 2, "start": 2.1, "end": 4.6, "editorial_score": 0.79, "hook_score": 0.48, "broll_score": 0.16, "novelty_score": 0.51, "visual_cluster_id": "cluster_2", "has_transcript": True},
            {"label": "ending", "scene_id": 3, "start": 4.7, "end": 7.2, "editorial_score": 0.77, "hook_score": 0.39, "broll_score": 0.18, "novelty_score": 0.53, "visual_cluster_id": "cluster_3", "has_transcript": True},
        ],
    )
    timeline_plan = build_timeline_plan(analysis["scenes"], [8.0], {"intent_mode": "video"}, analysis=analysis)
    session = EditSession.from_payloads(timeline_plan, analysis=analysis, requirements={"intent_mode": "video"})
    session.apply_instruction("add more captions")

    entry = session.history[0]
    assert entry["revision_index"] == 1
    assert "timestamp" in entry
    assert "before" in entry and "after" in entry
    assert "diff" in entry
    assert "validation_before" in entry and "validation_after" in entry


def test_render_compatibility_is_preserved_after_patch():
    analysis = _analysis(
        {
            "avg_shot_length": 2.4,
            "pacing_label": "medium",
            "intro_pacing_label": "medium",
            "short_form_likelihood": 0.38,
            "text_density": 0.18,
            "ocr_density": 0.1,
        },
        [
            {"label": "intro", "scene_id": 1, "start": 0.0, "end": 2.0, "editorial_score": 0.82, "hook_score": 0.68, "broll_score": 0.14, "novelty_score": 0.44, "visual_cluster_id": "cluster_1", "has_transcript": True},
            {"label": "middle", "scene_id": 2, "start": 2.1, "end": 4.6, "editorial_score": 0.79, "hook_score": 0.48, "broll_score": 0.16, "novelty_score": 0.51, "visual_cluster_id": "cluster_2", "has_transcript": True},
            {"label": "ending", "scene_id": 3, "start": 4.7, "end": 7.2, "editorial_score": 0.77, "hook_score": 0.39, "broll_score": 0.18, "novelty_score": 0.53, "visual_cluster_id": "cluster_3", "has_transcript": True},
        ],
    )
    timeline_plan = build_timeline_plan(analysis["scenes"], [8.0], {"intent_mode": "video"}, analysis=analysis)
    patched = EditSession.from_payloads(timeline_plan, analysis=analysis, requirements={"intent_mode": "video"}).apply_instruction(
        "shorten the ending"
    )
    render_spec = build_render_spec(
        timeline_plan=patched,
        overlay_plan={"overlays": [], "overlay_script": None, "timing_mode": "ocr_keyframe", "montage_mode": False},
        audio_plan={"music_mode": "original", "soundtrack_url": None, "use_reference_audio_bed": False, "mute_source_audio": False},
        requirements={"intent_mode": "video", "edit_mode": "scene"},
    )

    assert "resolution" in render_spec
    assert render_spec["timeline_plan"] == patched
    assert "plan_patch" in patched
    assert "plan_validation" in render_spec
    assert "edit_directives" in patched
