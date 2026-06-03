# ai_editor/chat_intake/state_machine.py

from typing import Dict, List
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
from ai_editor.llm_client import get_active_model_name

# Phase used when waiting for the content video in neural style transfer mode.
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


def build_reply_for_phase(state: dict) -> str:
    phase = state.get("phase", PHASE_AWAITING_REFERENCE)
    generation_mode = state.get("generation_mode")
    ref_slots = state.get("reference_slots") or []
    sources = state.get("sources") or []

    # ── Neural style transfer phases ────────────────────────────────────────
    if generation_mode == "neural_style_transfer":
        if phase == PHASE_AWAITING_REFERENCE:
            return (
                "Neural style transfer mode activated. "
                "Send the donor video URL — this is the video whose visual style will be learned."
            )
        if phase == PHASE_AWAITING_CONTENT_VIDEO:
            return (
                "Donor video received. Now send the content video URL — "
                "this is the video that will be repainted in the donor's style."
            )
        if phase == PHASE_AWAITING_AUDIO:
            return "Audio settings next. Keep the donor audio or provide a custom music URL?"
        if phase == PHASE_AWAITING_OUTPUT:
            return "Choose output aspect ratio and refit mode."
        if phase == PHASE_AWAITING_FINAL_CONFIRMATION:
            return (
                "Ready. The style renderer will train on the donor video (~15-25 min on CPU) "
                "then rerender the content video in that style. Confirm to start."
            )

    # ── Standard phases ──────────────────────────────────────────────────────
    if phase == PHASE_AWAITING_REFERENCE:
        return "Send the reference video URL to begin the analysis."

    if phase == PHASE_REFERENCE_URL_RECEIVED:
        return "The reference video is being analyzed. I will extract the style summary, slot timings, and any detected text."

    if phase == PHASE_AWAITING_SOURCES:
        return "The reference summary is ready. Use the replacement slot form below to enter clip URLs."

    if phase == PHASE_AWAITING_SLOT_MAPPING:
        slot_count = len(ref_slots)
        source_count = len(sources)
        if source_count == slot_count:
            return f"The {slot_count} replacement slots are mapped. Review the table below and make any adjustments if needed."
        elif source_count < slot_count:
            missing = slot_count - source_count
            return f"{source_count} slot(s) are mapped and {missing} remain. Add the remaining clip URLs in the slot form."
        else:
            extra = source_count - slot_count
            return f"The first {slot_count} clips are mapped and {extra} extra clip(s) remain unused. Review the table below to finalize assignments."

    if phase == PHASE_AWAITING_AUDIO:
        return "Audio settings are next. Choose whether to keep the reference audio or provide a custom music URL."

    if phase == PHASE_AWAITING_CUSTOM_MUSIC:
        return "Enter the custom music URL and any optional time range."

    if phase == PHASE_AWAITING_OUTPUT:
        return "Choose the output aspect ratio and refit mode for the final video."

    if phase == PHASE_AWAITING_TEXT_OVERLAYS:
        overlays = state.get("text_overlays") or []
        if overlays:
            from ai_editor.chat_intake.text_overlays import summarize_text_overlays_for_chat
            return summarize_text_overlays_for_chat(overlays)
        return (
            "Detected text moments are ready for review. Use the text replacement form below to remove, keep, or replace them."
        )

    if phase == PHASE_AWAITING_FINAL_CONFIRMATION:
        return "The edit plan is ready. Review the cards below and confirm when everything looks correct."

    return "Continuing the guided intake."


def _advance_phase_neural(state: dict) -> None:
    """Drive phase transitions for the neural_style_transfer flow.

    Simpler than the standard flow: donor URL → content URL → audio → output → confirm.
    """
    primary_url = state.get("primary_url")
    sources = state.get("sources") or []
    music_mode = state.get("music_mode")
    custom_music_url = state.get("custom_music_url")
    aspect_ratio = state.get("aspect_ratio")
    refit_mode = state.get("refit_mode")

    if not primary_url:
        state["phase"] = PHASE_AWAITING_REFERENCE
    elif not sources:
        state["phase"] = PHASE_AWAITING_CONTENT_VIDEO
    elif not music_mode:
        state["phase"] = PHASE_AWAITING_AUDIO
    elif music_mode == "custom" and not custom_music_url:
        state["phase"] = PHASE_AWAITING_CUSTOM_MUSIC
    elif not aspect_ratio or not refit_mode:
        state["phase"] = PHASE_AWAITING_OUTPUT
    else:
        state["phase"] = PHASE_AWAITING_FINAL_CONFIRMATION
        state["ready_to_submit"] = True


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
            "next_message": "Understood! Let's modify the plan. What would you like to change? You can specify slot mappings, audio choice, or output format.",
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

    # Phase transition — neural style transfer has its own simpler flow.
    if state.get("generation_mode") == "neural_style_transfer":
        _advance_phase_neural(state)
    else:
        # Standard guided state machine transition checks
        primary_url = state.get("primary_url")
        ref_slots = state.get("reference_slots")
        sources = state.get("sources") or []
        google_drive = state.get("google_drive_link")
        slot_mapping = state.get("slot_mapping") or []
        music_mode = state.get("music_mode")
        custom_music_url = state.get("custom_music_url")
        aspect_ratio = state.get("aspect_ratio")
        refit_mode = state.get("refit_mode")
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
        elif not music_mode:
            state["phase"] = PHASE_AWAITING_AUDIO
        elif music_mode == "custom" and not custom_music_url:
            state["phase"] = PHASE_AWAITING_CUSTOM_MUSIC
        elif not aspect_ratio or not refit_mode:
            state["phase"] = PHASE_AWAITING_OUTPUT
        elif text_overlays and not text_overlays_resolved:
            state["phase"] = PHASE_AWAITING_TEXT_OVERLAYS
            state["ready_to_submit"] = False
        else:
            state["phase"] = PHASE_AWAITING_FINAL_CONFIRMATION
            state["ready_to_submit"] = True

    next_message = build_reply_for_phase(state)

    return {
        "updated_state": state,
        "next_message": next_message,
        "is_complete": False,
        "final_report": None,
        "model_used": get_active_model_name(),
    }
