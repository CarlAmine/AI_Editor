from pipeline.feedback import build_pipeline_assistant_feedback


def test_reference_mimic_too_few_sources_routes_to_chat():
    feedback = build_pipeline_assistant_feedback(
        error="Reference mimic requires at least 4 sources; received 1.",
        stage="RENDER_PLAN",
        requirements={"generation_mode": "reference_mimic_mode", "edit_mode": "scene"},
    )

    assert feedback["route_to_chat"] is True
    assert feedback["reason"] == "reference_mimic_too_few_sources"
    assert "Add 3 more source clips" in feedback["message"]
    assert feedback["state_patch"]["pipeline_feedback"]["required_sources"] == 4
    assert feedback["state_patch"]["pipeline_feedback"]["received_sources"] == 1


def test_shotstack_credit_error_stays_out_of_chat():
    feedback = build_pipeline_assistant_feedback(
        error=(
            "Shotstack rejected the render because the current account has 0 credits for the sandbox/stage "
            "environment (https://api.shotstack.io/stage)."
        ),
        stage="SHOTSTACK_RENDER",
        requirements={},
    )

    assert feedback["route_to_chat"] is False
    assert feedback["reason"] == "shotstack_plan_limit"
