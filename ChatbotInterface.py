import json
import requests
import re
from datetime import datetime
from typing import List, Dict, Optional

def generate_video_requirements_report(
    analyzer_output: str, 
    user_instructions: List[str], 
    api_key: str
) -> str:
    """
    Pipeline function that takes video analysis text and user instructions, 
    processes them to extract structured requirements, and generates a final project brief.
    """

    # --- Configuration & Constants ---
    API_URL = "https://openrouter.ai/api/v1/chat/completions"
    MODEL_NAME = "deepseek/deepseek-chat"
    
    REQUIRED_INFO_SCHEMA = {
        "video_topic": None,
        "target_audience": None,
        "platform": None,
        "call_to_action": None,
        "branding": None,
        "subtitles": None,
        "deadline": None
    }

    conversation_state = {
        "conversation_history": [],
        "current_info": REQUIRED_INFO_SCHEMA.copy(),
        "completed": False
    }

    # --- Helper Functions ---

    def call_llm(system_prompt: str, user_prompt: str) -> str:
        """Handles the API request using the verified working configuration."""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost",
            "X-Title": "Video-Edit-Pipeline"
        }
        payload = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.3
        }

        # Use raise_for_status() to catch 401/404 errors immediately
        response = requests.post(API_URL, headers=headers, json=payload)
        
        if response.status_code != 200:
            # This will be caught by the try-except in analyze_instruction
            raise Exception(f"LLM Error {response.status_code}: {response.text}")

        return response.json()["choices"][0]["message"]["content"]

    def analyze_instruction(current_state: Dict, user_input: str) -> Dict:
        system_prompt = "You are an assistant that extracts video requirements into JSON."
        user_prompt = f"Context: {analyzer_output}\nInput: {user_input}\nReturn JSON."

        try:
            raw_response = call_llm(system_prompt, user_prompt)
            # Clean and Parse JSON logic...
            match = re.search(r"\{.*\}", raw_response, re.DOTALL)
            json_str = match.group(0).strip() if match else raw_response
            return json.loads(json_str)
        except Exception as e:
            print(f" Critical LLM failure: {e}")
            # Returning an empty dict prevents the 'str has no attribute get' error
            return {"updated_info": {}, "missing_fields": []}

    def generate_final_report(state: Dict) -> str:
        prompt = f"Generate a final brief based on these requirements: {json.dumps(state['current_info'])}"
        try:
            return call_llm("You are a professional video editor.", prompt)
        except:
            return "Final report could not be generated due to API error."

    # --- Main Pipeline Execution Logic ---
    print(" Starting Requirements Gathering...")

    for i, instruction in enumerate(user_instructions):
        print(f"   Processing instruction {i+1}/{len(user_instructions)}...")
        conversation_state["conversation_history"].append({"role": "user", "content": instruction})
        
        result = analyze_instruction(conversation_state, instruction)
        
        # This is where the .get() error was happening; now result is guaranteed to be a dict
        updated = result.get("updated_info", {})
        conversation_state["current_info"].update(updated)

    print("Generating Final Report...")
    return generate_final_report(conversation_state)