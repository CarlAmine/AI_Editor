import pytest

from pipeline.decision_engine import DecisionOutcome, PipelineDecision, PipelineDecisionEngine
from pipeline.provider_errors import ProviderFailure
from pipeline.state import new_state


def _state() -> object:
    return new_state(
        "job-decide",
        input_summary={"primary_url": "https://example.com/ref.mp4", "sources_count": 1},
        requirements={"prompt": "Make a short product edit"},
    )


def test_decision_schema_rejects_unknown_action():
    with pytest.raises(Exception):
        PipelineDecision(
            next_action="invent_new_step",
            confidence=0.6,
            rationale="invalid",
            parameters={},
        )


def test_decision_engine_returns_invalid_outcome_on_bad_json():
    engine = PipelineDecisionEngine(
        json_client=lambda *args, **kwargs: {
            "next_action": "invented",
            "confidence": 0.4,
            "rationale": "bad",
            "parameters": {},
        }
    )

    outcome = engine.decide(_state())

    assert isinstance(outcome, DecisionOutcome)
    assert outcome.source == "invalid"
    assert outcome.decision is None
    assert outcome.error


def test_decision_engine_can_repair_invalid_output_once():
    payloads = [
        {"next_action": "invented", "confidence": 0.4, "rationale": "bad", "parameters": {}},
        {"next_action": "validate_plan", "confidence": 0.77, "rationale": "repair", "parameters": {}},
    ]

    def _json_client(*args, **kwargs):
        return payloads.pop(0)

    engine = PipelineDecisionEngine(json_client=_json_client)
    state = _state()

    invalid = engine.decide(state)
    repaired = engine.repair_decide(
        state,
        error=invalid.error or "invalid",
        invalid_payload=invalid.invalid_payload,
    )

    assert invalid.decision is None
    assert repaired.source == "repair"
    assert repaired.decision is not None
    assert repaired.decision.next_action == "validate_plan"


def test_decision_engine_surfaces_model_provider_failure():
    def _json_client(*args, **kwargs):
        raise ProviderFailure(
            provider="model_provider",
            code="MODEL_PROVIDER_TIMEOUT",
            user_message="The AI controller timed out.",
            detail={"attempt": 1},
            retryable=True,
        )

    engine = PipelineDecisionEngine(json_client=_json_client)

    outcome = engine.decide(_state())

    assert outcome.decision is None
    assert outcome.source == "provider_error"
    assert outcome.failure_code == "MODEL_PROVIDER_TIMEOUT"
    assert outcome.user_message == "The AI controller timed out."
