from dataclasses import dataclass
from typing import List, Optional


@dataclass
class AssetRef:
    id: str
    name: str
    backend: str
    raw: Optional[dict] = None


@dataclass
class SourceInput:
    id: str
    backend: str
    asset_ref_or_url: str
    segment: Optional[dict] = None


class StorageAdapter:
    backend_name: str = "base"

    def list_videos(self, ref) -> List[AssetRef]:
        raise NotImplementedError

    def download(self, asset_ref: AssetRef, dst_path: str) -> str:
        raise NotImplementedError

    def upload(self, local_path: str, dst_ref=None) -> AssetRef:
        raise NotImplementedError

    def get_fetchable_url(self, asset_ref: AssetRef) -> str:
        raise NotImplementedError
