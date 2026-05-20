from dataclasses import dataclass

from ai_editor import llm_client


@dataclass
class _Message:
    content: str


@dataclass
class _Choice:
    message: _Message


@dataclass
class _Completion:
    choices: list


class _FakeCompletions:
    def create(self, **kwargs):
        return _Completion(choices=[_Choice(message=_Message(content='{"ok": true}'))])


class _FakeChat:
    def __init__(self):
        self.completions = _FakeCompletions()


class _FakeClient:
    def __init__(self):
        self.chat = _FakeChat()


def _fake_provider():
    return llm_client._Provider(
        name="test",
        model="model",
        base_url="https://example.com",
        env_key="TEST_KEY",
        client=_FakeClient(),
    )


def test_ai_client_verbose_false_suppresses_try_and_success_logs(monkeypatch, capsys):
    monkeypatch.setenv("AI_CLIENT_VERBOSE", "false")
    monkeypatch.setattr(llm_client, "_ordered_providers", lambda preferred_provider=None: [_fake_provider()])

    result = llm_client.chat_json(messages=[{"role": "user", "content": "hi"}])
    captured = capsys.readouterr()

    assert result == {"ok": True}
    assert "AI client: trying" not in captured.out
    assert "AI client: test/model succeeded" not in captured.out


def test_ai_client_verbose_true_keeps_try_and_success_logs(monkeypatch, capsys):
    monkeypatch.setenv("AI_CLIENT_VERBOSE", "true")
    monkeypatch.setattr(llm_client, "_ordered_providers", lambda preferred_provider=None: [_fake_provider()])

    result = llm_client.chat_json(messages=[{"role": "user", "content": "hi"}])
    captured = capsys.readouterr()

    assert result == {"ok": True}
    assert "AI client: trying test/model" in captured.out
    assert "AI client: test/model succeeded" in captured.out
