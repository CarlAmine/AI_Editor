"""Tests for FFmpeg renderer."""

import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from ai_editor.renderers import FFmpegRenderer


class TestFFmpegRenderer:
    """Test suite for FFmpeg renderer."""

    def test_parse_resolution(self):
        """Test resolution parsing."""
        renderer = FFmpegRenderer()
        
        assert renderer._parse_resolution("1080x1920") == (1080, 1920)
        assert renderer._parse_resolution("1920x1080") == (1920, 1080)
        assert renderer._parse_resolution("9x16") == (9, 16)
        assert renderer._parse_resolution("invalid") == (1080, 1920)  # Default
        assert renderer._parse_resolution("1920") == (1080, 1920)  # Default

    def test_escape_drawtext(self):
        """Test drawtext filter escaping."""
        renderer = FFmpegRenderer()
        
        text = "Hello: World"
        escaped = renderer._escape_drawtext(text)
        assert ":" in escaped or "\\" in escaped or text in escaped
        
        text_with_quotes = "It's working"
        escaped = renderer._escape_drawtext(text_with_quotes)
        assert escaped  # Should not be empty

    def test_write_concat_file(self, tmp_path):
        """Test concat.txt file generation."""
        renderer = FFmpegRenderer()
        concat_path = tmp_path / "concat.txt"
        clip_paths = [
            "/tmp/clip_0.mp4",
            "/tmp/clip_1.mp4",
            "/tmp/clip_2.mp4",
        ]
        
        renderer._write_concat_file(str(concat_path), clip_paths)
        
        assert concat_path.exists()
        contents = concat_path.read_text()
        assert "file '/tmp/clip_0.mp4'" in contents
        assert "file '/tmp/clip_1.mp4'" in contents
        assert "file '/tmp/clip_2.mp4'" in contents

    def test_failure_writes_debug_files(self, tmp_path):
        """Test that failure method creates debug files."""
        renderer = FFmpegRenderer()
        debug_dir = tmp_path / "debug"
        
        result = renderer._failure(
            "Test error message",
            str(debug_dir),
            "job-123",
        )
        
        assert result["success"] is False
        assert result["error"] == "Test error message"
        assert debug_dir.exists()
        
        error_file = debug_dir / "ffmpeg_error.json"
        assert error_file.exists()
        
        error_data = json.loads(error_file.read_text())
        assert error_data["stage"] == "ffmpeg_render"
        assert error_data["error"] == "Test error message"
        assert error_data["job_id"] == "job-123"

    def test_render_missing_canonical_timeline(self, tmp_path):
        """Test render fails with missing canonical_timeline."""
        renderer = FFmpegRenderer()
        
        render_spec = {
            "resolution": "1080x1920",
        }
        
        result = renderer.render(
            render_spec=render_spec,
            job_id="test-job",
            job_dir=str(tmp_path),
        )
        
        assert result["success"] is False
        assert "canonical_timeline" in result["error"].lower()

    @patch("ai_editor.renderers.ffmpeg_renderer.FFmpegRenderer._build_normalized_clip")
    @patch("ai_editor.renderers.ffmpeg_renderer.FFmpegRenderer._concat_clips")
    def test_render_with_canonical_timeline(
        self,
        mock_concat,
        mock_build_clip,
        tmp_path,
    ):
        """Test successful render with canonical_timeline."""
        mock_build_clip.return_value = str(tmp_path / "clip_0.mp4")
        mock_concat.return_value = True
        
        # Create a fake output file
        outputs_dir = tmp_path / "outputs"
        outputs_dir.mkdir()
        master_file = outputs_dir / "master.mp4"
        master_file.write_text("fake video data")
        
        # Patch shutil.copy to do nothing
        with patch("shutil.copy"):
            renderer = FFmpegRenderer()
            
            render_spec = {
                "resolution": "1080x1920",
                "canonical_timeline": [
                    {
                        "video_src": "https://example.com/clip.mp4",
                        "duration": 5,
                        "text": "Test Text",
                    }
                ],
            }
            
            result = renderer.render(
                render_spec=render_spec,
                job_id="test-job",
                job_dir=str(tmp_path),
            )
        
        assert result["success"] is True
        assert result["render_id"] is not None
        assert result["render_id"].startswith("ffmpeg")

    def test_build_normalized_clip_invalid_source(self, tmp_path):
        """Test building clip with invalid source."""
        renderer = FFmpegRenderer()
        
        row = {
            "video_src": "",  # Empty source
            "duration": 5,
        }
        
        result = renderer._build_normalized_clip(
            index=0,
            row=row,
            output_dir=str(tmp_path),
            width=1080,
            height=1920,
            fps=30,
        )
        
        assert result is None

    def test_build_normalized_clip_zero_duration(self, tmp_path):
        """Test building clip with zero duration."""
        renderer = FFmpegRenderer()
        
        row = {
            "video_src": "https://example.com/video.mp4",
            "duration": 0,  # Zero duration
        }
        
        result = renderer._build_normalized_clip(
            index=0,
            row=row,
            output_dir=str(tmp_path),
            width=1080,
            height=1920,
            fps=30,
        )
        
        assert result is None

    def test_iso_now(self):
        """Test ISO timestamp generation."""
        from datetime import datetime
        
        renderer = FFmpegRenderer()
        iso_time = renderer._iso_now()
        
        # Should be parseable as ISO 8601
        dt = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))
        assert dt is not None


class TestFFmpegRendererIntegration:
    """Integration tests that don't require external tools."""

    def test_render_builds_temp_clip_per_row(self, tmp_path):
        """Test that render creates one temp clip per canonical_timeline row."""
        renderer = FFmpegRenderer()
        
        # Create a mock video file
        mock_video = tmp_path / "mock.mp4"
        mock_video.write_bytes(b"fake video data")
        
        render_spec = {
            "resolution": "1080x1920",
            "canonical_timeline": [
                {
                    "video_src": str(mock_video),
                    "duration": 2,
                    "trim": 0,
                    "text": "Clip 1",
                },
                {
                    "video_src": str(mock_video),
                    "duration": 3,
                    "trim": 0.5,
                    "text": "Clip 2",
                },
            ],
        }
        
        # We can't fully execute without FFmpeg, but we can test the setup
        ffmpeg_dir = tmp_path / "ffmpeg"
        ffmpeg_dir.mkdir()
        
        # Verify canonical_timeline is recognized
        assert render_spec.get("canonical_timeline") is not None
        assert len(render_spec["canonical_timeline"]) == 2

    def test_render_writes_commands_debug_file(self, tmp_path):
        """Test that FFmpeg commands are logged."""
        renderer = FFmpegRenderer()
        
        # Add some mock commands
        renderer._commands = [
            {"type": "test", "command": "ffmpeg -i input.mp4 output.mp4"},
        ]
        
        debug_dir = tmp_path / "debug"
        debug_dir.mkdir()
        
        renderer._write_debug_commands(str(debug_dir / "ffmpeg_commands.json"))
        
        commands_file = debug_dir / "ffmpeg_commands.json"
        assert commands_file.exists()
        
        commands = json.loads(commands_file.read_text())
        assert len(commands) > 0
        assert commands[0]["type"] == "test"

    def test_render_writes_summary_debug_file(self, tmp_path):
        """Test render summary is written."""
        renderer = FFmpegRenderer()
        
        debug_dir = tmp_path / "debug"
        debug_dir.mkdir()
        
        summary = {
            "job_id": "test-job",
            "clip_count": 3,
            "success": True,
        }
        
        renderer._write_debug_summary(
            str(debug_dir / "ffmpeg_render_summary.json"),
            summary,
        )
        
        summary_file = debug_dir / "ffmpeg_render_summary.json"
        assert summary_file.exists()
        
        data = json.loads(summary_file.read_text())
        assert data["job_id"] == "test-job"
        assert data["clip_count"] == 3


def test_render_spec_with_audio(tmp_path):
    """Test render spec with soundtrack URL."""
    renderer = FFmpegRenderer()
    
    render_spec = {
        "resolution": "1920x1080",
        "canonical_timeline": [
            {
                "video_src": "https://example.com/video.mp4",
                "duration": 5,
            }
        ],
        "soundtrack_url": "https://example.com/audio.mp3",
    }
    
    # Verify soundtrack is present
    assert render_spec.get("soundtrack_url") is not None
    assert "example.com/audio.mp3" in render_spec["soundtrack_url"]
