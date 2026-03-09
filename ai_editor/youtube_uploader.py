import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

load_dotenv()

YOUTUBE_UPLOAD_SCOPE = ["https://www.googleapis.com/auth/youtube.upload"]


class YouTubeUploadError(Exception):
    """Raised when YouTube upload flow fails."""


class YouTubeUploader:
    """Handles YouTube OAuth and video uploads from remote render URLs."""

    def __init__(self):
        root_dir = Path(__file__).resolve().parent.parent
        self.root_dir = root_dir
        self.jobs_dir = (root_dir / "tmp" / "jobs").resolve()
        self.client_secret_file = Path(
            os.getenv("YOUTUBE_CLIENT_SECRET_FILE", str(root_dir / "youtube-client-secret.json"))
        )
        self.token_file = Path(
            os.getenv("YOUTUBE_TOKEN_FILE", str(root_dir / "youtube-token.json"))
        )
        self.oauth_console_mode = os.getenv("YOUTUBE_OAUTH_USE_CONSOLE", "false").lower() == "true"
        self.download_connect_timeout = int(os.getenv("YOUTUBE_RENDER_DOWNLOAD_CONNECT_TIMEOUT", "20"))
        self.download_read_timeout = int(os.getenv("YOUTUBE_RENDER_DOWNLOAD_READ_TIMEOUT", "600"))
        self.download_retries = max(1, int(os.getenv("YOUTUBE_RENDER_DOWNLOAD_RETRIES", "3")))
        self.youtube = self._build_youtube_client()

    def _build_youtube_client(self):
        if not self.client_secret_file.exists():
            raise YouTubeUploadError(
                f"YouTube OAuth client secret file not found: {self.client_secret_file}. "
                "Create OAuth Client ID (Desktop app) in Google Cloud Console and set YOUTUBE_CLIENT_SECRET_FILE."
            )

        creds = None
        if self.token_file.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_file), YOUTUBE_UPLOAD_SCOPE)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.client_secret_file),
                    YOUTUBE_UPLOAD_SCOPE,
                )
                if self.oauth_console_mode:
                    creds = flow.run_console()
                else:
                    creds = flow.run_local_server(port=0)
            self.token_file.write_text(creds.to_json(), encoding="utf-8")

        return build("youtube", "v3", credentials=creds)

    def _resolve_local_render_path(self, render_url: str) -> Optional[Path]:
        if not render_url:
            return None
        # Accept direct local filesystem paths.
        direct = Path(render_url)
        if direct.exists() and direct.is_file():
            return direct.resolve()

        parsed = urlparse(render_url)
        is_local_host = parsed.hostname in {None, "", "localhost", "127.0.0.1", "::1"}
        path_part = parsed.path or ""
        if not path_part and render_url.startswith("/"):
            path_part = render_url
        if not path_part.startswith("/files/"):
            return None
        if parsed.scheme and parsed.scheme not in {"http", "https"}:
            return None
        if parsed.scheme in {"http", "https"} and not is_local_host:
            return None

        rel = path_part[len("/files/") :].lstrip("/")
        candidate = (self.jobs_dir / rel).resolve()
        try:
            candidate.relative_to(self.jobs_dir)
        except ValueError:
            return None
        if candidate.exists() and candidate.is_file():
            return candidate
        return None

    def _download_video(self, render_url: str, output_path: Path) -> None:
        local_source = self._resolve_local_render_path(render_url)
        if local_source is not None:
            try:
                with local_source.open("rb") as src, output_path.open("wb") as dst:
                    shutil.copyfileobj(src, dst, length=1024 * 1024)
                if not output_path.exists() or output_path.stat().st_size == 0:
                    raise YouTubeUploadError("Downloaded rendered video is empty.")
                return
            except Exception as e:
                raise YouTubeUploadError(
                    f"Failed to read local rendered video file for upload: {local_source} ({e})"
                ) from e

        last_error = None
        for attempt in range(1, self.download_retries + 1):
            try:
                with requests.get(
                    render_url,
                    stream=True,
                    timeout=(self.download_connect_timeout, self.download_read_timeout),
                ) as response:
                    response.raise_for_status()
                    with output_path.open("wb") as f:
                        for chunk in response.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                f.write(chunk)
                if not output_path.exists() or output_path.stat().st_size == 0:
                    raise YouTubeUploadError("Downloaded rendered video is empty.")
                return
            except Exception as e:
                last_error = e
                try:
                    if output_path.exists():
                        output_path.unlink()
                except Exception:
                    pass
                if attempt < self.download_retries:
                    time.sleep(min(8, 2 ** (attempt - 1)))

        raise YouTubeUploadError(
            f"Failed to download rendered video from URL after {self.download_retries} attempt(s): {last_error}"
        ) from last_error

    def upload_from_render_url(
        self,
        render_url: str,
        title: str,
        description: str = "",
        privacy_status: str = "private",
        tags: Optional[List[str]] = None,
        category_id: str = "22",
        made_for_kids: bool = False,
    ) -> Dict:
        if not render_url:
            raise YouTubeUploadError("Missing render_url.")
        if privacy_status not in {"private", "public", "unlisted"}:
            raise YouTubeUploadError("privacy_status must be one of: private, public, unlisted.")

        tmp = tempfile.mkdtemp(prefix="youtube_upload_")
        try:
            local_video = Path(tmp) / "rendered_video.mp4"
            self._download_video(render_url, local_video)

            body = {
                "snippet": {
                    "title": (title or "AI Editor Render").strip()[:100],
                    "description": description or "",
                    "tags": tags or [],
                    "categoryId": category_id,
                },
                "status": {
                    "privacyStatus": privacy_status,
                    "selfDeclaredMadeForKids": made_for_kids,
                },
            }

            media = MediaFileUpload(str(local_video), chunksize=-1, resumable=True, mimetype="video/mp4")
            request = self.youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media,
            )
            response = request.execute()

            video_id = response.get("id")
            if not video_id:
                raise YouTubeUploadError("YouTube upload did not return a video ID.")

            return {
                "success": True,
                "video_id": video_id,
                "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
                "privacy_status": privacy_status,
                "title": body["snippet"]["title"],
            }
        finally:
            # Windows can keep the upload file handle locked briefly after request.execute().
            # Cleanup should be best-effort and must not fail the upload result.
            for i in range(5):
                try:
                    shutil.rmtree(tmp)
                    break
                except PermissionError:
                    if i == 4:
                        break
                    time.sleep(0.5)
                except Exception:
                    break
