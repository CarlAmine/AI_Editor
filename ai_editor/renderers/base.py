"""Base class for video renderers."""

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseRenderer(ABC):
    """Abstract base class for video renderers."""

    @abstractmethod
    def render(
        self,
        render_spec: Dict[str, Any],
        job_id: str,
        job_dir: str,
    ) -> Dict[str, Any]:
        """
        Render a video from render_spec.

        Args:
            render_spec: Normalized render specification with canonical_timeline.
            job_id: Unique job identifier.
            job_dir: Job working directory.

        Returns:
            Dict with keys:
                - success: bool
                - url: str (local path or HTTP URL to rendered video)
                - render_id: str (provider-specific ID, may be None)
                - error: str (if not successful)
                - debug_info: dict (debug files and metadata)
        """
        pass

    @property
    def supported_operations(self) -> set:
        """Return set of supported operations in timeline rendering."""
        return {
            "trim_clip",
            "crop_center",
            "pad",
            "overlay_text",
            "concat",
            "reference_audio",
            "mute_source_audio",
            "fade_in",
            "fade_out",
        }
