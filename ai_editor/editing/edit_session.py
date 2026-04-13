from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .edit_operations import EditOperation
from .instruction_parser import InstructionParser
from .plan_patcher import PlanPatcher


@dataclass
class EditSession:
    timeline_plan: Dict[str, Any]
    analysis: Dict[str, Any] = field(default_factory=dict)
    requirements: Dict[str, Any] = field(default_factory=dict)
    render_spec: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_job_dir(cls, job_dir: str) -> "EditSession":
        plans_dir = os.path.join(job_dir, "plans")
        timeline_plan = cls._load_json(os.path.join(plans_dir, "timeline_plan.json"))
        render_spec = cls._load_json(os.path.join(plans_dir, "render_spec.json"))
        analysis = cls._load_json(os.path.join(job_dir, "analysis.json"))
        requirements = cls._load_json(os.path.join(job_dir, "requirements.json"))
        return cls(
            timeline_plan=timeline_plan or {},
            analysis=analysis or {},
            requirements=requirements or {},
            render_spec=render_spec or {},
        )

    @classmethod
    def from_payloads(
        cls,
        timeline_plan: Dict[str, Any],
        analysis: Optional[Dict[str, Any]] = None,
        requirements: Optional[Dict[str, Any]] = None,
        render_spec: Optional[Dict[str, Any]] = None,
    ) -> "EditSession":
        return cls(
            timeline_plan=dict(timeline_plan or {}),
            analysis=dict(analysis or {}),
            requirements=dict(requirements or {}),
            render_spec=dict(render_spec or {}),
        )

    def apply_instruction(
        self,
        instruction: str,
        parser: Optional[InstructionParser] = None,
        patcher: Optional[PlanPatcher] = None,
    ) -> Dict[str, Any]:
        parser = parser or InstructionParser()
        patcher = patcher or PlanPatcher()
        operations = parser.parse(instruction)
        return self.apply_operations(operations, patcher=patcher, raw_instruction=instruction)

    def apply_operations(
        self,
        operations: List[EditOperation],
        patcher: Optional[PlanPatcher] = None,
        raw_instruction: str = "",
    ) -> Dict[str, Any]:
        patcher = patcher or PlanPatcher()
        before_plan = deepcopy(self.timeline_plan)
        before_validation = deepcopy((self.timeline_plan or {}).get("plan_validation", {}))
        patched_plan = patcher.apply_operations(
            self.timeline_plan,
            operations,
            analysis=self.analysis,
            requirements=self.requirements,
        )
        self.timeline_plan = patched_plan
        if self.render_spec:
            self.render_spec["timeline_plan"] = patched_plan
            self.render_spec["planning_strategy"] = patched_plan.get("planning_strategy")
            self.render_spec["target_pacing"] = patched_plan.get("target_pacing")
            self.render_spec["target_segment_duration"] = patched_plan.get("target_segment_duration")
            self.render_spec["selected_segments"] = patched_plan.get("selected_segments", [])
            self.render_spec["support_segments"] = patched_plan.get("support_segments", [])
            self.render_spec["opening_segment_ids"] = patched_plan.get("opening_segment_ids", [])
            self.render_spec["rejected_segments"] = patched_plan.get("rejected_segments", [])
            self.render_spec["plan_validation"] = patched_plan.get("plan_validation", {})
            self.render_spec["planning_debug"] = patched_plan.get("planning_debug", {})
            self.render_spec["edit_directives"] = patched_plan.get("edit_directives", [])
        entry = {
            "revision_index": len(self.history) + 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "instruction": raw_instruction,
            "operations": [operation.to_dict() for operation in operations],
            "result": patched_plan.get("plan_patch", {}),
            "before": self._snapshot(before_plan),
            "after": self._snapshot(patched_plan),
            "diff": self._compact_diff(before_plan, patched_plan),
            "validation_before": before_validation,
            "validation_after": deepcopy(patched_plan.get("plan_validation", {})),
        }
        self.history.append(entry)
        return patched_plan

    @staticmethod
    def _load_json(path: str) -> Dict[str, Any]:
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    @staticmethod
    def _snapshot(plan: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "selected_segment_ids": [segment.get("label") for segment in plan.get("selected_segments", [])],
            "support_segment_ids": [segment.get("label") for segment in plan.get("support_segments", [])],
            "target_pacing": plan.get("target_pacing"),
            "target_segment_duration": plan.get("target_segment_duration"),
            "target_segment_count": plan.get("target_segment_count"),
            "edit_directives": plan.get("edit_directives", []),
        }

    @staticmethod
    def _compact_diff(before_plan: Dict[str, Any], after_plan: Dict[str, Any]) -> Dict[str, Any]:
        before_selected = [segment.get("label") for segment in before_plan.get("selected_segments", [])]
        after_selected = [segment.get("label") for segment in after_plan.get("selected_segments", [])]
        before_support = [segment.get("label") for segment in before_plan.get("support_segments", [])]
        after_support = [segment.get("label") for segment in after_plan.get("support_segments", [])]
        return {
            "selected_added": [label for label in after_selected if label not in before_selected],
            "selected_removed": [label for label in before_selected if label not in after_selected],
            "support_added": [label for label in after_support if label not in before_support],
            "support_removed": [label for label in before_support if label not in after_support],
            "pacing_changed": before_plan.get("target_pacing") != after_plan.get("target_pacing"),
            "duration_changed": before_plan.get("target_segment_duration") != after_plan.get("target_segment_duration"),
            "directive_count_delta": len(after_plan.get("edit_directives", [])) - len(before_plan.get("edit_directives", [])),
        }
