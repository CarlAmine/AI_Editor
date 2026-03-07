from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import shutil
import os
import re
import json
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Optional, List
from urllib.parse import parse_qs, urlparse

from ai_editor.pipeline import Assemble_Pipeline
from ai_editor.chatbot_interface import process_ui_turn
from ai_editor.youtube_clipper import YouTubeClipper
from ai_editor.youtube_uploader import YouTubeUploader, YouTubeUploadError

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

TMP_JOBS_DIR = os.path.join(os.path.dirname(__file__), "tmp", "jobs")
os.makedirs(TMP_JOBS_DIR, exist_ok=True)
app.mount("/files", StaticFiles(directory=TMP_JOBS_DIR), name="files")


def _state_file_path(project_id: str) -> str:
    return os.path.join(TMP_JOBS_DIR, project_id, "state.json")


def _mark_youtube_uploaded_and_cleanup(project_id: str) -> None:
    state_path = _state_file_path(project_id)
    if not os.path.exists(state_path):
        return
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
        state["youtube_uploaded"] = True
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

        work_dir = state.get("work_dir")
        job_dir = os.path.join(TMP_JOBS_DIR, project_id)
        if os.path.isdir(job_dir):
            shutil.rmtree(job_dir, ignore_errors=True)
    except Exception as e:
        print(f"[cleanup] Failed deferred cleanup for project {project_id}: {e}")


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
GROQ_API_KEY = os.getenv("GROQ")
# Request/Response Models

class VideoSegment(BaseModel):
    """Time segment for video clipping."""
    start: float
    end: float


class VideoSource(BaseModel):
    """Source video specification."""
    label: int
    url: str
    segments: Optional[List[VideoSegment]] = None


class ProcessVideoURLRequest(BaseModel):
    """New URL-based video processing request."""
    primary_url: str
    sources: List[VideoSource]
    prompt: str
    music_mode: str = "original"  # "original" or "custom"
    custom_music_url: Optional[str] = None
    google_drive_link: Optional[str] = None
    job_id: Optional[str] = None
    requirements_state: Optional[dict] = {}


def extract_drive_folder_id(link_or_id: Optional[str]) -> Optional[str]:
    """
    Accept a Drive folder URL or plain folder ID and return the folder ID.
    Supported URL styles:
    - https://drive.google.com/drive/folders/<FOLDER_ID>
    - https://drive.google.com/open?id=<FOLDER_ID>
    """
    if not link_or_id:
        return None

    value = link_or_id.strip()
    if not value:
        return None

    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return value

    query = parse_qs(parsed.query or "")
    if "id" in query and query["id"]:
        return query["id"][0]

    match = re.search(r"/folders/([a-zA-Z0-9_-]+)", parsed.path or "")
    if match:
        return match.group(1)

    return None


@app.post("/process-video-url")
async def process_video_url(request: ProcessVideoURLRequest):
    """
    Process videos from YouTube/TikTok URLs.
    
    Request:
    {
        "primary_url": "https://youtube.com/watch?v=...",
        "sources": [
            {
                "label": 1,
                "url": "https://youtube.com/watch?v=...",
                "segments": [{"start": 10, "end": 30}, {"start": 45, "end": 60}]
            }
        ],
        "prompt": "Make it energetic with fast cuts",
        "music_mode": "original",
        "custom_music_url": null,
        "google_drive_link": "https://drive.google.com/drive/folders/..."
    }
    """
    try:
        folder_id = extract_drive_folder_id(request.google_drive_link)
        if request.google_drive_link and not folder_id:
            return {
                "success": False,
                "error": "Invalid Google Drive folder link. Please provide a valid folder URL or folder ID."
            }

        if not request.sources and not folder_id:
            return {
                "success": False,
                "error": "Please provide at least one source video or a Google Drive folder link."
            }

        # Convert Pydantic models to dicts for pipeline
        sources_list = []
        for source in request.sources:
            segments = None
            if source.segments:
                segments = [{"start": s.start, "end": s.end} for s in source.segments]
            sources_list.append({
                "label": source.label,
                "url": source.url,
                "segments": segments,
            })
        
        result = Assemble_Pipeline(
            primary_url=request.primary_url,
            sources=sources_list,
            prompt=request.prompt,
            music_mode=request.music_mode,
            custom_music_url=request.custom_music_url,
            requirements_state=request.requirements_state or {},
            job_id=request.job_id,
            gdrive_folder_id=folder_id,
        )
        return result
        
    except Exception as e:
        print(f"ERROR in /process-video-url: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


# Legacy endpoint (kept for compatibility)
@app.post("/process-video")
async def process_video(
    prompt: str = Form(...), 
    video: UploadFile = File(...),
    requirements_state: str = Form(None)
):
    """
    DEPRECATED: File upload endpoint. Use /process-video-url instead.
    
    This endpoint is maintained for backwards compatibility only.
    """
    return {
        "success": False,
        "error": "File upload workflow has been deprecated. Please use /process-video-url with YouTube/TikTok URLs instead.",
        "migration_guide": "See API documentation for /process-video-url"
    }


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


# ============= YOUTUBE CLIPPER ENDPOINTS =============

class YouTubeClipRequest(BaseModel):
    """Request model for single YouTube clip."""
    youtube_url: str
    start_time: str  # Can be seconds, MM:SS, or HH:MM:SS format
    end_time: str
    clip_name: Optional[str] = None
    output_folder_id: str = "1Kdu-CDI670WegvpFiK2ypPDtoqvlO0K8"  # Default folder ID


class YouTubeClipItem(BaseModel):
    """Single clip specification in batch request."""
    url: str
    start_time: str
    end_time: str
    name: Optional[str] = None


class YouTubeClipBatchRequest(BaseModel):
    """Request model for batch YouTube clips."""
    clips: List[YouTubeClipItem]
    output_folder_id: str = "1Kdu-CDI670WegvpFiK2ypPDtoqvlO0K8"  # Default folder ID


class YouTubeApprovedUploadRequest(BaseModel):
    """Upload an approved rendered video from Shotstack URL to YouTube."""
    render_url: str
    title: str
    description: Optional[str] = ""
    privacy_status: str = "private"  # private | public | unlisted
    tags: Optional[List[str]] = None
    category_id: str = "22"
    made_for_kids: bool = False
    project_id: Optional[str] = None


@app.post("/youtube-clip")
async def clip_youtube_video(request: YouTubeClipRequest):
    """
    Clip a YouTube video and upload to Google Drive.
    
    Request body:
    {
        "youtube_url": "https://www.youtube.com/watch?v=...",
        "start_time": "1:30" or "0:01:30" or "90",
        "end_time": "3:45" or "0:03:45" or "225",
        "clip_name": "my_clip.mp4" (optional),
        "output_folder_id": "1Kdu-CDI670WegvpFiK2ypPDtoqvlO0K8" (optional)
    }
    """
    try:
        clipper = YouTubeClipper()
        result = clipper.process_youtube_clip(
            yt_url=request.youtube_url,
            start_time=request.start_time,
            end_time=request.end_time,
            output_folder_id=request.output_folder_id,
            clip_name=request.clip_name,
        )
        return result
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


@app.post("/youtube-clip-batch")
async def clip_youtube_videos_batch(request: YouTubeClipBatchRequest):
    """
    Clip multiple YouTube videos and upload to Google Drive.
    
    Request body:
    {
        "clips": [
            {
                "url": "https://www.youtube.com/watch?v=...",
                "start_time": "1:30",
                "end_time": "3:45",
                "name": "clip1.mp4" (optional)
            },
            {
                "url": "https://www.youtube.com/watch?v=...",
                "start_time": "0:30",
                "end_time": "2:00",
                "name": "clip2.mp4" (optional)
            }
        ],
        "output_folder_id": "1Kdu-CDI670WegvpFiK2ypPDtoqvlO0K8" (optional)
    }
    """
    try:
        clipper = YouTubeClipper()
        clips_data = [
            {
                "url": clip.url,
                "start_time": clip.start_time,
                "end_time": clip.end_time,
                "name": clip.name,
            }
            for clip in request.clips
        ]
        result = clipper.process_batch_clips(
            clips_data=clips_data,
            output_folder_id=request.output_folder_id,
        )
        return result
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "total": len(request.clips),
            "successful": 0,
            "failed": len(request.clips),
        }


@app.post("/upload-approved-video-youtube")
async def upload_approved_video_to_youtube(request: YouTubeApprovedUploadRequest):
    """
    Upload a user-approved rendered video (from Shotstack URL) to YouTube.
    This endpoint should be called only after user previews and approves the video.
    """
    try:
        uploader = YouTubeUploader()
        result = uploader.upload_from_render_url(
            render_url=request.render_url,
            title=request.title,
            description=request.description or "",
            privacy_status=request.privacy_status,
            tags=request.tags or [],
            category_id=request.category_id,
            made_for_kids=request.made_for_kids,
        )
        if result.get("success") and request.project_id:
            _mark_youtube_uploaded_and_cleanup(request.project_id)
        return result
    except YouTubeUploadError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"YouTube upload failed: {str(e)}"}

