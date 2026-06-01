from __future__ import annotations

import re
from typing import Any, Dict, List

from ai_editor.edit_contracts.user_plan import SlotReplacement, TextReplacement, UserPatchedPlan

def build_user_patched_plan(
    requirements: Dict[str, Any],
    request_payload: Dict[str, Any],
    reference_template: Dict[str, Any],
) -> Dict[str, Any]:
    # Check if there is an existing user_patched_plan in requirements
    if requirements.get("user_patched_plan"):
        existing = requirements["user_patched_plan"]
        if isinstance(existing, dict):
            # Return restored dict representation
            try:
                return UserPatchedPlan.from_dict(existing).to_dict()
            except Exception:
                pass

    slot_replacements: List[SlotReplacement] = []
    text_replacements: List[TextReplacement] = []

    # 1. Convert slot_mapping from request_payload or requirements
    slot_mapping = request_payload.get("slot_mapping") or requirements.get("slot_mapping") or []
    if isinstance(slot_mapping, list):
        for item in slot_mapping:
            if isinstance(item, dict):
                slot_id = item.get("slot_id") or item.get("slot") or item.get("index")
                if slot_id is not None:
                    # Clip id is either clip_id, source_id, or value
                    clip_id = item.get("clip_id") or item.get("source_id") or item.get("id")
                    if clip_id is not None:
                        clip_id = str(clip_id)
                    slot_replacements.append(SlotReplacement(
                        slot_id=int(slot_id),
                        clip_id=clip_id,
                        source_index=item.get("source_index"),
                        replacement_text=item.get("replacement_text") or item.get("text"),
                        source_start=item.get("source_start") or item.get("trim"),
                        source_end=item.get("source_end"),
                    ))

    # 2. Add explicit slot replacements from requirements
    explicit_slots = requirements.get("slot_replacements") or []
    if isinstance(explicit_slots, list):
        for item in explicit_slots:
            if isinstance(item, dict):
                slot_id = item.get("slot_id")
                if slot_id is not None:
                    slot_replacements.append(SlotReplacement.from_dict(item))

    # 3. Add explicit text replacements from requirements
    explicit_texts = requirements.get("text_replacements") or []
    if isinstance(explicit_texts, list):
        for item in explicit_texts:
            if isinstance(item, dict):
                text_replacements.append(TextReplacement.from_dict(item))

    # 4. Parse simple edit requests phrases conservatively
    edit_requests: List[str] = []
    for key in ("edit_requests", "user_requests"):
        values = requirements.get(key) or []
        if isinstance(values, list):
            edit_requests.extend(str(item or "").strip() for item in values if str(item or "").strip())

    for req in edit_requests:
        req_raw = str(req or "").strip()
        req_str = req_raw.lower()
        # "replace first text with X" or "replace text for slot 1 with X"
        m1 = re.search(r"replace\s+first\s+text\s+with\s+(.+)", req_str)
        if m1:
            text_replacements.append(TextReplacement(slot_id=1, new_text=m1.group(1).strip()))

        m2 = re.search(r"replace\s+second\s+text\s+with\s+(.+)", req_str)
        if m2:
            text_replacements.append(TextReplacement(slot_id=2, new_text=m2.group(1).strip()))

        m3 = re.search(r"slot\s+(\d+)\s+text\s+(?:should be|to|is|with)\s+(.+)", req_str)
        if m3:
            text_replacements.append(TextReplacement(
                slot_id=int(m3.group(1)),
                new_text=m3.group(2).strip(),
            ))

    # De-duplicate replacements by slot_id (preferring explicit or newer)
    final_slots: Dict[int, SlotReplacement] = {}
    for r in slot_replacements:
        final_slots[r.slot_id] = r
    
    # De-duplicate texts by slot_id and text content
    final_texts: List[TextReplacement] = []
    seen_text_slots = set()
    for t in text_replacements:
        if t.slot_id is not None:
            if t.slot_id not in seen_text_slots:
                final_texts.append(t)
                seen_text_slots.add(t.slot_id)
        else:
            final_texts.append(t)

    # Defaults
    preserve = {
        "timing": True,
        "transitions": True,
        "caption_style": True,
        "visual_style": True,
        "audio": True
    }
    # Allow requirements to override preserve flags
    req_preserve = requirements.get("preserve") or {}
    if isinstance(req_preserve, dict):
        preserve.update(req_preserve)

    plan = UserPatchedPlan(
        slot_replacements=list(final_slots.values()),
        text_replacements=final_texts,
        preserve=preserve,
        user_notes=str(requirements.get("user_notes", "")),
        raw_requirements=dict(requirements),
    )
    payload = plan.to_dict()
    payload["prompt"] = str(request_payload.get("prompt") or requirements.get("prompt") or "")
    return payload
