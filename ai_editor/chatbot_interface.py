import json
import os
import re
from typing import Dict, List

from groq import Groq

GROQ_API_KEY = os.getenv("GROQ")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
MODEL_NAME = "llama-3.3-70b-versatile"

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

    extracted_data = {}
    if client:
        extraction_prompt = (
            "Extract and normalize video preferences from the user message.\n"
            "Use defaults if unclear; do not block on missing info.\n"
            "Return a JSON object with keys:\n"
            f"{REQUIRED_FIELDS}\n"
            "Allowed intent_mode: video|shorts. Allowed refit_mode: crop|pad.\n"
            "If a value is unknown, return null.\n\n"
            f"Current state: {json.dumps(state, ensure_ascii=False)}\n"
            f"Analyzer context: {analyzer_output}\n"
            f"User message: {user_input}\n"
        )
        try:
            completion = client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You extract user preferences for a video editing assistant. Output JSON only.",
                    },
                    {"role": "user", "content": extraction_prompt},
                ],
                model=MODEL_NAME,
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            extracted_data = json.loads(completion.choices[0].message.content)
        except Exception as e:
            print(f"Groq Extraction Error: {e}")

    for key in REQUIRED_FIELDS:
        val = extracted_data.get(key)
        if val is not None and val != "":
            state[key] = val

    # Normalize constrained values
    if str(state.get("intent_mode", "")).lower() not in {"video", "shorts"}:
        state["intent_mode"] = "video"
    if str(state.get("refit_mode", "")).lower() not in {"crop", "pad"}:
        state["refit_mode"] = "crop"

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
    }
