from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from .validator import validate_edit_graph


class ReferenceEditAgentError(RuntimeError):
    def __init__(self, code: str, message: str, detail: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "detail": self.detail,
        }


def compile_edit_graph(
    reference_template: Dict[str, Any],
    user_patched_plan: Dict[str, Any],
    source_inventory: Dict[str, Any],
    requirements: Dict[str, Any],
) -> Dict[str, Any]:
    backend = str(
        os.getenv("EDIT_AGENT_BACKEND")
        or requirements.get("edit_agent_backend")
        or "llm_json"
    ).strip().lower()

    if backend != "llm_json":
        raise ReferenceEditAgentError(
            "REFERENCE_EDIT_AGENT_UNSUPPORTED_BACKEND",
            "reference_edit_agent requires the llm_json backend in production.",
            {"backend": backend},
        )

    return compile_with_llm_json_agent(
        reference_template,
        user_patched_plan,
        source_inventory,
        requirements,
    )


def compile_with_llm_json_agent(
    reference_template: Dict[str, Any],
    user_patched_plan: Dict[str, Any],
    source_inventory: Dict[str, Any],
    requirements: Dict[str, Any],
) -> Dict[str, Any]:
    model = str(
        os.getenv("EDIT_AGENT_MODEL")
        or requirements.get("edit_agent_model")
        or ""
    ).strip()
    if not model:
        raise ReferenceEditAgentError(
            "REFERENCE_EDIT_AGENT_LLM_UNAVAILABLE",
            "reference_edit_agent requires EDIT_AGENT_MODEL and an LLM provider configuration.",
            {"missing": ["EDIT_AGENT_MODEL"]},
        )

    if not _has_llm_provider_config(requirements):
        raise ReferenceEditAgentError(
            "REFERENCE_EDIT_AGENT_LLM_UNAVAILABLE",
            "reference_edit_agent requires an LLM provider. Configure OPENAI_API_KEY for the llm_json backend.",
            {"backend": "llm_json"},
        )

    temperature = _coerce_float(
        os.getenv("EDIT_AGENT_TEMPERATURE", requirements.get("edit_agent_temperature", 0.2)),
        default=0.2,
    )
    max_repairs = max(
        0,
        int(_coerce_float(os.getenv("EDIT_AGENT_MAX_REPAIR_ATTEMPTS", 1), default=1)),
    )

    invalid_graph: Optional[Dict[str, Any]] = None
    validation_errors: Optional[List[str]] = None
    last_validation: Optional[Dict[str, Any]] = None

    for attempt in range(max_repairs + 1):
        prompt = build_edit_agent_prompt(
            reference_template,
            user_patched_plan,
            source_inventory,
            requirements,
            validation_errors=validation_errors,
            invalid_graph=invalid_graph,
        )
        raw_output = _call_llm_json_agent(prompt, model=model, temperature=temperature)
        graph = _parse_llm_graph_output(raw_output)
        graph.setdefault("version", "edit_graph_v1")
        graph.setdefault("global_style_ops", [])
        graph.setdefault("audio", {})
        graph.setdefault("warnings", [])
        graph.setdefault("model_metadata", {})
        graph["model_metadata"]["backend"] = "llm_json"
        graph["model_metadata"]["model"] = model
        graph["model_metadata"]["repair_attempt"] = attempt

        validation = validate_edit_graph(graph, reference_template, source_inventory)
        last_validation = validation
        if validation.get("valid"):
            return graph

        invalid_graph = graph
        validation_errors = list(validation.get("errors") or [])

    raise ReferenceEditAgentError(
        "REFERENCE_EDIT_AGENT_INVALID_GRAPH",
        "The LLM returned an invalid executable_edit_graph and the repair attempt did not succeed.",
        {
            "validation": last_validation or {},
            "invalid_graph": invalid_graph,
        },
    )


def build_edit_agent_prompt(
    reference_template: Dict[str, Any],
    user_patched_plan: Dict[str, Any],
    source_inventory: Dict[str, Any],
    requirements: Dict[str, Any],
    validation_errors: List[str] | None = None,
    invalid_graph: Dict[str, Any] | None = None,
) -> str:
    prompt_lines = [
        "You are a video editing agent.",
        "",
        "Your task is to convert:",
        "1. a reference edit template",
        "2. a user patched plan",
        "3. a source inventory",
        "4. user requirements",
        "",
        "into executable_edit_graph_v1 JSON.",
        "",
        "Return ONLY valid JSON.",
        "Do not output markdown.",
        "Do not explain.",
        "Do not write FFmpeg commands.",
        "Do not write code.",
        "Do not invent clip IDs.",
        "Do not invent file paths.",
        "Do not use source segments outside the available clip duration.",
        "",
        "Output schema:",
        "{",
        '  "version": "edit_graph_v1",',
        '  "timeline": [',
        "    {",
        '      "slot_id": 1,',
        '      "clip_id": "string",',
        '      "source_index": 1,',
        '      "video_src": null,',
        '      "source_start": 0.0,',
        '      "duration": 1.0,',
        '      "crop": {',
        '        "mode": "center",',
        '        "aspect_ratio": "9:16"',
        "      },",
        '      "motion_effects": [],',
        '      "transition_out": null,',
        '      "text": null,',
        '      "style_ops": [],',
        '      "metadata": {}',
        "    }",
        "  ],",
        '  "global_style_ops": [],',
        '  "audio": {},',
        '  "warnings": [],',
        '  "model_metadata": {',
        '    "backend": "llm_json"',
        "  }",
        "}",
        "",
        "Rules:",
        "1. Use the reference_template slots as the timeline skeleton.",
        "2. Preserve each slot duration unless user_patched_plan explicitly changes timing.",
        "3. Use user_patched_plan slot_replacements to choose clips.",
        "4. Use user_patched_plan replacement_text or text_replacements to replace detected/reference text.",
        "5. Use source_inventory candidate_segments to choose valid source_start values.",
        "6. Do not exceed clip duration.",
        "7. If a source clip is too short, shorten duration and add a warning.",
        "8. Preserve transition_out from the reference slot when available.",
        "9. Preserve motion from the reference slot as motion_effects.",
        "10. Add style_ops for reference matching, but keep them structured.",
        "11. Do not emit unsupported arbitrary operation names.",
        "12. The graph must be compilable to canonical_timeline.",
        "13. Use only clips present in source_inventory.",
        "14. Do not remove slots unless the user explicitly requested removal.",
        "",
        "Allowed crop modes:",
        "- center",
        "- subject_center",
        "- cover",
        "- fit",
        "",
        "Allowed transition types:",
        "- hard_cut",
        "- flash_cut",
        "- zoom_cut",
        "- crossfade",
        "- none",
        "",
        "Allowed style op types:",
        "- match_reference_style",
        "- match_reference_color",
        "- preserve_source_style",
        "",
        "REFERENCE_TEMPLATE:",
        json.dumps(reference_template, ensure_ascii=False, indent=2),
        "",
        "USER_PATCHED_PLAN:",
        json.dumps(user_patched_plan, ensure_ascii=False, indent=2),
        "",
        "SOURCE_INVENTORY:",
        json.dumps(source_inventory, ensure_ascii=False, indent=2),
        "",
        "REQUIREMENTS:",
        json.dumps(requirements, ensure_ascii=False, indent=2),
    ]

    if validation_errors is not None and invalid_graph is not None:
        prompt_lines.extend(
            [
                "",
                "VALIDATION_ERRORS:",
                json.dumps(validation_errors, ensure_ascii=False, indent=2),
                "",
                "INVALID_GRAPH:",
                json.dumps(invalid_graph, ensure_ascii=False, indent=2),
                "",
                "Repair the graph. Return only corrected JSON.",
            ]
        )

    return "\n".join(prompt_lines)


def _call_llm_json_agent(prompt: str, *, model: str, temperature: float) -> str:
    try:
        from openai import OpenAI
    except Exception as exc:
        raise ReferenceEditAgentError(
            "REFERENCE_EDIT_AGENT_LLM_UNAVAILABLE",
            "reference_edit_agent requires the OpenAI SDK for the llm_json backend.",
            {"exception": repr(exc)},
        ) from exc

    api_key = str(os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise ReferenceEditAgentError(
            "REFERENCE_EDIT_AGENT_LLM_UNAVAILABLE",
            "reference_edit_agent requires OPENAI_API_KEY for the llm_json backend.",
        )

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            temperature=temperature,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "You are a video editing agent that returns only executable_edit_graph_v1 JSON.",
                },
                {"role": "user", "content": prompt},
            ],
        )
    except Exception as exc:
        raise ReferenceEditAgentError(
            "REFERENCE_EDIT_AGENT_LLM_FAILED",
            "The reference_edit_agent LLM request failed.",
            {"exception": repr(exc), "model": model},
        ) from exc

    output = response.choices[0].message.content if response.choices else ""
    if not output:
        raise ReferenceEditAgentError(
            "REFERENCE_EDIT_AGENT_EMPTY_RESPONSE",
            "The reference_edit_agent LLM returned an empty response.",
            {"model": model},
        )
    return output


def _parse_llm_graph_output(raw_output: str) -> Dict[str, Any]:
    payload = str(raw_output or "").strip()
    if not payload:
        raise ReferenceEditAgentError(
            "REFERENCE_EDIT_AGENT_INVALID_JSON",
            "The reference_edit_agent LLM returned empty output instead of JSON.",
        )

    if payload.startswith("```"):
        lines = payload.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        payload = "\n".join(lines).strip()

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ReferenceEditAgentError(
            "REFERENCE_EDIT_AGENT_INVALID_JSON",
            "The reference_edit_agent LLM returned malformed JSON.",
            {"exception": repr(exc), "raw_output": raw_output},
        ) from exc

    if not isinstance(parsed, dict):
        raise ReferenceEditAgentError(
            "REFERENCE_EDIT_AGENT_INVALID_JSON",
            "The reference_edit_agent LLM must return a top-level JSON object.",
            {"parsed_type": type(parsed).__name__},
        )

    required_fields = {"version", "timeline", "global_style_ops", "audio", "warnings", "model_metadata"}
    missing = sorted(required_fields - set(parsed.keys()))
    if missing:
        raise ReferenceEditAgentError(
            "REFERENCE_EDIT_AGENT_INVALID_JSON",
            "The reference_edit_agent LLM output is missing required top-level fields.",
            {"missing_fields": missing, "graph": parsed},
        )
    return parsed


def _has_llm_provider_config(requirements: Dict[str, Any]) -> bool:
    return bool(
        str(os.getenv("OPENAI_API_KEY") or "").strip()
        or str(requirements.get("openai_api_key") or "").strip()
    )


def _coerce_float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
