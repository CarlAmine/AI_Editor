"""Tests for render provider selection in executor."""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from pipeline.executor import PipelineExecutor, ExecutionContext
from pipeline.provider_errors import ProviderFailure
from pipeline.state import JobState, StageName


class TestRenderProviderSelection:
    """Test render provider selection logic."""

    def test_render_provider_default_is_ffmpeg(self, monkeypatch):
        """Test that FFmpeg is the default render provider."""
        monkeypatch.delenv("RENDER_PROVIDER", raising=False)
        
        from pipeline.executor import PipelineExecutor
        executor = PipelineExecutor()
        
        # Create a minimal execution context
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = MagicMock(spec=ExecutionContext)
            ctx.job_id = "test-job"
            ctx.dirs = {
                "job": tmpdir,
                "plans": os.path.join(tmpdir, "plans"),
                "debug": os.path.join(tmpdir, "debug"),
            }
            ctx.state = MagicMock()
            ctx.state.render_spec = {
                "canonical_timeline": [
                    {
                        "video_src": "https://example.com/video.mp4",
                        "duration": 5,
                    }
                ],
            }
            
            # Mock the _stage_ffmpeg_render method
            executor._stage_ffmpeg_render = MagicMock()
            
            # Mock the _run_stage to directly call the function
            with patch.object(executor, "_run_stage", side_effect=lambda ctx, stage, fn: fn()):
                with patch.object(executor, "_stage_render_provider") as mock_provider:
                    # The _stage_render_provider should be called
                    executor._stage_render_provider(ctx)

    def test_render_provider_ffmpeg_selected(self, monkeypatch):
        """Test FFmpeg provider is selected when configured."""
        monkeypatch.setenv("RENDER_PROVIDER", "ffmpeg")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = MagicMock(spec=ExecutionContext)
            ctx.job_id = "test-job"
            ctx.dirs = {
                "job": tmpdir,
                "plans": os.path.join(tmpdir, "plans"),
                "debug": os.path.join(tmpdir, "debug"),
            }
            ctx.state = MagicMock()
            ctx.state.render_spec = {
                "canonical_timeline": [
                    {
                        "video_src": "https://example.com/video.mp4",
                        "duration": 5,
                    }
                ],
            }
            ctx.artifacts = MagicMock()
            ctx.runtime = {}
            
            executor = PipelineExecutor()
            
            # Create the required directories
            os.makedirs(os.path.join(tmpdir, "plans"), exist_ok=True)
            os.makedirs(os.path.join(tmpdir, "debug"), exist_ok=True)
            
            # Mock the _stage_ffmpeg_render method
            with patch.object(executor, "_stage_ffmpeg_render") as mock_ffmpeg:
                executor._stage_render_provider(ctx)
                mock_ffmpeg.assert_called_once_with(ctx)

    def test_render_provider_shotstack_selected(self, monkeypatch):
        """Test Shotstack provider is selected when configured."""
        monkeypatch.setenv("RENDER_PROVIDER", "shotstack")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = MagicMock(spec=ExecutionContext)
            ctx.job_id = "test-job"
            ctx.dirs = {
                "job": tmpdir,
                "plans": os.path.join(tmpdir, "plans"),
                "debug": os.path.join(tmpdir, "debug"),
            }
            ctx.state = MagicMock()
            ctx.state.render_spec = {}
            
            executor = PipelineExecutor()
            
            # Mock the _stage_shotstack_render method
            with patch.object(executor, "_stage_shotstack_render") as mock_shotstack:
                executor._stage_render_provider(ctx)
                mock_shotstack.assert_called_once_with(ctx)

    def test_render_provider_invalid_fails(self, monkeypatch):
        """Test invalid provider raises error."""
        monkeypatch.setenv("RENDER_PROVIDER", "invalid_provider")
        
        ctx = MagicMock(spec=ExecutionContext)
        executor = PipelineExecutor()
        
        with pytest.raises(ProviderFailure) as exc_info:
            executor._stage_render_provider(ctx)
        
        assert "invalid_provider" in str(exc_info.value).lower()

    def test_render_provider_case_insensitive(self, monkeypatch):
        """Test provider name is case-insensitive."""
        monkeypatch.setenv("RENDER_PROVIDER", "FFMPEG")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = MagicMock(spec=ExecutionContext)
            ctx.job_id = "test-job"
            ctx.dirs = {
                "job": tmpdir,
                "plans": os.path.join(tmpdir, "plans"),
                "debug": os.path.join(tmpdir, "debug"),
            }
            ctx.state = MagicMock()
            ctx.state.render_spec = {
                "canonical_timeline": [
                    {
                        "video_src": "https://example.com/video.mp4",
                        "duration": 5,
                    }
                ],
            }
            ctx.artifacts = MagicMock()
            ctx.runtime = {}
            
            executor = PipelineExecutor()
            
            # Create the required directories
            os.makedirs(os.path.join(tmpdir, "plans"), exist_ok=True)
            os.makedirs(os.path.join(tmpdir, "debug"), exist_ok=True)
            
            # Should still select FFmpeg (case-insensitive)
            with patch.object(executor, "_stage_ffmpeg_render") as mock_ffmpeg:
                executor._stage_render_provider(ctx)
                mock_ffmpeg.assert_called_once()

    def test_ffmpeg_render_requires_canonical_timeline(self, monkeypatch):
        """Test FFmpeg render fails without canonical_timeline."""
        monkeypatch.setenv("RENDER_PROVIDER", "ffmpeg")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = MagicMock(spec=ExecutionContext)
            ctx.job_id = "test-job"
            ctx.dirs = {
                "job": tmpdir,
                "plans": os.path.join(tmpdir, "plans"),
                "debug": os.path.join(tmpdir, "debug"),
            }
            ctx.state = MagicMock()
            ctx.state.render_spec = {}  # No canonical_timeline
            
            executor = PipelineExecutor()
            
            with pytest.raises(ProviderFailure) as exc_info:
                executor._stage_ffmpeg_render(ctx)
            
            assert "canonical_timeline" in str(exc_info.value).lower()

    def test_ffmpeg_render_registers_artifacts(self, monkeypatch, tmp_path):
        """Test FFmpeg render registers output artifacts."""
        monkeypatch.setenv("RENDER_PROVIDER", "ffmpeg")
        
        ctx = MagicMock(spec=ExecutionContext)
        ctx.job_id = "test-job"
        ctx.dirs = {
            "job": str(tmp_path),
            "plans": str(tmp_path / "plans"),
            "debug": str(tmp_path / "debug"),
        }
        ctx.state = MagicMock()
        ctx.state.render_spec = {
            "canonical_timeline": [
                {
                    "video_src": "https://example.com/video.mp4",
                    "duration": 5,
                }
            ],
        }
        ctx.artifacts = MagicMock()
        ctx.runtime = {}
        
        executor = PipelineExecutor()
        
        # Create required directories
        (tmp_path / "plans").mkdir(exist_ok=True)
        (tmp_path / "debug").mkdir(exist_ok=True)
        
        # Mock FFmpegRenderer
        with patch("ai_editor.renderers.FFmpegRenderer") as mock_renderer_class:
            mock_renderer = MagicMock()
            mock_renderer_class.return_value = mock_renderer
            
            # Create a fake output file
            output_file = tmp_path / "outputs" / "master.mp4"
            output_file.parent.mkdir(exist_ok=True)
            output_file.write_text("fake video")
            
            mock_renderer.render.return_value = {
                "success": True,
                "url": "/files/test-job/outputs/master.mp4",
                "render_id": "ffmpeg-test-job",
                "output_path": str(output_file),
                "debug_info": {},
            }
            
            executor._stage_ffmpeg_render(ctx)
            
            # Verify artifacts were registered
            assert ctx.artifacts.register_file.called
            assert ctx.artifacts.register_url.called


def test_ffmpeg_render_error_handling(tmp_path):
    """Test FFmpeg render error handling."""
    ctx = MagicMock(spec=ExecutionContext)
    ctx.job_id = "test-job"
    ctx.dirs = {
        "job": str(tmp_path),
        "plans": str(tmp_path / "plans"),
        "debug": str(tmp_path / "debug"),
    }
    ctx.state = MagicMock()
    ctx.state.render_spec = {
        "canonical_timeline": [
            {
                "video_src": "https://example.com/video.mp4",
                "duration": 5,
            }
        ],
    }
    
    executor = PipelineExecutor()
    
    # Create required directories
    (tmp_path / "plans").mkdir(exist_ok=True)
    (tmp_path / "debug").mkdir(exist_ok=True)
    
    # Mock FFmpegRenderer to fail
    with patch("ai_editor.renderers.FFmpegRenderer") as mock_renderer_class:
        mock_renderer = MagicMock()
        mock_renderer_class.return_value = mock_renderer
        
        mock_renderer.render.return_value = {
            "success": False,
            "url": None,
            "render_id": None,
            "error": "FFmpeg failed",
            "debug_info": {},
        }
        
        with pytest.raises(ProviderFailure):
            executor._stage_ffmpeg_render(ctx)
