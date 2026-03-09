from pipeline.plans.builders import build_overlay_plan


def test_explicit_script_overrides_ocr_in_montage():
    analysis = {
        "scenes": [{"start_time": 0.0, "end_time": 20.9}],
        "keyframes": [
            {"timestamp": 3.4, "detected_text": "10 MANDY"},
            {"timestamp": 5.2, "detected_text": "MEEPLE"},
        ],
    }
    requirements = {
        "edit_requests": [
            "add overlay texts: Top 10 Best nature in the world. 10. Japan, 9. Korea, 8. Norway, 7. Iceland, 6. Lebanon, 5. Turkey, 4. Canada, 3. Russia, 2. China, 1. Indonesia"
        ],
        "user_requests": [],
    }
    plan = build_overlay_plan(
        analysis=analysis,
        requirements=requirements,
        summary="",
        render_duration=18.0,
        analysis_duration=20.9,
        montage_mode=True,
    )
    texts = [x.get("text", "") for x in plan["overlays"]]
    assert any("Japan" in t for t in texts)
    assert not any("MANDY" in t.upper() for t in texts)
    assert plan.get("timing_mode") == "clip_anchored"
    assert any(w.get("code") == "OVERLAY_SCRIPT_USED" for w in plan.get("warnings", []))


def test_ocr_used_when_no_script():
    analysis = {
        "scenes": [{"start_time": 0.0, "end_time": 6.0}],
        "keyframes": [
            {"timestamp": 0.0, "detected_text": "TOP 10"},
            {"timestamp": 3.0, "detected_text": "NEXT"},
        ],
    }
    plan = build_overlay_plan(
        analysis=analysis,
        requirements={"edit_requests": [], "user_requests": []},
        summary="",
        render_duration=6.0,
        analysis_duration=6.0,
        montage_mode=False,
    )
    texts = [x.get("text", "") for x in plan["overlays"]]
    assert any("TOP 10" in t for t in texts)
    assert plan.get("timing_mode") == "ocr_keyframe"


def test_edit_mode_ocr_uses_ocr_timeline_without_scene_split():
    analysis = {
        "scenes": [
            {"start_time": 0.0, "end_time": 4.9},
            {"start_time": 5.2, "end_time": 10.0},
        ],
        "keyframes": [
            {"timestamp": 0.0, "detected_text": "HELLO"},
            {"timestamp": 8.0, "detected_text": "WORLD"},
        ],
    }
    plan = build_overlay_plan(
        analysis=analysis,
        requirements={"edit_mode": "ocr", "edit_requests": [], "user_requests": []},
        summary="",
        render_duration=10.0,
        analysis_duration=10.0,
        montage_mode=False,
    )
    assert plan.get("timing_mode") == "ocr_timeline"
    segments = plan.get("text_segments") or []
    assert len(segments) == 2
    assert abs(float(segments[0]["start"]) - 0.0) < 1e-6
    assert abs(float(segments[0]["end"]) - 8.0) < 1e-6


def test_edit_mode_scene_keeps_scene_split_behavior():
    analysis = {
        "scenes": [
            {"start_time": 0.0, "end_time": 4.9},
            {"start_time": 5.2, "end_time": 10.0},
        ],
        "keyframes": [
            {"timestamp": 0.0, "detected_text": "HELLO"},
            {"timestamp": 8.0, "detected_text": "WORLD"},
        ],
    }
    plan = build_overlay_plan(
        analysis=analysis,
        requirements={"edit_mode": "scene", "edit_requests": [], "user_requests": []},
        summary="",
        render_duration=10.0,
        analysis_duration=10.0,
        montage_mode=False,
    )
    segments = plan.get("text_segments") or []
    # Scene mode keeps existing scene-boundary splitting.
    assert len(segments) == 3
    assert abs(float(segments[0]["start"]) - 0.0) < 1e-6
    assert abs(float(segments[0]["end"]) - 4.9) < 1e-6
    assert abs(float(segments[1]["start"]) - 5.2) < 1e-6
    assert abs(float(segments[1]["end"]) - 8.0) < 1e-6
