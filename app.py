from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, HTMLResponse, FileResponse
import shutil
import os
import re
import json
import time
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Optional, List
from urllib.parse import parse_qs, urlparse

from ai_editor.pipeline import Assemble_Pipeline
from ai_editor.chatbot_interface import process_ui_turn
from ai_editor.google_auth import (
    build_drive_service_oauth,
    GoogleCredentialError,
    resolve_drive_oauth_client_secret_path,
    resolve_drive_token_path,
)
from pipeline.providers import get_provider_health
from pipeline.state import (
    JobStatus,
    build_controller_status_payload,
    load_state,
    sanitize_decision_trace_entries,
)

load_dotenv()

app = FastAPI(
    title="AI Editor",
    description="Video analysis and automated editing pipeline with conversational brief builder.",
    version="1.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

APP_DIR = Path(__file__).resolve().parent
TMP_JOBS_DIR = APP_DIR / "tmp" / "jobs"
TMP_JOBS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/files", StaticFiles(directory=str(TMP_JOBS_DIR)), name="files")
DRIVE_OAUTH_PENDING = {}


def _find_frontend_dist() -> Optional[Path]:
    candidates = (
        APP_DIR / "static",
        APP_DIR / "frontend" / "dist",
    )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


FRONTEND_DIST_DIR = _find_frontend_dist()


def _frontend_index_path() -> Optional[Path]:
    if FRONTEND_DIST_DIR is None:
        return None
    index_path = FRONTEND_DIST_DIR / "index.html"
    if index_path.is_file():
        return index_path
    return None


def _resolve_frontend_asset_path(relative_path: str) -> Optional[Path]:
    if FRONTEND_DIST_DIR is None:
        return None

    requested_path = (relative_path or "").lstrip("/")
    candidate = (FRONTEND_DIST_DIR / requested_path).resolve()
    dist_root = FRONTEND_DIST_DIR.resolve()

    if candidate != dist_root and dist_root not in candidate.parents:
        return None
    if candidate.is_file():
        return candidate
    return None


def _state_file_path(project_id: str) -> str:
    return str(TMP_JOBS_DIR / project_id / "state.json")


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
        job_dir = TMP_JOBS_DIR / project_id
        if job_dir.is_dir():
            shutil.rmtree(job_dir, ignore_errors=True)
    except Exception as e:
        print(f"[cleanup] Failed deferred cleanup for project {project_id}: {e}")


@app.get("/", include_in_schema=False)
async def root():
    """Serve the SPA when bundled, otherwise redirect to the API docs."""
    index_path = _frontend_index_path()
    if index_path is not None:
        return FileResponse(index_path)
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
    start: Optional[float] = None
    segments: Optional[List[VideoSegment]] = None


class ProcessVideoURLRequest(BaseModel):
    """New URL-based video processing request."""
    primary_url: str
    sources: List[VideoSource]
    prompt: str
    music_mode: str = "original"  # "original" or "custom"
    custom_music_url: Optional[str] = None
    custom_music_start: Optional[str] = None
    custom_music_end: Optional[str] = None
    custom_music_segment: Optional[str] = None
    custom_music_segments: Optional[List[VideoSegment]] = None
    google_drive_link: Optional[str] = None
    edit_mode: Optional[str] = None
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
                "start": source.start,
                "segments": segments,
            })
        
        requirements_state = dict(request.requirements_state or {})
        if request.edit_mode and not requirements_state.get("edit_mode"):
            requirements_state["edit_mode"] = request.edit_mode

        result = Assemble_Pipeline(
            primary_url=request.primary_url,
            sources=sources_list,
            prompt=request.prompt,
            music_mode=request.music_mode,
            custom_music_url=request.custom_music_url,
            custom_music_start=request.custom_music_start,
            custom_music_end=request.custom_music_end,
            custom_music_segment=request.custom_music_segment,
            custom_music_segments=(
                [{"start": s.start, "end": s.end} for s in (request.custom_music_segments or [])]
                if request.custom_music_segments
                else None
            ),
            requirements_state=requirements_state,
            job_id=request.job_id,
            gdrive_folder_id=folder_id,
        )
        return result
        
    except Exception as e:
        print(f"ERROR in /process-video-url: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


@app.get("/google-drive/oauth/start")
async def google_drive_oauth_start():
    """Start OAuth login flow for Google Drive using server-configured client secret."""
    try:
        from google_auth_oauthlib.flow import Flow

        client_secret_path = resolve_drive_oauth_client_secret_path()
        redirect_uri = os.getenv("DRIVE_OAUTH_REDIRECT_URI", "http://localhost:10000/google-drive/oauth/callback")
        scopes = ["https://www.googleapis.com/auth/drive"]
        flow = Flow.from_client_secrets_file(str(client_secret_path), scopes=scopes)
        flow.redirect_uri = redirect_uri
        auth_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        DRIVE_OAUTH_PENDING[state] = {
            "created_at": time.time(),
            "redirect_uri": redirect_uri,
            "code_verifier": getattr(flow, "code_verifier", None),
        }
        return {
            "success": True,
            "auth_url": auth_url,
        }
    except GoogleCredentialError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Failed to start Google Drive OAuth: {str(e)}"}


@app.get("/google-drive/oauth/callback")
async def google_drive_oauth_callback(code: str, state: str):
    """OAuth callback endpoint used by Google to exchange code for tokens."""
    try:
        from google_auth_oauthlib.flow import Flow

        pending = DRIVE_OAUTH_PENDING.pop(state, None)
        if not pending:
            return HTMLResponse("<h3>Google Drive OAuth failed: invalid/expired state.</h3>", status_code=400)

        client_secret_path = resolve_drive_oauth_client_secret_path()
        token_path = resolve_drive_token_path()
        os.environ["DRIVE_AUTH_MODE"] = "oauth_user"
        os.environ["DRIVE_CLIENT_SECRET_FILE"] = str(client_secret_path)
        os.environ["DRIVE_TOKEN_FILE"] = str(token_path)

        scopes = ["https://www.googleapis.com/auth/drive"]
        flow = Flow.from_client_secrets_file(str(client_secret_path), scopes=scopes, state=state)
        flow.redirect_uri = pending["redirect_uri"]
        if pending.get("code_verifier"):
            flow.code_verifier = pending["code_verifier"]
        flow.fetch_token(code=code)
        token_path.write_text(flow.credentials.to_json(), encoding="utf-8")

        html = """
        <html><body>
          <h3>Google Drive connected successfully.</h3>
          <p>You can close this tab and continue in AI Editor.</p>
          <script>window.close();</script>
        </body></html>
        """
        return HTMLResponse(html)
    except Exception as e:
        return HTMLResponse(f"<h3>Google Drive OAuth failed: {str(e)}</h3>", status_code=400)


@app.get("/google-drive/oauth/status")
async def google_drive_oauth_status():
    """Check whether a Drive OAuth token is connected and usable."""
    try:
        drive = build_drive_service_oauth(scopes=["https://www.googleapis.com/auth/drive"])
        about = drive.about().get(fields="user").execute()
        user_email = (about.get("user") or {}).get("emailAddress", "")
        return {"connected": True, "email": user_email}
    except Exception as e:
        return {"connected": False, "error": str(e)}


@app.get("/jobs/{project_id}/status")
async def job_status(project_id: str, include_trace: bool = False):
    job_dir = TMP_JOBS_DIR / project_id
    state = load_state(str(job_dir))
    if state is None:
        raise HTTPException(status_code=404, detail="Job state not found.")
    payload = {
        "success": state.status == JobStatus.SUCCEEDED,
        "project_id": project_id,
        "requested_user_input": state.requested_user_input,
        "warnings": state.warnings,
        "errors": state.errors,
        "render_summary": state.render_summary,
        "source_status": state.source_status,
        **build_controller_status_payload(state),
    }
    if include_trace:
        payload["decision_trace"] = sanitize_decision_trace_entries(state.decision_trace)
    return payload


@app.get("/health/providers")
async def provider_health():
    health = get_provider_health(
        require_llm=True,
        require_render=True,
        require_drive=True,
    )
    providers = {
        name: {
            "name": payload.get("name", name),
            "required": bool(payload.get("required", False)),
            "configured": bool(payload.get("configured", False)),
            "ready": bool(payload.get("ready", False)),
            "code": payload.get("code", ""),
            "message": payload.get("message", ""),
        }
        for name, payload in (health.get("providers") or {}).items()
    }
    return {"success": bool(health.get("ready", False)), "ready": bool(health.get("ready", False)), "providers": providers}


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
        from ai_editor.youtube_clipper import YouTubeClipper

        clipper = YouTubeClipper()
        result = clipper.process_youtube_clip(
            yt_url=request.youtube_url,
            start_time=request.start_time,
            end_time=request.end_time,
            output_folder_id=request.output_folder_id,
            clip_name=request.clip_name,
        )
        return result
    except ModuleNotFoundError as e:
        return {
            "success": False,
            "error": f"YouTube clipper dependencies are missing: {str(e)}",
        }
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
        from ai_editor.youtube_clipper import YouTubeClipper

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
        from ai_editor.youtube_uploader import YouTubeUploader, YouTubeUploadError

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
    except ModuleNotFoundError as e:
        return {"success": False, "error": f"YouTube upload dependencies are missing: {str(e)}"}
    except YouTubeUploadError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"YouTube upload failed: {str(e)}"}


@app.get("/healthz")
async def healthz():
    """Container health endpoint used by Docker and deployment platforms."""
    return {
        "status": "ok",
        "frontend_bundled": _frontend_index_path() is not None,
    }


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend(full_path: str):
    """Serve bundled frontend assets and fall back to the SPA index for client routes."""
    index_path = _frontend_index_path()
    if index_path is None:
        raise HTTPException(status_code=404, detail="Frontend build not found.")

    asset_path = _resolve_frontend_asset_path(full_path)
    if asset_path is not None:
        return FileResponse(asset_path)

    return FileResponse(index_path)

