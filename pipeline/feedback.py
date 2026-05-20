import re
from typing import Any, Dict, Optional

from ai_editor.generation_modes import normalize_generation_mode


def build_pipeline_assistant_feedback(
    error: str,
    stage: Optional[str] = None,
    requirements: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Turn raw pipeline failures into structured UI/chat guidance."""
    requirements = requirements or {}
    message = str(error or "").strip() or "Pipeline failed."
    low = message.lower()
    generation_mode = normalize_generation_mode(requirements.get("generation_mode"))
    edit_mode = str(requirements.get("edit_mode", "scene")).strip().lower()

    feedback: Dict[str, Any] = {
        "route_to_chat": False,
        "category": "system",
        "reason": "pipeline_failure",
        "message": "",
        "state_patch": {
            "pipeline_feedback": {
                "stage": stage or "UNKNOWN",
                "error": message,
                "category": "system",
                "reason": "pipeline_failure",
                "route_to_chat": False,
            }
        },
    }

    def apply(
        *,
        route_to_chat: bool,
        category: str,
        reason: str,
        assistant_message: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload = {
            "stage": stage or "UNKNOWN",
            "error": message,
            "category": category,
            "reason": reason,
            "route_to_chat": route_to_chat,
        }
        if extra:
            payload.update(extra)
        feedback["route_to_chat"] = route_to_chat
        feedback["category"] = category
        feedback["reason"] = reason
        feedback["message"] = assistant_message
        feedback["state_patch"] = {"pipeline_feedback": payload}
        return feedback

    ref_mimic_match = re.search(
        r"Reference (?:mimic|style transfer) requires at least (\d+) sources; received (\d+)\.",
        message,
        re.IGNORECASE,
    )
    if ref_mimic_match:
        required = int(ref_mimic_match.group(1))
        received = int(ref_mimic_match.group(2))
        missing = max(0, required - received)
        return apply(
            route_to_chat=True,
            category="input",
            reason="reference_mimic_too_few_sources",
            assistant_message=(
                f"I couldn't continue because reference style transfer needs {required} source videos, "
                f"and only {received} {'was' if received == 1 else 'were'} available. "
                f"Add {missing} more source clip{'s' if missing != 1 else ''} in Source Footage or Bulk Source, "
                "or tell me in chat to switch this job to free generation mode."
            ),
            extra={
                "required_sources": required,
                "received_sources": received,
                "generation_mode": generation_mode,
                "edit_mode": edit_mode,
            },
        )

    ocr_match = re.search(
        r"OCR mode in reference (?:mimic|style transfer) requires at least (\d+) sources; received (\d+)\.",
        message,
        re.IGNORECASE,
    )
    if ocr_match:
        required = int(ocr_match.group(1))
        received = int(ocr_match.group(2))
        missing = max(0, required - received)
        return apply(
            route_to_chat=True,
            category="input",
            reason="ocr_reference_mimic_too_few_sources",
            assistant_message=(
                f"OCR reference style transfer needs {required} source videos, but only {received} {'was' if received == 1 else 'were'} provided. "
                f"Add {missing} more source clip{'s' if missing != 1 else ''}, or ask me in chat to switch away from OCR/reference style transfer mode."
            ),
            extra={
                "required_sources": required,
                "received_sources": received,
                "generation_mode": generation_mode,
                "edit_mode": edit_mode,
            },
        )

    if "no video files found in provided google drive folder" in low:
        return apply(
            route_to_chat=True,
            category="input",
            reason="drive_folder_empty",
            assistant_message=(
                "The Google Drive folder did not contain any video files the pipeline could use. "
                "Add videos to that folder, or remove the Drive link and use Source Footage or Bulk Source instead."
            ),
        )

    if "no fetchable sources available for rendering" in low:
        return apply(
            route_to_chat=True,
            category="input",
            reason="no_fetchable_sources",
            assistant_message=(
                "The pipeline reached rendering without any usable source clips. "
                "Please add valid source videos, then try again. If you want, tell me in chat which source strategy to use and I will help adjust it."
            ),
        )

    if "drive oauth not connected" in low or "google drive connected" in low:
        return apply(
            route_to_chat=False,
            category="auth",
            reason="drive_oauth_required",
            assistant_message=(
                "This failure is caused by Google Drive authentication, so I left it as a direct action instead of routing it to chat. "
                "Reconnect Google Drive and retry."
            ),
        )

    if "youtube oauth" in low or "upload to youtube" in low:
        return apply(
            route_to_chat=False,
            category="auth",
            reason="youtube_oauth_issue",
            assistant_message=(
                "This is a YouTube authentication problem, so it is better handled directly by reconnecting the account than by sending it to chat."
            ),
        )

    if "shotstack" in low and ("0 credits" in low or "sandbox environment" in low or "403" in low):
        return apply(
            route_to_chat=False,
            category="billing",
            reason="shotstack_plan_limit",
            assistant_message=(
                "This is a Shotstack account or environment issue, so I did not route it into chat. "
                "Use a funded account or a production key with the production host, then retry."
            ),
        )

    if "requires" in low and "sources" in low and "received" in low:
        return apply(
            route_to_chat=True,
            category="input",
            reason="source_count_mismatch",
            assistant_message=(
                "The pipeline needs more source videos for the mode you selected. "
                "Add more source footage, or ask me in chat to switch to a mode that can work with fewer clips."
            ),
        )

    return feedback
