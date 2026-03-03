import json
import os
from typing import Any, Dict, List, Optional

from groq import Groq

# LLM client configuration (shared with the chatbot module via the same env var)
GROQ_API_KEY = os.getenv("GROQ")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
MODEL_NAME = "llama-3.3-70b-versatile"


def generate_overlay_plan(
    analysis_results: Dict[str, Any],
    user_prompt: str,
    analysis_summary: Optional[str] = None,
    tone: Optional[str] = None,
    pacing: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Use the analyzer output + a short user request to build a list of
    timestamped overlay captions.

    Each overlay dict has the shape:
        {
            "timestamp": float,   # seconds, based on analyzer timestamps
            "text": str,          # short caption
            "position": str       # "top" | "middle" | "bottom" | "center"
        }
    """
    if not client:
        # Groq is not configured; caller should fall back to simple behavior.
        print("Overlay planner: GROQ API key is not set; skipping overlay generation.")
        return []

    keyframes = analysis_results.get("keyframes") or []
    if not keyframes:
        print("Overlay planner: analysis_results has no keyframes; cannot generate overlays.")
        return []

    # Keep only keyframes where we have some detected text, so we don't spam the model.
    interesting = []
    for kf in keyframes:
        detected_text = kf.get("detected_text") or ""
        if not detected_text or detected_text == "No text":
            continue
        try:
            ts = float(kf.get("timestamp", 0.0))
        except (TypeError, ValueError):
            continue
        interesting.append(
            {
                "timestamp": ts,
                "detected_text": detected_text,
                "easyocr_details": kf.get("easyocr_details", []),
            }
        )

    if not interesting:
        print(
            "Overlay planner: no keyframes with meaningful detected_text; "
            "falling back to simple prompt-based overlay."
        )
        return []

    # Limit how much we send to the model for cost/reliability.
    interesting = interesting[:20]

    overlays_hint = {
        "keyframes_with_text": interesting,
    }

    summary_snippet = analysis_summary or ""
    if len(summary_snippet) > 1200:
        summary_snippet = summary_snippet[:1200] + "…"

    # Build style hints from tone/pacing if provided
    style_hints = ""
    if tone or pacing:
        style_hints = "\nStyle guidance from requirements:\n"
        if tone:
            style_hints += f"- Tone: {tone}\n"
        if pacing:
            style_hints += f"- Pacing: {pacing}\n"
        style_hints += "Use this to guide caption wording and intensity.\n"

    user_message = (
        "You are planning on-screen captions for a video.\n"
        "You must ONLY place captions at timestamps that come from the list "
        "of keyframes I provide. Do not invent new timestamps.\n\n"
        f"User request / style notes: {user_prompt!r}\n"
        f"{style_hints}\n"
        "Optional analysis summary (do not assume it is complete):\n"
        f"{summary_snippet}\n\n"
        "Keyframes with text (JSON, in chronological order):\n"
        f"{json.dumps(overlays_hint, ensure_ascii=False)}\n\n"
        "Your task:\n"
        "- For EACH entry in keyframes_with_text, create exactly ONE caption.\n"
        "- Keep the same order and the same 'timestamp' value for that entry.\n"
        "- Rewrite the detected_text into a short, readable caption that matches "
        "the user's request and style, but do not invent facts that are not "
        "supported by the analysis or the user's request.\n"
        "- Optionally set 'position' to 'top', 'middle', or 'bottom'. "
        "If unsure, default to 'bottom'.\n\n"
        "Return a JSON object with a single key 'overlays' whose value is an "
        "array of objects with exactly these keys: timestamp, text, position.\n"
        "Example:\n"
        "{\n"
        '  \"overlays\": [\n'
        '    {\"timestamp\": 3.2, \"text\": \"Discover the hidden forest\", \"position\": \"top\"}\n'
        "  ]\n"
        "}\n"
    )

    # Write a small debug payload so you can inspect what was sent to the model.
    try:
        with open("overlay_debug_payload.json", "w", encoding="utf-8") as f:
            json.dump(
                {
                    "user_prompt": user_prompt,
                    "summary_snippet": summary_snippet,
                    "overlays_hint": overlays_hint,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
    except Exception as e:
        print(f"Overlay planner: failed to write overlay_debug_payload.json: {e}")

    try:
        completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a precise caption planner. "
                        "You MUST NOT invent events or timestamps. "
                        "Use only the provided timestamps and keep captions short "
                        "(max ~8 words). Output VALID JSON only."
                    ),
                },
                {"role": "user", "content": user_message},
            ],
            model=MODEL_NAME,
            response_format={"type": "json_object"},
            temperature=0,
        )
        raw = completion.choices[0].message.content
        data = json.loads(raw)
        overlays = data.get("overlays") or []
        if not isinstance(overlays, list):
            print("Overlay planner: model returned a non-list 'overlays'; falling back.")
            return []

        # Also dump the planned overlays to a debug file for inspection.
        try:
            with open("overlay_plan_debug.json", "w", encoding="utf-8") as f:
                json.dump(overlays, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Overlay planner: failed to write overlay_plan_debug.json: {e}")

        return overlays
    except Exception as e:
        print(f"Groq overlay planning error: {e}")
        return []

