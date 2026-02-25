from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
from Pipeline import Assemble_Pipeline
from dotenv import load_dotenv
from pydantic import BaseModel
load_dotenv()

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

# Default values from .env as fallbacks
DEFAULT_FOLDER = os.getenv("VIDEO_FOLDER")
DEFAULT_MUSIC = os.getenv("MUSIC_URL")
DEEPSEEK_API= os.getenv("DEEPSEEK_KEY")
@app.post("/process-video")
async def process_video(
    prompt: str = Form(...), 
    video: UploadFile = File(...),
    folder_id: str = Form(None), # Optional: UI can override .env
    music_url: str = Form(None)  # Optional: UI can override .env
):
    # 1. Save the uploaded video locally
    temp_path = f"temp_{video.filename}"
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(video.file, buffer)
    
    # 2. Determine which assets to use (Request value OR .env default)
    active_folder = folder_id or DEFAULT_FOLDER
    active_music = music_url or DEFAULT_MUSIC

    try:
        # 3. Run updated pipeline logic with 4 arguments
        result = Assemble_Pipeline(
            file_path=temp_path, 
            prompt=prompt, 
            folder_id=active_folder, 
            music_url=active_music
        )
        return result
        
    except Exception as e:
        return {"success": False, "error": str(e)}
        
    finally:
        # 4. Cleanup
        if os.path.exists(temp_path):
            os.remove(temp_path)


class ChatTurn(BaseModel):
    user_input: str
    current_state: dict
    analyzer_output: str

@app.post("/chat")
async def handle_chat(turn: ChatTurn):
    # This calls the logic we wrote previously
    result = process_ui_turn(
        turn.user_input, 
        turn.current_state, 
        turn.analyzer_output, 
        DEEPSEEK_API
    )
    return result # This sends the JSON back to your UI
