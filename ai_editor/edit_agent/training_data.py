from __future__ import annotations
import os
import json
import time
from typing import Any, Dict, Optional

def write_edit_agent_training_sample(
    job_dir: str,
    reference_template: Dict[str, Any],
    user_patched_plan: Dict[str, Any],
    source_inventory: Dict[str, Any],
    edit_graph: Dict[str, Any],
    render_spec: Dict[str, Any],
    requirements: Dict[str, Any],
    result: Optional[Dict[str, Any]] = None,
) -> str:
    training_dir = os.path.join(job_dir, "training")
    os.makedirs(training_dir, exist_ok=True)

    sample = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "reference_template": reference_template,
        "user_patched_plan": user_patched_plan,
        "source_inventory": source_inventory,
        "edit_graph": edit_graph,
        "render_spec": render_spec,
        "requirements": requirements,
        "result": result or {},
    }

    # Write JSON sample
    json_path = os.path.join(training_dir, "edit_agent_sample.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(sample, f, ensure_ascii=False, indent=2)

    # Append JSONL sample
    jsonl_path = os.path.join(training_dir, "edit_agent_sample.jsonl")
    single_line = json.dumps(sample, ensure_ascii=False)
    with open(jsonl_path, "a", encoding="utf-8") as f:
        f.write(single_line + "\n")

    return json_path
