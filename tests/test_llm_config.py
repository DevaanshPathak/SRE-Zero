import json
import os
import urllib.error
import urllib.request
from typing import cast

from srezero.llm_config import LLMConfig, OpenAICompatibleChatClient, load_env_file


def test_load_env_file_does_not_override_existing_env(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "OPENAI_BASE_URL=https://example.test/v1\n"
        "OPENAI_MODEL=from-file\n"
        "SREZERO_LLM_TIMEOUT_SECONDS=12\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENAI_MODEL", "from-env")

    loaded = load_env_file(env_file)

    assert loaded["OPENAI_MODEL"] == "from-file"
    assert os.environ["OPENAI_MODEL"] == "from-env"


def test_load_env_file_discovers_parent_env_from_subdirectory(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    nested = tmp_path / "eval"
    nested.mkdir()
    env_file.write_text(
        "OPENAI_BASE_URL=https://example.test/v1\n"
        "OPENAI_MODEL=parent-file-model\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(nested)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    loaded = load_env_file()

    assert loaded["OPENAI_MODEL"] == "parent-file-model"
    assert os.environ["OPENAI_BASE_URL"] == "https://example.test/v1"


def test_llm_config_uses_profile_model_override(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("OPENAI_MODEL", "fallback-model")
    monkeypatch.setenv("SREZERO_REACT_MODEL", "react-model")

    config = LLMConfig.from_env("react")

    assert config.base_url == "https://example.test/v1"
    assert config.model == "react-model"


def test_llm_config_reads_provider_throttle_controls(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("OPENAI_MODEL", "fallback-model")
    monkeypatch.setenv("SREZERO_LLM_MAX_TOKENS", "2048")
    monkeypatch.setenv("SREZERO_LLM_MAX_RETRIES", "7")
    monkeypatch.setenv("SREZERO_LLM_MIN_REQUEST_INTERVAL_SECONDS", "2.5")
    monkeypatch.setenv("SREZERO_LLM_RATE_LIMIT_REQUESTS", "4")
    monkeypatch.setenv("SREZERO_LLM_RATE_LIMIT_WINDOW_SECONDS", "30")
    monkeypatch.setenv("SREZERO_LLM_REJECTION_PAUSE_THRESHOLD", "9")
    monkeypatch.setenv("SREZERO_LLM_REJECTION_PAUSE_SECONDS", "45")
    monkeypatch.setenv("SREZERO_LLM_REASONING_EXCLUDE", "false")
    monkeypatch.setenv("SREZERO_LLM_QWEN_NO_THINK", "false")

    config = LLMConfig.from_env("open_source")

    assert config.max_tokens == 2048
    assert config.max_retries == 7
    assert config.min_request_interval_seconds == 2.5
    assert config.rate_limit_requests == 4
    assert config.rate_limit_window_seconds == 30
    assert config.rejection_pause_threshold == 9
    assert config.rejection_pause_seconds == 45
    assert config.reasoning_exclude is False
    assert config.qwen_no_think is False


def test_chat_client_retries_provider_errors(monkeypatch) -> None:
    calls = 0

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"choices": [{"message": {"content": "check_status(cache)"}}]}'

    def fake_urlopen(_request: object, timeout: float) -> FakeResponse:
        nonlocal calls
        calls += 1
        assert timeout == 1
        if calls <= 3:
            raise urllib.error.URLError("temporary provider error")
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    config = LLMConfig(
        base_url="https://example.test/v1",
        model="test-model",
        timeout_seconds=1,
        max_retries=3,
        min_request_interval_seconds=0,
        rate_limit_requests=0,
        rejection_pause_threshold=0,
    )
    client = OpenAICompatibleChatClient(config)

    response = client.complete([{"role": "user", "content": "act"}])

    assert response == "check_status(cache)"
    assert calls == 4


def test_chat_client_sends_hackclub_reasoning_and_qwen_controls(monkeypatch) -> None:
    captured_payload: dict[str, object] = {}

    class FakeResponse:
        status = 200

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"choices": [{"message": {"content": "inspect_logs(database)"}}]}'

    def fake_urlopen(request: urllib.request.Request, timeout: float) -> FakeResponse:
        nonlocal captured_payload
        assert timeout == 60.0
        assert request.data is not None
        captured_payload = json_loads_bytes(cast(bytes, request.data))
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    config = LLMConfig(
        base_url="https://ai.hackclub.com/proxy/v1",
        model="qwen/qwen3.6-35b-a3b",
        max_tokens=1536,
        min_request_interval_seconds=0,
        rate_limit_requests=0,
        rejection_pause_threshold=0,
    )
    client = OpenAICompatibleChatClient(config)

    response = client.complete([{"role": "user", "content": "act"}])

    assert response == "inspect_logs(database)"
    assert captured_payload["max_tokens"] == 1536
    assert captured_payload["reasoning"] == {"exclude": True}
    messages = captured_payload["messages"]
    assert isinstance(messages, list)
    assert messages[-1]["content"].endswith("/no_think")


def test_chat_client_null_content_error_includes_finish_reason(monkeypatch) -> None:
    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return (
                b'{"choices": [{"finish_reason": "length", "message": '
                b'{"content": null, "reasoning": "thinking"}}]}'
            )

    monkeypatch.setattr(urllib.request, "urlopen", lambda *_args, **_kwargs: FakeResponse())
    config = LLMConfig(
        base_url="https://example.test/v1",
        model="qwen/qwen3.6-35b-a3b",
        max_retries=0,
        min_request_interval_seconds=0,
        rate_limit_requests=0,
        rejection_pause_threshold=0,
    )
    client = OpenAICompatibleChatClient(config)

    try:
        client.complete([{"role": "user", "content": "act"}])
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected RuntimeError")

    assert "Unexpected message content type: NoneType" in message
    assert "finish_reason='length'" in message
    assert "has_reasoning=True" in message


def json_loads_bytes(data: bytes) -> dict[str, object]:
    parsed = json.loads(data.decode("utf-8"))
    assert isinstance(parsed, dict)
    return parsed
