import os
import io
from typing import List

from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from ai_editor.google_auth import build_drive_service

from .base import AssetRef, StorageAdapter


class DriveStorageAdapter(StorageAdapter):
    backend_name = "drive"

    def __init__(self):
        self.drive = build_drive_service(scopes=["https://www.googleapis.com/auth/drive"])

    @staticmethod
    def _direct_url(file_id: str) -> str:
        return f"https://drive.google.com/uc?export=download&id={file_id}"

    def _ensure_public(self, file_id: str) -> None:
        try:
            self.drive.permissions().create(
                fileId=file_id,
                body={"type": "anyone", "role": "reader"},
                fields="id",
            ).execute()
        except Exception:
            pass

    def list_videos(self, ref) -> List[AssetRef]:
        folder_id = str(ref)
        q = f"'{folder_id}' in parents and (mimeType contains 'video' or mimeType contains 'video/')"
        resp = self.drive.files().list(q=q, fields="files(id,name,mimeType,webViewLink,webContentLink)").execute()
        files = resp.get("files", [])
        return [
            AssetRef(id=f["id"], name=f.get("name") or f"drive_{i+1}.mp4", backend=self.backend_name, raw=f)
            for i, f in enumerate(files)
        ]

    def download(self, asset_ref: AssetRef, dst_path: str) -> str:
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        request = self.drive.files().get_media(fileId=asset_ref.id)
        with io.FileIO(dst_path, "wb") as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        self._ensure_public(asset_ref.id)
        return dst_path

    def upload(self, local_path: str, dst_ref=None) -> AssetRef:
        folder_id = str(dst_ref) if dst_ref else None
        body = {"name": os.path.basename(local_path)}
        if folder_id:
            body["parents"] = [folder_id]
        media = MediaFileUpload(local_path, mimetype="video/mp4", resumable=False)
        res = self.drive.files().create(
            body=body,
            media_body=media,
            fields="id,name,mimeType,webViewLink,webContentLink",
        ).execute(num_retries=3)
        self._ensure_public(res["id"])
        return AssetRef(id=res["id"], name=res.get("name") or os.path.basename(local_path), backend=self.backend_name, raw=res)

    def get_fetchable_url(self, asset_ref: AssetRef) -> str:
        return self._direct_url(asset_ref.id)
