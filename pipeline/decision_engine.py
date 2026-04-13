from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, Literal, Optional, Sequence

from pydantic import BaseModel, Field, ValidationError

from ai_editor.ai_client import chat_json
from .provider_errors import ProviderFailure

from .state import JobState, build_decision_state_snapshot

AllowedAction = Literal[
    "run_analysis",
    "generate_plan",
    "revise_plan",
    "validate_plan",
    "render_preview",
    "render_final",
    "request_user_input",
    "abort_job",
    "finish",
]

ALLOWED_ACTIONS: Sequence[AllowedAction] = (
    "run_analysis",
    "generate_plan",
    "revise_plan",
    "validate_plan",
    "render_preview",
    "render_final",
    "request_user_input",
    "abort_job",
    "finish",
)


class PipelineDecision(BaseModel):
    """Single bounded controller decision produced by the model."""

    next_action: AllowedAction
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=1, max_length=280)
    parameters: Dict[str, Any] = Field(default_factory=dict)


@dataclass
class DecisionOutcome:
    decision: Optional[PipelineDecision]
    source: str = "model"
    error: Optional[str] = None
    invalid_payload: Optional[Dict[str, Any]] = None
    repair_attempted: bool = False
    failure_code: Optional[str] = None
    user_message: Optional[str] = None
    debug_details: Optional[Dict[str, Any]] = None


class PipelineDecisionEngine:
    """LLM-backed controller that picks the next allowed pipeline action."""

    def __init__(
        self,
        *,
        json_client: Optional[
            Callable[[list[dict[str, Any]], float, int, Optional[str]], Optional[Dict[str, Any]]]
        ] = None,
        preferred_provider: Optional[str] = None,
        minimum_validation_score: float = 0.74,
        max_revision_attempts: int = 3,
    ) -> None:
        self._json_client = json_client or self._default_json_client
        self._uses_model_provider = json_client is None
        self.preferred_provider = preferred_provider
        self.minimum_validation_score = minimum_validation_score
        self.max_revision_attempts = max_revision_attempts

    def provider_requirements(self) -> Dict[str, bool]:
        return {"llm": self._uses_model_provider}

    def decide(self, state: JobState) -> DecisionOutcome:
        return self._decide(state, repair=False)

    def repair_decide(
        self,
        state: JobState,
        *,
        error: str,
        invalid_payload: Optional[Dict[str, Any]] = None,
    ) -> DecisionOutcome:
        return self._decide(
            state,
            repair=True,
            invalid_error=error,
            invalid_payload=invalid_payload,
        )

    def _decide(
        self,
        state: JobState,
        *,
        repair: bool,
        invalid_error: Optional[str] = None,
        invalid_payload: Optional[Dict[str, Any]] = None,
    ) -> DecisionOutcome:
        messages = self._build_messages(
            state,
            repair=repair,
            invalid_error=invalid_error,
            invalid_payload=invalid_payload,
        )
        payload: Optional[Dict[str, Any]] = None
        try:
            payload = self._json_client(
                messages,
                0.0 if repair else 0.1,
                500 if repair else 700,
                self.preferred_provider,
            )
            if payload is None:
                raise ValueError("model returned no JSON decision")
            decision = _validate_model(PipelineDecision, payload)
            return DecisionOutcome(
                decision=decision,
                source="repair" if repair else "model",
                repair_attempted=repair,
            )
        except ProviderFailure as exc:
            return DecisionOutcome(
                decision=None,
                source="provider_error",
                error=exc.user_message,
                repair_attempted=repair,
                failure_code=exc.code,
                user_message=exc.user_message,
                debug_details=exc.to_error_detail(),
            )
        except Exception as exc:
            return DecisionOutcome(
                decision=None,
                source="repair_invalid" if repair else "invalid",
                error=str(exc),
                invalid_payload=payload,
                repair_attempted=repair,
            )

    def _build_messages(
        self,
        state: JobState,
        *,
        repair: bool = False,
        invalid_error: Optional[str] = None,
        invalid_payload: Optional[Dict[str, Any]] = None,
    ) -> list[dict[str, str]]:
        snapshot = build_decision_state_snapshot(state)
        schema_text = json.dumps(_model_schema(PipelineDecision), ensure_ascii=False, indent=2)
        repair_suffix = ""
        if repair:
            repair_suffix = (
                "\n\nRepair instructions:\n"
                "- The previous controller output was invalid and must be repaired.\n"
                f"- Validation error: {invalid_error or 'unknown error'}\n"
                f"- Previous invalid payload: {json.dumps(invalid_payload or {}, ensure_ascii=False)}\n"
                "- Return one repaired JSON object that exactly matches the schema.\n"
                "- Do not explain the repair. Output JSON only."
            )
        user_content = (
            "Current workflow goal:\n"
            f"{state.user_goal or state.requirements.get('prompt', '')}\n\n"
            "Current pipeline state summary:\n"
            f"{json.dumps(snapshot, ensure_ascii=False, indent=2)}\n\n"
            "Allowed actions:\n"
            f"{json.dumps(list(ALLOWED_ACTIONS), ensure_ascii=False)}\n\n"
            "Decision rules:\n"
            "- Choose exactly one next action from the allowed list.\n"
            "- Prefer validate_plan or revise_plan before any render action when the plan is weak or stale.\n"
            "- Do not ask for user input unless the workflow is blocked on missing information or repeated revisions are exhausted.\n"
            "- Abort only when the material is too poor, state is unrecoverable, or retries are exhausted.\n"
            "- Never invent new actions.\n"
            "- Provide action parameters only when deterministic execution needs them.\n\n"
            "Return strict JSON matching this schema:\n"
            f"{schema_text}"
            f"{repair_suffix}"
        )
        return [
            {
                "role": "system",
                "content": (
                    "You are the pipeline controller for a bounded video editing workflow. "
                    "You only choose the next allowed action. "
                    "You never provide free-form workflow instructions, shell commands, file operations, or implementation details. "
                    "Output JSON only."
                ),
            },
            {"role": "user", "content": user_content},
        ]

    @staticmethod
    def _default_json_client(
        messages: list[dict[str, Any]],
        temperature: float,
        max_tokens: int,
        preferred_provider: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        return chat_json(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            preferred_provider=preferred_provider,
            raise_on_failure=True,
        )


def _validate_model(model_cls: type[BaseModel], payload: Dict[str, Any]) -> BaseModel:
    if hasattr(model_cls, "model_validate"):
        return model_cls.model_validate(payload)
    return model_cls.parse_obj(payload)


def _model_schema(model_cls: type[BaseModel]) -> Dict[str, Any]:
    if hasattr(model_cls, "model_json_schema"):
        return model_cls.model_json_schema()
    return model_cls.schema()


def model_dump(instance: BaseModel) -> Dict[str, Any]:
    if hasattr(instance, "model_dump"):
        return instance.model_dump()
    return instance.dict()


__all__ = [
    "ALLOWED_ACTIONS",
    "AllowedAction",
    "DecisionOutcome",
    "PipelineDecision",
    "PipelineDecisionEngine",
    "ValidationError",
    "model_dump",
]
