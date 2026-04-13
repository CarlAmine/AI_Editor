from __future__ import annotations

from typing import Optional

from .analysis_schema import AnalysisStatus, TranscriptResult


class TranscriptAnalyzer:
    """
    Incremental abstraction for transcript backends.

    Today this layer intentionally degrades gracefully. When no backend such as
    Whisper or faster-whisper is installed, the analyzer returns an empty
    transcript payload instead of failing the pipeline.
    """

    def __init__(self, preferred_backend: Optional[str] = None) -> None:
        self.preferred_backend = preferred_backend or "auto"

    def analyze(self, video_path: str) -> TranscriptResult:
        try:
            import faster_whisper  # type: ignore  # pragma: no cover

            _ = faster_whisper
            return TranscriptResult(
                status=AnalysisStatus.EMPTY.value,
                backend="faster-whisper",
                reason="Transcript backend detected but transcription is not wired in yet.",
                spans=[],
            )
        except Exception:
            pass

        try:
            import whisper  # type: ignore  # pragma: no cover

            _ = whisper
            return TranscriptResult(
                status=AnalysisStatus.EMPTY.value,
                backend="whisper",
                reason="Transcript backend detected but transcription is not wired in yet.",
                spans=[],
            )
        except Exception:
            pass

        return TranscriptResult(
            status=AnalysisStatus.UNAVAILABLE.value,
            backend=None,
            reason="No transcript backend installed. Install whisper or faster-whisper to enable transcripts.",
            spans=[],
        )
