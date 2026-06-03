# ai_editor/chat_intake/state_machine.py

import json
from typing import Dict, List, Optional
from ai_editor.chat_intake.schemas import (
    DEFAULT_INTAKE_STATE,
    PHASE_AWAITING_REFERENCE,
    PHASE_REFERENCE_URL_RECEIVED,
    PHASE_AWAITING_SOURCES,
    PHASE_AWAITING_SLOT_MAPPING,
    PHASE_AWAITING_AUDIO,
    PHASE_AWAITING_CUSTOM_MUSIC,
    PHASE_AWAITING_OUTPUT,
    PHASE_AWAITING_TEXT_OVERLAYS,
    PHASE_AWAITING_FINAL_CONFIRMATION,
)
from ai_editor.chat_intake.extractors import extract_all
from ai_editor.llm_client import chat_text, get_active_model_name

# Neural style transfer uses a dedicated content-video phase not in the standard flow
PHASE_AWAITING_CONTENT_VIDEO = "awaiting_content_video"


def auto_assign_slots(state: dict):
    slots = state.get("reference_slots") or []
    sources = state.get("sources") or []
    google_drive = state.get("google_drive_link") or ""

    if google_drive:
        return

    # Neural style transfer uses sources directly — no slot mapping needed.
    if state.get("generation_mode") == "neural_style_transfer":
        return

    if not slots or not sources:
        return

    mapping = []
    for i, slot in enumerate(slots):
        slot_id = slot["slot_id"]
        if i < len(sources):
            src = sources[i]
            mapping.append({
                "slot_id": slot_id,
                "clip_url": src.get("url") if isinstance(src, dict) else src,
            })
    state["slot_mapping"] = mapping


def _advance_phase_neural(state: dict) -> None:
    """Drive phase transitions for the neural style transfer intake flow.

    Only two things are collected from the user:
      1. Donor (reference) video URL
      2. N content clip URLs (N = number of scenes detected in the donor)

    Everything else (audio, output format, aspect ratio) is handled automatically.
    """
    primary_url = state.get("primary_url")
    sources = state.get("sources") or []
    slots = state.get("reference_slots") or []
    needed = len(slots) if slots else 1

    if not primary_url:
        state["phase"] = PHASE_AWAITING_REFERENCE
    elif len(sources) < needed:
        state["phase"] = PHASE_AWAITING_CONTENT_VIDEO
    else:
        state["phase"] = PHASE_AWAITING_FINAL_CONFIRMATION
        state["ready_to_submit"] = True


def build_reply_for_phase(state: dict) -> str:
    phase = state.get("phase", PHASE_AWAITING_REFERENCE)
    generation_mode = state.get("generation_mode")
    ref_slots = state.get("reference_slots") or []
    sources = state.get("sources") or []

    # ── Neural style transfer phases ────────────────────────────────────────
    if generation_mode == "neural_style_transfer":
        if phase == PHASE_AWAITING_REFERENCE:
            return "Send the donor video URL — the neural network will learn its visual style."
        if phase == PHASE_AWAITING_CONTENT_VIDEO:
            slots = state.get("reference_slots") or []
            needed = len(slots) if slots else 1
            have = len(state.get("sources") or [])
            if needed == 1:
                return (
                    "Got it. Now send the content clip URL — "
                    "the footage that will be repainted in the donor's style."
                )
            return (
                f"{needed} scene(s) detected. Send {needed} content clip URL(s), one per scene. "
                f"{have} received so far."
            )
        if phase == PHASE_AWAITING_FINAL_CONFIRMATION:
            return "All set. Confirm to start training and rendering."

    # ── Standard phases ──────────────────────────────────────────────────────
    if phase == PHASE_AWAITING_REFERENCE:
        return "Drop a reference video URL and I'll analyse the editing style for you."

    if phase == PHASE_AWAITING_CONTENT_VIDEO:
        slots = state.get("reference_slots") or []
        needed = len(slots) if slots else 1
        have = len(state.get("sources") or [])
        if needed == 1:
            return (
                "Donor video received. Now send the content video URL — "
                "this is the video whose footage will be repainted in the donor's style."
            )
        return (
            f"Donor video received. {needed} scene(s) were detected. "
            f"Send {needed} content clip URLs, one per scene. "
            f"You have sent {have} so far."
        )

    if phase == PHASE_REFERENCE_URL_RECEIVED:
        return "On it — pulling out the editing style, scene timings, and any on-screen text now."

    if phase == PHASE_AWAITING_SOURCES:
        return "Got the analysis. Now paste in your replacement clip URLs using the form below."

    if phase == PHASE_AWAITING_SLOT_MAPPING:
        slot_count = len(ref_slots)
        source_count = len(sources)
        if source_count == slot_count:
            return f"All {slot_count} clips are mapped. Take a look and tweak anything before moving on."
        elif source_count < slot_count:
            missing = slot_count - source_count
            return f"{source_count} clip{'s' if source_count != 1 else ''} mapped, {missing} still needed — add the rest in the form below."
        else:
            extra = source_count - slot_count
            return f"First {slot_count} clips are mapped ({extra} extra won't be used). Review below and confirm when it looks right."

    if phase == PHASE_AWAITING_TEXT_OVERLAYS:
        overlays = state.get("text_overlays") or []
        if overlays:
            from ai_editor.chat_intake.text_overlays import summarize_text_overlays_for_chat
            return summarize_text_overlays_for_chat(overlays)
        return "I found some on-screen text in the reference. Use the form below to keep, replace, or remove each one."

    if phase == PHASE_AWAITING_FINAL_CONFIRMATION:
        return "Everything's set. Look over the plan below and hit confirm when you're happy with it."

    return "Still with you — what would you like to adjust?"

def _generate_reply(user_input: str, state: dict) -> str:
    """LLM-generated reply that acknowledges the user's message and guides toward the next step."""
    phase_prompt = build_reply_for_phase(state)

    if not user_input.strip():
        return phase_prompt

    reply = chat_text(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a video editing assistant. The workflow collects exactly three "
                    "things from the user: a reference video URL, replacement clip URLs, and "
                    "text overlay choices. Everything else — style, tone, pacing, audio, "
                    "aspect ratio — is inferred automatically from the reference video. "
                    "Your only job is to briefly acknowledge what the user said, then state "
                    "what is needed next (given by 'Next step'). "
                    "NEVER ask the user a question. NEVER ask about preferences, style, tone, "
                    "pacing, audio, or format. Keep it to 1-2 short sentences."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Next step: {phase_prompt}\n"
                    f"User said: {json.dumps(user_input)}\n\n"
                    "Reply to the user."
                ),
            },
        ],
        temperature=0.4,
    )
    return reply or phase_prompt


def process_guided_turn(user_input: str, current_state: dict, analyzer_output: str = "") -> dict:
    state = dict(DEFAULT_INTAKE_STATE)
    if current_state:
        state.update(current_state)

    for key in [
        "edit_requests",
        "user_requests",
        "sources",
        "slot_mapping",
        "reference_slots",
        "text_overlays",
    ]:
        if not isinstance(state.get(key), list):
            state[key] = []
    if not isinstance(state.get("text_overlays_resolved"), bool):
        state["text_overlays_resolved"] = False

    if user_input.strip():
        state["user_requests"].append(user_input.strip())

    user_input_lower = user_input.strip().lower()
    if any(k in user_input_lower for k in ["change this plan", "change plan", "edit plan", "adjust plan", "modify plan"]):
        state["phase"] = PHASE_AWAITING_SLOT_MAPPING
        state["ready_to_submit"] = False
        return {
            "updated_state": state,
            "next_message": "Sure, let's tweak it — update the clip assignments in the form below.",
            "is_complete": False,
            "final_report": None,
            "model_used": "deterministic-extractor"
        }

    extracted = extract_all(user_input, state)
    for k, v in extracted.items():
        if v is not None and v != "":
            state[k] = v

    # Always re-run auto-assign so pre-existing sources in state are mapped
    # even when no new sources/slots were extracted from the current message.
    auto_assign_slots(state)

    # Preserve legacy editing instructions
    from ai_editor.chatbot_interface import _is_editing_instruction, _INTENT_PARSER
    if _is_editing_instruction(user_input):
        try:
            operations = _INTENT_PARSER.parse(user_input, current_state=state)
            parsed_ops = [op.to_dict() for op in operations]
            existing_keys = {
                (r.get("operation"), r.get("target"), r.get("scope"))
                for r in state["edit_requests"]
                if isinstance(r, dict)
            }
            for op_dict in parsed_ops:
                key = (op_dict.get("operation"), op_dict.get("target"), op_dict.get("scope"))
                if key not in existing_keys:
                    state["edit_requests"].append(op_dict)
        except Exception:
            pass

    # Route neural style transfer through its own phase machine
    if state.get("generation_mode") == "neural_style_transfer":
        _advance_phase_neural(state)
    else:
        # Guided state machine transition checks
        primary_url = state.get("primary_url")
        ref_slots = state.get("reference_slots")
        sources = state.get("sources") or []
        google_drive = state.get("google_drive_link")
        slot_mapping = state.get("slot_mapping") or []
        text_overlays = state.get("text_overlays") or []
        text_overlays_resolved = bool(state.get("text_overlays_resolved"))

        if not primary_url:
            state["phase"] = PHASE_AWAITING_REFERENCE
        elif not ref_slots:
            state["phase"] = PHASE_REFERENCE_URL_RECEIVED
        elif not sources and not google_drive:
            state["phase"] = PHASE_AWAITING_SOURCES
        elif not google_drive and len(slot_mapping) < len(ref_slots):
            state["phase"] = PHASE_AWAITING_SLOT_MAPPING
        elif text_overlays and not text_overlays_resolved:
            state["phase"] = PHASE_AWAITING_TEXT_OVERLAYS
            state["ready_to_submit"] = False
        else:
            state["phase"] = PHASE_AWAITING_FINAL_CONFIRMATION
            state["ready_to_submit"] = True

    next_message = _generate_reply(user_input, state)

    return {
        "updated_state": state,
        "next_message": next_message,
        "is_complete": False,
        "final_report": None,
        "model_used": get_active_model_name(),
    }
