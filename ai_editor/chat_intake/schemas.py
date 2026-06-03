# ai_editor/chat_intake/schemas.py

PHASE_AWAITING_REFERENCE = "awaiting_reference"
PHASE_ANALYZING_REFERENCE = "analyzing_reference"
PHASE_REFERENCE_URL_RECEIVED = "reference_url_received"
PHASE_REFERENCE_SUMMARY_READY = "reference_summary_ready"
PHASE_AWAITING_SOURCES = "awaiting_sources"
PHASE_AWAITING_SLOT_MAPPING = "awaiting_slot_mapping"
PHASE_AWAITING_AUDIO = "awaiting_audio"
PHASE_AWAITING_CUSTOM_MUSIC = "awaiting_custom_music"
PHASE_AWAITING_OUTPUT = "awaiting_output"
PHASE_AWAITING_TEXT_OVERLAYS = "awaiting_text_overlays"
PHASE_AWAITING_FINAL_CONFIRMATION = "awaiting_final_confirmation"
PHASE_PIPELINE_RUNNING = "pipeline_running"

INTAKE_PHASES = {
    PHASE_AWAITING_REFERENCE,
    PHASE_ANALYZING_REFERENCE,
    PHASE_REFERENCE_URL_RECEIVED,
    PHASE_REFERENCE_SUMMARY_READY,
    PHASE_AWAITING_SOURCES,
    PHASE_AWAITING_SLOT_MAPPING,
    PHASE_AWAITING_AUDIO,
    PHASE_AWAITING_CUSTOM_MUSIC,
    PHASE_AWAITING_OUTPUT,
    PHASE_AWAITING_TEXT_OVERLAYS,
    PHASE_AWAITING_FINAL_CONFIRMATION,
    PHASE_PIPELINE_RUNNING
}

DEFAULT_INTAKE_STATE = {
    "phase": PHASE_AWAITING_REFERENCE,
    "primary_url": "",
    "reference_analysis": None,
    "reference_style_summary": "",
    "reference_slots": [],
    "text_overlays": [],
    "text_overlays_resolved": False,
    "reference_job_id": "",
    "sources": [],
    "google_drive_link": "",
    "slot_mapping": [],
    "music_mode": "",
    "custom_music_url": "",
    "custom_music_segment": "",
    "intent_mode": "",
    "aspect_ratio": "",
    "output_mode": "",
    "refit_mode": "",
    "ready_to_submit": False,
    "user_goal": "",
    "edit_requests": [],
    "user_requests": [],
    "generation_mode": "neural_style_transfer",
    "edit_mode": "scene",
}
