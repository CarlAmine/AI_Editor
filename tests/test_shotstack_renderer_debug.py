import json
from pathlib import Path
from types import SimpleNamespace

import ai_editor.shotstack_renderer as renderer


class _Model:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class _FakeConfiguration:
    def __init__(self, host):
        self.host = host
        self.api_key = {}


class _FakeApiClient:
    def __init__(self, config):
        self.config = config

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def sanitize_for_serialization(self, edit_object):
        return {"timeline": "ok", "api_key_echo": self.config.api_key.get("DeveloperKey")}


class _FakeApiException(Exception):
    def __init__(self, message, *, status=None, body=None):
        super().__init__(message)
        self.status = status
        self.body = body


class _FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def _install_fake_sdk(monkeypatch, post_render):
    monkeypatch.setattr(renderer, "shotstack", SimpleNamespace(Configuration=_FakeConfiguration, ApiClient=_FakeApiClient))
    monkeypatch.setattr(
        renderer,
        "edit_api",
        SimpleNamespace(EditApi=lambda client: SimpleNamespace(post_render=post_render)),
    )
    for name in ("Soundtrack", "VideoAsset", "HtmlAsset", "Clip", "Track", "Timeline", "Output", "Edit", "Transition", "Offset"):
        monkeypatch.setattr(renderer, name, _Model)
    monkeypatch.setattr(renderer, "ApiException", _FakeApiException)


def _base_kwargs(tmp_path):
    return {
        "api_key": "super-secret-shotstack-key",
        "video_urls": ["https://example.com/clip.mp4"],
        "wait_for_render": False,
        "debug_shotstack_payload_path": str(tmp_path / "shotstack_request_payload.json"),
        "debug_shotstack_error_path": str(tmp_path / "shotstack_error.json"),
    }


def test_strip_none_values_recursively_removes_none_values():
    payload = {
        "a": None,
        "b": {"out": None, "keep": 1},
        "c": [
            {"x": None, "y": 2},
            {"z": 3},
        ],
    }

    stripped = renderer._strip_none_values(payload)

    assert stripped == {"b": {"keep": 1}, "c": [{"y": 2}, {"z": 3}]}


def test_optional_none_transition_out_is_not_passed_to_sdk_model(monkeypatch, tmp_path):
    payload_path = tmp_path / "shotstack_request_payload.json"

    def post_render(edit_object):
        video_track = edit_object.timeline.tracks[1]
        transition_obj = video_track.clips[0].transition
        assert hasattr(transition_obj, "_in")
        assert not hasattr(transition_obj, "out")
        return {"response": {"id": "render-123", "message": "queued"}}

    _install_fake_sdk(monkeypatch, post_render)

    result = renderer.create_and_render_video(
        **{
            **_base_kwargs(tmp_path),
            "video_urls": ["https://example.com/clip.mp4"],
            "canonical_timeline": [
                {
                    "start": 0,
                    "end": 5,
                    "video_src": "https://example.com/clip.mp4",
                    "duration": 5,
                    "transitionIn": "cross_dissolve",
                    "transitionOut": None,
                }
            ],
            "wait_for_render": False,
        }
    )

    assert result["success"] is True
    assert payload_path.exists()


def test_renderer_writes_payload_without_out_null(monkeypatch, tmp_path):
    payload_path = tmp_path / "shotstack_request_payload.json"

    class _FakeApiClientWithNull(_FakeApiClient):
        def sanitize_for_serialization(self, edit_object):
            return {"transition": {"in": "fade", "out": None}}

    monkeypatch.setattr(renderer, "shotstack", SimpleNamespace(Configuration=_FakeConfiguration, ApiClient=_FakeApiClientWithNull))
    monkeypatch.setattr(
        renderer,
        "edit_api",
        SimpleNamespace(EditApi=lambda client: SimpleNamespace(post_render=lambda _edit_object: {"response": {"id": "render-123", "message": "queued"}})),
    )
    for name in ("Soundtrack", "VideoAsset", "HtmlAsset", "Clip", "Track", "Timeline", "Output", "Edit", "Transition", "Offset"):
        monkeypatch.setattr(renderer, name, _Model)
    monkeypatch.setattr(renderer, "ApiException", _FakeApiException)

    result = renderer.create_and_render_video(**_base_kwargs(tmp_path))

    assert result["success"] is True
    contents = payload_path.read_text(encoding="utf-8")
    assert '"out": null' not in contents


def test_renderer_writes_error_file_on_non_2xx_create_response(monkeypatch, tmp_path):
    def post_render(_edit_object):
        raise _FakeApiException(
            "forbidden",
            status=403,
            body='{"message":"invalid api key super-secret-shotstack-key"}',
        )

    _install_fake_sdk(monkeypatch, post_render)

    result = renderer.create_and_render_video(**_base_kwargs(tmp_path))

    debug_path = tmp_path / "shotstack_error.json"
    assert result["success"] is False
    assert debug_path.exists()
    contents = debug_path.read_text(encoding="utf-8")
    assert "shotstack_create" in contents
    assert "403" in contents
    assert "super-secret-shotstack-key" not in contents


def test_renderer_writes_error_file_on_sdk_validation_failure(monkeypatch, tmp_path):
    def post_render(_edit_object):
        raise _FakeApiException(
            "Invalid type for variable 'out'. Required value type is str and passed type was NoneType at ['out']",
            status=400,
            body='{"error":"invalid payload"}',
        )

    _install_fake_sdk(monkeypatch, post_render)

    result = renderer.create_and_render_video(**_base_kwargs(tmp_path))

    debug_path = tmp_path / "shotstack_error.json"
    assert result["success"] is False
    assert debug_path.exists()
    contents = json.loads(debug_path.read_text(encoding="utf-8"))
    assert contents["stage"] == "shotstack_create"
    assert contents["offending_field"] == "out"
    assert "Optional Shotstack fields must be omitted when None." in contents["hint"]
    assert "invalid payload" in contents["response_text"] or contents["exception"]


def test_renderer_writes_error_file_on_failed_render_status(monkeypatch, tmp_path):
    def post_render(_edit_object):
        return {"response": {"id": "render-456", "message": "queued"}}

    _install_fake_sdk(monkeypatch, post_render)
    monkeypatch.setattr(renderer.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        renderer.requests,
        "get",
        lambda url, headers=None: _FakeResponse(
            200,
            payload={"response": {"status": "failed", "error": "asset url not fetchable"}},
            text='{"response":{"status":"failed","error":"asset url not fetchable"}}',
        ),
    )

    kwargs = _base_kwargs(tmp_path)
    kwargs["wait_for_render"] = True
    result = renderer.create_and_render_video(**kwargs)

    debug_path = tmp_path / "shotstack_error.json"
    assert result["success"] is False
    assert debug_path.exists()
    contents = debug_path.read_text(encoding="utf-8")
    assert "shotstack_poll" in contents
    assert "render-456" in contents
    assert "asset url not fetchable" in contents
    assert "super-secret-shotstack-key" not in contents
