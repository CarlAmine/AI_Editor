# Legacy OpenRouter-based implementation is kept commented out for reference.
# The active implementation uses Groq for extraction and brief generation.

import json
import re
from groq import Groq
from typing import Dict, List, Optional
import os

# --- Configuration ---
# You can hardcode the key like your example, but os.getenv("GROQ_API_KEY") is safer!
GROQ_API_KEY = os.getenv("GROQ")
client = Groq(api_key=GROQ_API_KEY)
MODEL_NAME = "llama-3.3-70b-versatile"

# Collected fields that power the "current_state" JSON shown in the UI.
# Keep these relatively stable; only extend or rename with care.
REQUIRED_FIELDS = [
    # Core description
    "video_topic",           # What the video is about
    "target_audience",       # Who it is for
    "platform",              # e.g. YouTube, TikTok, Instagram Reels

    # Structure & length
    "duration_seconds",      # Target runtime in seconds (number, or null)
    "aspect_ratio",          # e.g. 16:9, 9:16, 1:1
    "orientation",           # e.g. vertical, horizontal, square

    # Creative style
    "tone",                  # e.g. playful, serious, cinematic
    "pacing",                # e.g. fast cuts, slow and calm
    "style_reference",       # Optional reference show/creator/style

    # Business / messaging
    "call_to_action",        # e.g. sign up, subscribe, visit website
    "branding",              # Brand name, colors, logo usage
    "subtitles",             # e.g. yes/no, language, style

    # Practical details
    "deadline",              # When the video is needed
    "budget",                # Optional budget notes, currency as text
]


def process_ui_turn(
    user_input: str,
    current_state: Dict,
    analyzer_output: str,
    api_key: str = None,  # Kept for compatibility with your app.py call
) -> Dict:
    # 1. Extraction Logic
    extraction_prompt = (
        "You will extract structured video requirements from a short user message.\n"
        "Use ONLY information that is explicitly and clearly stated by the user "
        "or in the analysis context. If something is not clearly specified, "
        "you MUST set that field to null instead of guessing.\n\n"
        "Field semantics:\n"
        "- video_topic: short description of what the video is about.\n"
        "- target_audience: who this is for.\n"
        "- platform: main publishing platform (e.g. YouTube, TikTok).\n"
        "- duration_seconds: numeric target runtime in seconds (e.g. 60, 90). "
        "If user only says '1 minute', convert to 60.\n"
        "- aspect_ratio: aspect ratio string like '16:9' or '9:16'.\n"
        "- orientation: 'vertical', 'horizontal', or 'square'.\n"
        "- tone: adjectives describing tone (e.g. 'playful', 'serious').\n"
        "- pacing: description of pacing (e.g. 'fast cuts', 'slow and calm').\n"
        "- style_reference: any reference shows, creators, brands, or examples.\n"
        "- call_to_action: the main viewer action to encourage.\n"
        "- branding: brand name and important brand notes.\n"
        "- subtitles: subtitle preference (yes/no, language, style).\n"
        "- deadline: when the video is needed.\n"
        "- budget: any budget notes (string; you do not need to parse currency).\n\n"
        f"User message: {user_input!r}\n"
        f"Analysis context (may be empty): {analyzer_output}\n\n"
        f"Return a JSON object with exactly these keys: {REQUIRED_FIELDS}.\n"
        "For each key:\n"
        "- If the value is clearly mentioned, copy it (and for duration_seconds, use a number in seconds).\n"
        "- If it is not mentioned, or you are unsure, set it to null.\n"
        "Do NOT invent brands, platforms, durations, deadlines, budgets, or other details.\n"
    )
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a STRICT data extractor. "
                        "Output ONLY valid JSON, and NEVER hallucinate or guess values. "
                        "Use null when information is missing."
                    ),
                },
                {"role": "user", "content": extraction_prompt},
            ],
            model=MODEL_NAME,
            response_format={"type": "json_object"},  # Ensures Groq sends valid JSON
            temperature=0,
        )
        extracted_data = json.loads(chat_completion.choices[0].message.content)
    except Exception as e:
        print(f"Groq Extraction Error: {e}")
        extracted_data = {}

    # Merge data
    for key in REQUIRED_FIELDS:
        if key in extracted_data and extracted_data[key]:
            current_state[key] = extracted_data[key]

    # 2. Check for missing fields
    missing = [k for k in REQUIRED_FIELDS if current_state.get(k) is None]

    # 3. Handle Completion
    if not missing:
        report = _generate_final_report(current_state)
        return {
            "updated_state": current_state,
            "next_message": "Perfect! I've gathered everything I need.",
            "is_complete": True,
            "final_report": report,
        }

    # 4. Generate next question
    question_prompt = (
        f"We are missing: {missing}. Current info: {json.dumps(current_state)}. "
        "Ask a short, friendly question to get the next missing piece."
    )
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a helpful video producer."},
                {"role": "user", "content": question_prompt},
            ],
            model=MODEL_NAME,
            temperature=0.7,
        )
        next_question = chat_completion.choices[0].message.content
    except Exception as e:
        print(f"Groq Text Error: {e}")
        next_question = "I'm sorry, I hit a snag. Could you repeat that?"

    return {
        "updated_state": current_state,
        "next_message": next_question,
        "is_complete": False,
        "final_report": None,
    }


def _generate_final_report(state: Dict) -> str:
    try:
        completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a professional video editor."},
                {
                    "role": "user",
                    "content": f"Create a brief from: {json.dumps(state)}",
                },
            ],
            model=MODEL_NAME,
        )
        return completion.choices[0].message.content
    except Exception:
        return "Report generation failed."

