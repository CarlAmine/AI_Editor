from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import shutil
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Optional

from ai_editor.pipeline import Assemble_Pipeline
from ai_editor.chatbot_interface import process_ui_turn

load_dotenv()

app = FastAPI(
    title="AI Editor",
    description="Video analysis and automated editing pipeline with conversational brief builder.",
    version="1.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

# Optional static frontend (only if a 'static' directory exists)
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
HAS_STATIC = os.path.isdir(STATIC_DIR)

if HAS_STATIC:
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def root():
    """Redirect root path to the web UI if present, otherwise to API docs."""
    if HAS_STATIC:
        return RedirectResponse(url="/static/index.html")
    return RedirectResponse(url="/api/docs")


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
GROQ_API_KEY = os.getenv("GROQ")
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
    current_state: dict = {} 
    analyzer_output: str = ""

@app.post("/chat")
async def handle_chat(turn: ChatTurn):
    # This calls the logic we wrote previously
    result = process_ui_turn(
        turn.user_input, 
        turn.current_state, 
        turn.analyzer_output, 
        GROQ_API_KEY
    )
    return result # This sends the JSON back to your UI
