import json
import re
from typing import Dict, List

from ai_editor.ai_client import chat_json, chat_text, get_active_model_name

REQUIRED_FIELDS = [
    "video_topic",
    "target_audience",
    "platform",
    "duration_seconds",
    "aspect_ratio",
    "orientation",
    "tone",
    "pacing",
    "style_reference",
    "call_to_action",
    "branding",
    "subtitles",
    "deadline",
    "budget",
    "intent_mode",
    "refit_mode",
    "generation_mode",
    "edit_mode",
]

DEFAULT_STATE = {
    "video_topic": "General promotional/edit video",
    "target_audience": "General audience",
    "platform": "YouTube",
    "duration_seconds": 60,
    "aspect_ratio": "16:9",
    "orientation": "horizontal",
    "tone": "engaging",
    "pacing": "medium",
    "style_reference": "",
    "call_to_action": "",
    "branding": "",
    "subtitles": "yes",
    "deadline": "",
    "budget": "",
    "intent_mode": "video",
    "refit_mode": "crop",
    "generation_mode": "reference_mimic_mode",
    "edit_mode": "scene",
    "edit_requests": [],
    "user_requests": [],
}


def _normalize_state(current_state: Dict) -> Dict:
    state = dict(DEFAULT_STATE)
    if current_state:
        state.update(current_state)
    if not isinstance(state.get("edit_requests"), list):
        state["edit_requests"] = []
    if not isinstance(state.get("user_requests"), list):
        state["user_requests"] = []
    return state


def _extract_action_requests(text: str) -> List[str]:
    text_low = text.lower()
    actions = []

    patterns = [
        (r"(remove|cut|delete)\s+(.+)", "remove"),
        (r"(trim)\s+(.+)", "trim"),
        (r"(add)\s+(.+)", "add"),
        (r"(replace)\s+(.+)", "replace"),
    ]
    for pattern, action in patterns:
        m = re.search(pattern, text_low)
        if m:
            actions.append(f"{action}: {m.group(2).strip()}")

    if not actions and any(k in text_low for k in ["remove", "cut", "trim", "delete", "add", "replace"]):
        actions.append(f"edit: {text.strip()}")
    return actions


def _extract_generation_mode(text: str) -> str:
    text_low = text.lower()
    if any(k in text_low for k in ["reference mimic", "mimic mode", "match reference", "copy reference timing"]):
        return "reference_mimic_mode"
    if any(k in text_low for k in ["free generation", "free mode", "non mimic", "not mimic"]):
        return "free_generation_mode"
    return ""


def _extract_edit_mode(text: str) -> str:
    text_low = text.lower()
    if any(
        k in text_low
        for k in [
            "ocr mode",
            "ocr-based",
            "ocr based",
            "text timeline",
            "follow text",
            "use ocr",
        ]
    ):
        return "ocr"
    if any(
        k in text_low
        for k in [
            "scene mode",
            "scene-based",
            "scene based",
            "use scenes",
            "scene timeline",
        ]
    ):
        return "scene"
    return ""


def _summarize_pipeline_feedback(state: Dict) -> str:
    feedback = state.get("pipeline_feedback")
    if not isinstance(feedback, dict):
        return ""
    reason = str(feedback.get("reason", "")).strip()
    error = str(feedback.get("error", "")).strip()
    stage = str(feedback.get("stage", "")).strip()
    if not reason and not error:
        return ""
    summary = f"stage={stage or 'UNKNOWN'}"
    if reason:
        summary += f", reason={reason}"
    if error:
        summary += f", error={error}"
    return summary


def process_ui_turn(
    user_input: str,
    current_state: Dict,
    analyzer_output: str,
    api_key: str = None,
) -> Dict:
    state = _normalize_state(current_state)

    # Always keep raw user request history.
    state["user_requests"].append(user_input.strip())
    for req in _extract_action_requests(user_input):
        if req not in state["edit_requests"]:
            state["edit_requests"].append(req)

    extraction_prompt = (
        "Extract and normalize video preferences from the user message.\n"
        "Use defaults if unclear; do not block on missing info.\n"
        "Return a JSON object with keys:\n"
        f"{REQUIRED_FIELDS}\n"
        "Allowed intent_mode: video|shorts. Allowed refit_mode: crop|pad.\n"
        "Allowed generation_mode: reference_mimic_mode|free_generation_mode.\n"
        "Allowed edit_mode: scene|ocr.\n"
        "If a value is unknown, return null.\n\n"
        f"Current state: {json.dumps(state, ensure_ascii=False)}\n"
        f"Analyzer context: {analyzer_output}\n"
        f"User message: {user_input}\n"
    )
    extracted_data = chat_json(
        messages=[
            {
                "role": "system",
                "content": "You extract user preferences for a video editing assistant. Output JSON only.",
            },
            {"role": "user", "content": extraction_prompt},
        ],
        temperature=0.2,
    )
    if extracted_data is None:
        extracted_data = {}

    for key in REQUIRED_FIELDS:
        val = extracted_data.get(key)
        if val is not None and val != "":
            state[key] = val

    explicit_generation_mode = _extract_generation_mode(user_input)
    if explicit_generation_mode:
        state["generation_mode"] = explicit_generation_mode
    explicit_edit_mode = _extract_edit_mode(user_input)
    if explicit_edit_mode:
        state["edit_mode"] = explicit_edit_mode

    # Normalize constrained values
    if str(state.get("intent_mode", "")).lower() not in {"video", "shorts"}:
        state["intent_mode"] = "video"
    if str(state.get("refit_mode", "")).lower() not in {"crop", "pad"}:
        state["refit_mode"] = "crop"
    if str(state.get("generation_mode", "")).lower() not in {
        "reference_mimic_mode",
        "free_generation_mode",
    }:
        state["generation_mode"] = "reference_mimic_mode"
    if str(state.get("edit_mode", "")).lower() not in {"scene", "ocr"}:
        state["edit_mode"] = "scene"

    latest_request = state["edit_requests"][-1] if state["edit_requests"] else ""
    pipeline_feedback_summary = _summarize_pipeline_feedback(state)
    state_summary = (
        f"platform={state.get('platform')}, "
        f"tone={state.get('tone')}, "
        f"pacing={state.get('pacing')}, "
        f"edit_mode={state.get('edit_mode')}, "
        f"generation_mode={state.get('generation_mode')}"
    )
    if latest_request:
        state_summary += f", latest_edit_request={latest_request}"
    if pipeline_feedback_summary:
        state_summary += f", latest_pipeline_feedback={pipeline_feedback_summary}"

    next_message = chat_text(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful video editing assistant. "
                    "Respond naturally to the user in 1-2 short sentences. "
                    "Confirm what you understood, and if any edit_requests were captured, "
                    "mention the latest one. Be concise and friendly."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"User input: {user_input}\n"
                    f"State summary: {state_summary}"
                ),
            },
        ]
    )
    if not next_message:
        next_message = (
            "Got it. I registered your request and updated the editing plan. "
            "You can keep adding changes like remove/cut/trim/add, and I will keep tracking them."
        )
        if state["edit_requests"]:
            latest = state["edit_requests"][-1]
            next_message += f" Latest edit request: {latest}."

    return {
        "updated_state": state,
        "next_message": next_message,
        "is_complete": False,
        "final_report": None,
        "model_used": get_active_model_name(),
    }
