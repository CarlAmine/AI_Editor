# import json
# import requests
# import re
# from datetime import datetime
# from typing import List, Dict, Optional

# def generate_video_requirements_report(
#     analyzer_output: str, 
#     user_instructions: List[str], 
#     api_key: str
# ) -> str:
#     """
#     Pipeline function that takes video analysis text and user instructions, 
#     processes them to extract structured requirements, and generates a final project brief.
#     """

#     # --- Configuration & Constants ---
#     API_URL = "https://openrouter.ai/api/v1/chat/completions"
#     MODEL_NAME = "deepseek/deepseek-chat"
    
#     REQUIRED_INFO_SCHEMA = {
#         "video_topic": None,
#         "target_audience": None,
#         "platform": None,
#         "call_to_action": None,
#         "branding": None,
#         "subtitles": None,
#         "deadline": None
#     }

#     conversation_state = {
#         "conversation_history": [],
#         "current_info": REQUIRED_INFO_SCHEMA.copy(),
#         "completed": False
#     }

#     # --- Helper Functions ---

#     def call_llm(system_prompt: str, user_prompt: str) -> str:
#         """Handles the API request using the verified working configuration."""
#         headers = {
#             "Authorization": f"Bearer {api_key}",
#             "Content-Type": "application/json",
#             "HTTP-Referer": "http://localhost",
#             "X-Title": "Video-Edit-Pipeline"
#         }
#         payload = {
#             "model": MODEL_NAME,
#             "messages": [
#                 {"role": "system", "content": system_prompt},
#                 {"role": "user", "content": user_prompt}
#             ],
#             "temperature": 0.3
#         }

#         # Use raise_for_status() to catch 401/404 errors immediately
#         response = requests.post(API_URL, headers=headers, json=payload)
        
#         if response.status_code != 200:
#             # This will be caught by the try-except in analyze_instruction
#             raise Exception(f"LLM Error {response.status_code}: {response.text}")

#         return response.json()["choices"][0]["message"]["content"]

#     def analyze_instruction(current_state: Dict, user_input: str) -> Dict:
#         system_prompt = "You are an assistant that extracts video requirements into JSON."
#         user_prompt = f"Context: {analyzer_output}\nInput: {user_input}\nReturn JSON."

#         try:
#             raw_response = call_llm(system_prompt, user_prompt)
#             # Clean and Parse JSON logic...
#             match = re.search(r"\{.*\}", raw_response, re.DOTALL)
#             json_str = match.group(0).strip() if match else raw_response
#             return json.loads(json_str)
#         except Exception as e:
#             print(f" Critical LLM failure: {e}")
#             # Returning an empty dict prevents the 'str has no attribute get' error
#             return {"updated_info": {}, "missing_fields": []}

#     def generate_final_report(state: Dict) -> str:
#         prompt = f"Generate a final brief based on these requirements: {json.dumps(state['current_info'])}"
#         try:
#             return call_llm("You are a professional video editor.", prompt)
#         except:
#             return "Final report could not be generated due to API error."

#     # --- Main Pipeline Execution Logic ---
#     print(" Starting Requirements Gathering...")

#     for i, instruction in enumerate(user_instructions):
#         print(f"   Processing instruction {i+1}/{len(user_instructions)}...")
#         conversation_state["conversation_history"].append({"role": "user", "content": instruction})
        
#         result = analyze_instruction(conversation_state, instruction)
        
#         # This is where the .get() error was happening; now result is guaranteed to be a dict
#         updated = result.get("updated_info", {})
#         conversation_state["current_info"].update(updated)

#     print("Generating Final Report...")
#     return generate_final_report(conversation_state)
import json
import requests
import re
from typing import Dict, List, Optional

# --- Configuration & Constants ---
API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_NAME = "deepseek/deepseek-chat"

REQUIRED_FIELDS = [
    "video_topic", "target_audience", "platform", 
    "call_to_action", "branding", "subtitles", "deadline"
]

def process_ui_turn(
    user_input: str, 
    current_state: Dict, 
    analyzer_output: str, 
    api_key: str
) -> Dict:
    """
    Processes a single interaction from the UI.
    """
    
    # 1. Extraction: Update state based on user input
    extraction_prompt = (
        f"Extract video requirements from: '{user_input}'. "
        f"Context from video analysis: {analyzer_output}. "
        f"Current known info: {json.dumps(current_state)}. "
        f"Update these specific keys: {REQUIRED_FIELDS}. "
        "Return ONLY a JSON object with found fields. If a field isn't mentioned, don't include it."
    )
    
    extracted_data = _call_llm_json(extraction_prompt, api_key)
    
    # Log for debugging in Render
    print(f"DEBUG: Input: {user_input} | Extracted: {extracted_data}") 
    
    # Merge extracted data into current state
    if isinstance(extracted_data, dict):
        for key in REQUIRED_FIELDS:
            if key in extracted_data and extracted_data[key]:
                current_state[key] = extracted_data[key]

    # 2. Check for missing fields
    missing = [k for k in REQUIRED_FIELDS if current_state.get(k) is None]

    # 3. Handle Completion
    if not missing:
        report = _generate_final_report(current_state, api_key)
        return {
            "updated_state": current_state,
            "next_message": "Perfect! I've gathered everything I need for your project brief.",
            "is_complete": True,
            "final_report": report
        }

    # 4. Generate next question if not complete
    question_prompt = (
        f"We are missing: {missing}. "
        f"Current info: {json.dumps(current_state)}. "
        "Ask the user a friendly, short question to get the next missing piece of information."
    )
    
    next_question = _call_llm_text(question_prompt, api_key)

    return {
        "updated_state": current_state,
        "next_message": next_question,
        "is_complete": False,
        "final_report": None
    }

# --- Internal LLM Helpers ---

def _call_llm_json(prompt: str, api_key: str) -> Dict:
    headers = {
        "Authorization": f"Bearer {api_key}", 
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "Video-Edit-Pipeline"
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "You are a data extractor. Output ONLY pure JSON."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0
    }
    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        response.raise_for_status() # Raises error for 401, 402, 500, etc.
        
        resp_data = response.json()
        
        if "choices" not in resp_data:
            print(f"!!! API Error Response: {resp_data}")
            return {}

        content = resp_data["choices"][0]["message"]["content"]
        
        # Regex to ensure we only get the JSON block
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return json.loads(content)
        
    except Exception as e:
        print(f"Extraction Error Trace: {e}")
        return {}

def _call_llm_text(prompt: str, api_key: str) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}", 
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "You are a helpful video producer assistant."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }
    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Text Generation Error: {e}")
        return "I'm sorry, I'm having trouble connecting to my brain right now. Could you try again?"

def _generate_final_report(state: Dict, api_key: str) -> str:
    return _call_llm_text(f"Generate a professional video production brief from these requirements: {json.dumps(state)}", api_key)
