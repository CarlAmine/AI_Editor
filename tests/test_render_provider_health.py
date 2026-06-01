"""Tests for render provider health status checks."""

import os
import shutil
from unittest.mock import patch

from pipeline.providers import _build_render_status


def test_render_provider_ffmpeg_success():
    """Test RENDER_PROVIDER=ffmpeg is ready if ffmpeg and ffprobe resolve."""
    env_mock = {
        "RENDER_PROVIDER": "ffmpeg",
        "FFMPEG_BINARY": "ffmpeg",
        "FFPROBE_BINARY": "ffprobe",
    }
    with patch.dict(os.environ, env_mock, clear=True), \
         patch("shutil.which", return_value="/usr/bin/mock-binary"):
        status = _build_render_status(required=True)
        assert status.configured is True
        assert status.ready is True
        assert "Local FFmpeg and FFprobe are configured and ready." in status.message


def test_render_provider_ffmpeg_missing_binaries():
    """Test RENDER_PROVIDER=ffmpeg is not ready if binaries are missing."""
    env_mock = {
        "RENDER_PROVIDER": "ffmpeg",
        "FFMPEG_BINARY": "custom-ffmpeg",
        "FFPROBE_BINARY": "custom-ffprobe",
    }

    # Simulate both missing
    with patch.dict(os.environ, env_mock, clear=True), \
         patch("shutil.which", return_value=None):
        status = _build_render_status(required=True)
        assert status.configured is False
        assert status.ready is False
        assert status.code == "FFMPEG_NOT_INSTALLED"
        assert "missing custom-ffmpeg, custom-ffprobe" in status.message

    # Simulate one missing
    def mock_which_side_effect(name):
        if name == "custom-ffmpeg":
            return "/usr/bin/custom-ffmpeg"
        return None

    with patch.dict(os.environ, env_mock, clear=True), \
         patch("shutil.which", side_effect=mock_which_side_effect):
        status = _build_render_status(required=True)
        assert status.configured is False
        assert status.ready is False
        assert status.code == "FFMPEG_NOT_INSTALLED"
        assert "missing custom-ffprobe" in status.message


def test_render_provider_shotstack_requires_key():
    """Test RENDER_PROVIDER=shotstack requires SHOTSTACK_KEY."""
    env_mock = {
        "RENDER_PROVIDER": "shotstack",
        "SHOTSTACK_KEY": "",
    }
    with patch.dict(os.environ, env_mock, clear=True):
        status = _build_render_status(required=True)
        assert status.configured is False
        assert status.ready is False
        assert status.code == "RENDER_PROVIDER_NOT_CONFIGURED"

    env_mock_with_key = {
        "RENDER_PROVIDER": "shotstack",
        "SHOTSTACK_KEY": "dummy-key",
    }
    with patch.dict(os.environ, env_mock_with_key, clear=True):
        status = _build_render_status(required=True)
        assert status.configured is True
        assert status.ready is True


def test_render_provider_invalid():
    """Test invalid RENDER_PROVIDER triggers expected error."""
    env_mock = {
        "RENDER_PROVIDER": "invalid-provider-name",
    }
    with patch.dict(os.environ, env_mock, clear=True):
        status = _build_render_status(required=True)
        assert status.configured is False
        assert status.ready is False
        assert status.code == "INVALID_RENDER_PROVIDER"
        assert "invalid-provider-name" in status.message
