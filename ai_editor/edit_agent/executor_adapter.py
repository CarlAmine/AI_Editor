from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from .compiler import compile_edit_graph_to_render_spec
from .model_client import ReferenceEditAgentError, compile_edit_graph
from .training_data import write_edit_agent_training_sample
from .user_plan_adapter import build_user_patched_plan
from .validator import validate_edit_graph


def run_edit_agent_compile_stage(
    job_id: str,
    job_dir: str,
    requirements: Dict[str, Any],
    request_payload: Dict[str, Any],
    reference_template: Dict[str, Any],
    source_inventory: Dict[str, Any],
    audio_plan: Optional[Dict[str, Any]] = None,
    overlay_plan: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    plans_dir = os.path.join(job_dir, "plans")
    os.makedirs(plans_dir, exist_ok=True)

    user_patched_plan = build_user_patched_plan(requirements, request_payload, reference_template)
    _write_json(os.path.join(plans_dir, "user_patched_plan.json"), user_patched_plan)

    try:
        edit_graph = compile_edit_graph(reference_template, user_patched_plan, source_inventory, requirements)
        validation = validate_edit_graph(edit_graph, reference_template, source_inventory)
        _write_json(os.path.join(plans_dir, "executable_edit_graph.json"), edit_graph)
        _write_json(os.path.join(plans_dir, "edit_graph_validation.json"), validation)

        if not validation.get("valid"):
            raise ReferenceEditAgentError(
                "REFERENCE_EDIT_AGENT_INVALID_GRAPH",
                "reference_edit_agent produced an invalid executable_edit_graph.",
                {"validation": validation, "graph": edit_graph},
            )

        compile_result = compile_edit_graph_to_render_spec(
            edit_graph=edit_graph,
            source_inventory=source_inventory,
            reference_template=reference_template,
            requirements=requirements,
            existing_audio_plan=audio_plan,
            existing_overlay_plan=overlay_plan,
        )
        render_spec = compile_result["render_spec"]
        canonical_timeline = compile_result["canonical_timeline"]
        warnings = list(compile_result.get("warnings") or [])
        for warning in validation.get("warnings") or []:
            if warning not in warnings:
                warnings.append(warning)

        _write_json(os.path.join(plans_dir, "compiled_render_spec.json"), render_spec)
        _write_json(os.path.join(plans_dir, "render_spec.json"), render_spec)

        training_sample_path = write_edit_agent_training_sample(
            job_dir=job_dir,
            reference_template=reference_template,
            user_patched_plan=user_patched_plan,
            source_inventory=source_inventory,
            edit_graph=edit_graph,
            render_spec=render_spec,
            requirements=requirements,
            result={"success": True},
        )

        return {
            "user_patched_plan": user_patched_plan,
            "edit_graph": edit_graph,
            "validation": validation,
            "render_spec": render_spec,
            "canonical_timeline": canonical_timeline,
            "warnings": warnings,
            "training_sample_path": training_sample_path,
        }
    except ReferenceEditAgentError as exc:
        error_payload = exc.to_dict()
        _write_json(os.path.join(plans_dir, "edit_agent_error.json"), error_payload)
        raise


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
