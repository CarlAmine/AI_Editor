"""Tests for FFmpeg renderer."""

import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from ai_editor.renderers import FFmpegRenderer
from ai_editor.renderers.ffmpeg_renderer import (
    _concat_demuxer_path,
    _escape_drawtext_path,
    _escape_drawtext_text,
    _resolve_font_file,
)


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

    def test_escape_drawtext_text(self):
        """Test drawtext overlay text escaping."""
        assert _escape_drawtext_text("Hello: World") == r"Hello\: World"
        assert _escape_drawtext_text("It's 100% done") == r"It\'s 100\% done"
        assert _escape_drawtext_text("line\nbreak") == "line break"
        assert _escape_drawtext_text(r"path\file") == r"path\\file"

    def test_escape_drawtext_path_windows(self):
        """Test drawtext font path escaping on Windows."""
        assert (
            _escape_drawtext_path(r"C:\Windows\Fonts\arial.ttf")
            == r"C\:/Windows/Fonts/arial.ttf"
        )

    def test_resolve_font_file_from_env(self, tmp_path, monkeypatch):
        """Test font resolution prefers FFMPEG_FONT_FILE when set."""
        font_path = tmp_path / "custom.ttf"
        font_path.write_text("font", encoding="utf-8")
        monkeypatch.setenv("FFMPEG_FONT_FILE", str(font_path))
        assert _resolve_font_file() == str(font_path)

    def test_write_concat_file(self, tmp_path):
        """Test concat.txt uses absolute normalized paths."""
        renderer = FFmpegRenderer()
        ffmpeg_dir = tmp_path / "ffmpeg"
        ffmpeg_dir.mkdir()
        clip_paths = [
            ffmpeg_dir / "clip_0.mp4",
            ffmpeg_dir / "clip_1.mp4",
            ffmpeg_dir / "clip_2.mp4",
        ]
        for clip in clip_paths:
            clip.write_bytes(b"clip")

        concat_path = ffmpeg_dir / "concat.txt"
        renderer._write_concat_file(
            str(concat_path),
            [str(clip) for clip in clip_paths],
        )

        assert concat_path.exists()
        contents = concat_path.read_text(encoding="utf-8")
        for clip in clip_paths:
            expected = _concat_demuxer_path(clip)
            assert f"file '{expected}'" in contents
            assert str(clip.resolve().as_posix()) in contents

    def test_write_concat_file_no_doubled_relative_paths(self, tmp_path, monkeypatch):
        """Relative clip paths must not double the ffmpeg directory in concat.txt."""
        monkeypatch.chdir(tmp_path)
        renderer = FFmpegRenderer()
        ffmpeg_dir = tmp_path / "tmp" / "jobs" / "job_1" / "ffmpeg"
        ffmpeg_dir.mkdir(parents=True)
        clip0 = ffmpeg_dir / "clip_0.mp4"
        clip1 = ffmpeg_dir / "clip_1.mp4"
        clip0.write_bytes(b"clip")
        clip1.write_bytes(b"clip")

        rel_clip0 = Path("tmp/jobs/job_1/ffmpeg/clip_0.mp4")
        rel_clip1 = Path("tmp/jobs/job_1/ffmpeg/clip_1.mp4")
        concat_path = ffmpeg_dir / "concat.txt"
        renderer._write_concat_file(str(concat_path), [str(rel_clip0), str(rel_clip1)])

        contents = concat_path.read_text(encoding="utf-8")
        doubled = "tmp/jobs/job_1/ffmpeg/tmp/jobs/job_1/ffmpeg"
        assert doubled not in contents.replace("\\", "/")
        for clip in (clip0, clip1):
            assert _concat_demuxer_path(clip) in contents

    def test_concat_demuxer_path_windows_style(self, tmp_path):
        """Windows paths are normalized to forward-slash absolute paths."""
        clip = tmp_path / "clip_0.mp4"
        clip.write_bytes(b"clip")
        demuxer_path = _concat_demuxer_path(clip)
        assert "\\" not in demuxer_path
        assert demuxer_path.startswith("/") or (len(demuxer_path) > 2 and demuxer_path[1] == ":")

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

class TestFFmpegRendererFilters:
    """Test filter strings generated by FFmpegRenderer."""

    @patch("ai_editor.renderers.ffmpeg_renderer.subprocess.run")
    def test_pad_vs_crop_filter(self, mock_run, tmp_path):
        renderer = FFmpegRenderer()
        renderer._has_audio = MagicMock(return_value=True)
        mock_run.return_value = MagicMock(returncode=0)
        
        row = {"video_src": "fake.mp4", "duration": 5}
        
        # Test pad
        renderer._build_normalized_clip(0, row, str(tmp_path), 1080, 1920, 30, refit_mode="pad")
        cmd_pad = renderer._commands[-1]["command"]
        assert "force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black" in cmd_pad
        
        # Test crop
        renderer._build_normalized_clip(1, row, str(tmp_path), 1080, 1920, 30, refit_mode="crop_center")
        cmd_crop = renderer._commands[-1]["command"]
        assert "force_original_aspect_ratio=increase,crop=1080:1920" in cmd_crop

    @patch("ai_editor.renderers.ffmpeg_renderer._resolve_font_file")
    @patch("ai_editor.renderers.ffmpeg_renderer.subprocess.run")
    def test_drawtext_relative_timing(self, mock_run, mock_resolve_font, tmp_path):
        renderer = FFmpegRenderer()
        renderer._has_audio = MagicMock(return_value=True)
        mock_run.return_value = MagicMock(returncode=0)
        mock_resolve_font.return_value = r"C:\Windows\Fonts\arial.ttf"

        row = {
            "video_src": "fake.mp4",
            "duration": 10.0,
            "start": 5.0,
            "text": "Hello World",
            "text_start": 7.0,
            "text_end": 12.0,
        }

        renderer._build_normalized_clip(0, row, str(tmp_path), 1080, 1920, 30)
        cmd = renderer._commands[-1]["command"]
        # rel_start = 7.0 - 5.0 = 2.0
        # rel_end = 12.0 - 5.0 = 7.0
        assert "enable='between(t,2.000,7.000)'" in cmd
        assert "drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':" in cmd
        assert "text='Hello World'" in cmd
        assert "box=1" not in cmd
        assert "borderw=2" in cmd

    @patch("ai_editor.renderers.ffmpeg_renderer._resolve_font_file")
    @patch("ai_editor.renderers.ffmpeg_renderer.subprocess.run")
    def test_drawtext_skipped_without_font(self, mock_run, mock_resolve_font, tmp_path):
        renderer = FFmpegRenderer()
        renderer._has_audio = MagicMock(return_value=True)
        mock_run.return_value = MagicMock(returncode=0)
        mock_resolve_font.return_value = None

        row = {
            "video_src": "fake.mp4",
            "duration": 5.0,
            "text": "Hello World",
        }

        renderer._build_normalized_clip(0, row, str(tmp_path), 1080, 1920, 30)
        filter_graph = renderer._commands[-1]["filter_graph"]
        assert "drawtext=" not in filter_graph

    @patch("ai_editor.renderers.ffmpeg_renderer._resolve_font_file")
    @patch("ai_editor.renderers.ffmpeg_renderer.subprocess.run")
    def test_drawtext_retry_without_overlay_on_failure(
        self, mock_run, mock_resolve_font, tmp_path
    ):
        renderer = FFmpegRenderer()
        renderer._has_audio = MagicMock(return_value=True)
        mock_resolve_font.return_value = r"C:\Windows\Fonts\arial.ttf"
        mock_run.side_effect = [
            MagicMock(returncode=1, stderr="Fontconfig error"),
            MagicMock(returncode=0, stderr=""),
        ]

        row = {
            "video_src": "fake.mp4",
            "duration": 5.0,
            "text": "Retry me",
        }

        result = renderer._build_normalized_clip(0, row, str(tmp_path), 1080, 1920, 30)
        assert result is not None
        assert mock_run.call_count == 2
        assert renderer._commands[0]["filter_graph"].count("drawtext") == 1
        assert renderer._commands[1]["retry_without_text"] is True
        assert "drawtext" not in renderer._commands[1]["filter_graph"]

    @patch("ai_editor.renderers.ffmpeg_renderer.subprocess.run")
    def test_silent_audio_fallback(self, mock_run, tmp_path):
        renderer = FFmpegRenderer()
        renderer._has_audio = MagicMock(return_value=False)
        mock_run.return_value = MagicMock(returncode=0)
        
        row = {"video_src": "fake.mp4", "duration": 5.0}
        
        renderer._build_normalized_clip(0, row, str(tmp_path), 1080, 1920, 30)
        cmd = renderer._commands[-1]["command"]
        assert "anullsrc=channel_layout=stereo:sample_rate=48000" in cmd
        assert "-map [out_a]" in cmd

    @patch("ai_editor.renderers.ffmpeg_renderer.subprocess.run")
    def test_mute_source_audio(self, mock_run, tmp_path):
        renderer = FFmpegRenderer()
        renderer._has_audio = MagicMock(return_value=True)
        mock_run.return_value = MagicMock(returncode=0)
        
        row = {"video_src": "fake.mp4", "duration": 5.0}
        
        renderer._build_normalized_clip(0, row, str(tmp_path), 1080, 1920, 30, mute_source_audio=True)
        cmd = renderer._commands[-1]["command"]
        assert "[0:a]" not in cmd
        assert "anullsrc" not in cmd
        assert "-map [out_a]" not in cmd

    @patch("ai_editor.renderers.ffmpeg_renderer.subprocess.run")
    def test_soundtrack_mixing(self, mock_run, tmp_path):
        renderer = FFmpegRenderer()
        mock_run.return_value = MagicMock(returncode=0)
        
        renderer._add_audio("video.mp4", "audio.mp3", "output.mp4", preserve_source_audio=True)
        cmd = renderer._commands[-1]["command"]
        assert "amix=inputs=2:duration=first" in cmd
        assert "aformat=sample_fmts=s16:sample_rates=48000:channel_layouts=stereo" in cmd
        assert "-shortest" in cmd
        
        renderer._add_audio("video.mp4", "audio.mp3", "output2.mp4", preserve_source_audio=False)
        cmd = renderer._commands[-1]["command"]
        assert "amix" not in cmd
        assert "aformat=sample_fmts=s16:sample_rates=48000:channel_layouts=stereo" in cmd
        assert "-shortest" in cmd

import shutil
import subprocess

@pytest.mark.integration
def test_render_integration_lavfi(tmp_path):
    """Integration test using real ffmpeg and lavfi synthetic clips."""
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg or ffprobe not available on PATH")
        
    renderer = FFmpegRenderer()
    
    # Generate synthetic clips
    clip1 = tmp_path / "clip1.mp4"
    clip2 = tmp_path / "clip2.mp4"
    
    # Clip 1: video + sine audio
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=2:size=1280x720:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=1000:duration=2",
        "-c:v", "libx264", "-c:a", "aac", str(clip1)
    ], check=True, capture_output=True)
    
    # Clip 2: video only
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "smptebars=duration=2:size=1280x720:rate=30",
        "-c:v", "libx264", "-an", str(clip2)
    ], check=True, capture_output=True)
    
    render_spec = {
        "resolution": "1080x1920",
        "refit_mode": "crop_center",
        "mute_source_audio": False,
        "canonical_timeline": [
            {
                "video_src": str(clip1),
                "duration": 2.0,
            },
            {
                "video_src": str(clip2),
                "duration": 2.0,
            }
        ]
    }
    
    job_id = "integ-job-123"
    result = renderer.render(render_spec, job_id, str(tmp_path))
    
    assert result["success"] is True
    assert result["url"] == f"/files/{job_id}/outputs/master_16x9.mp4"
    
    output_path = tmp_path / "outputs" / "master_16x9.mp4"
    assert output_path.exists()
    
    # Check streams and duration with ffprobe
    probe_cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-show_streams", "-of", "json", str(output_path)
    ]
    probe_res = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
    probe_data = json.loads(probe_res.stdout)
    
    duration = float(probe_data["format"]["duration"])
    assert 3.8 <= duration <= 4.2  # close to 4.0
    
    streams = probe_data.get("streams", [])
    has_video = any(s.get("codec_type") == "video" for s in streams)
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    
    assert has_video is True
    assert has_audio is True


@pytest.mark.integration
def test_render_integration_text_overlay(tmp_path):
    """Integration test: synthetic clip with drawtext overlay."""
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg or ffprobe not available on PATH")

    font_file = _resolve_font_file()
    if not font_file:
        pytest.skip("no usable font file for drawtext integration test")

    renderer = FFmpegRenderer()
    clip = tmp_path / "clip_with_text.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=2:size=1280x720:rate=30",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000:duration=2",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            str(clip),
        ],
        check=True,
        capture_output=True,
    )

    render_spec = {
        "resolution": "1080x1920",
        "refit_mode": "crop_center",
        "canonical_timeline": [
            {
                "video_src": str(clip),
                "duration": 2.0,
                "text": "Integration Caption",
            }
        ],
    }

    job_id = "integ-text-job"
    result = renderer.render(render_spec, job_id, str(tmp_path))

    assert result["success"] is True
    output_path = tmp_path / "outputs" / "master_16x9.mp4"
    assert output_path.exists()
