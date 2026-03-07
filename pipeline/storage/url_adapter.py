import os
from typing import List

from ai_editor.downloader import download_video

from .base import AssetRef, StorageAdapter


class UrlStorageAdapter(StorageAdapter):
    backend_name = "url"

    def list_videos(self, ref) -> List[AssetRef]:
        if isinstance(ref, list):
            return [
                AssetRef(id=f"url-{i+1}", name=f"url_source_{i+1}", backend=self.backend_name, raw={"url": u})
                for i, u in enumerate(ref)
            ]
        return [AssetRef(id="url-1", name="url_source_1", backend=self.backend_name, raw={"url": str(ref)})]

    def download(self, asset_ref: AssetRef, dst_path: str) -> str:
        url = (asset_ref.raw or {}).get("url")
        out_dir = os.path.dirname(dst_path)
        out_name = os.path.basename(dst_path)
        return download_video(url, out_dir, out_name)

    def upload(self, local_path: str, dst_ref=None) -> AssetRef:
        # URL backend has no upload concept; expose local path as asset ref
        return AssetRef(id=local_path, name=os.path.basename(local_path), backend=self.backend_name, raw={"path": local_path})

    def get_fetchable_url(self, asset_ref: AssetRef) -> str:
        raw = asset_ref.raw or {}
        return raw.get("url") or raw.get("path") or asset_ref.id
