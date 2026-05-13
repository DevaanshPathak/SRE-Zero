"""Configuration and client utilities for optional LLM baselines."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

LLMProfile = Literal["prompting", "react", "open_source", "frontier"]


@dataclass(frozen=True)
class LLMConfig:
    """OpenAI-compatible chat completions configuration."""

    base_url: str
    model: str
    api_key: str = ""
    temperature: float = 0.0
    timeout_seconds: float = 60.0

    @classmethod
    def from_env(
        cls,
        profile: LLMProfile,
        *,
        model_override: str | None = None,
        base_url_override: str | None = None,
    ) -> LLMConfig:
        load_env_file()

        profile_prefix = f"SREZERO_{profile.upper()}"
        model = model_override or _env_first(f"{profile_prefix}_MODEL", "OPENAI_MODEL")
        base_url = _normalize_base_url(
            base_url_override or _env_first(f"{profile_prefix}_BASE_URL", "OPENAI_BASE_URL")
        )
        api_key = _env_first(f"{profile_prefix}_API_KEY", "OPENAI_API_KEY")
        temperature = _float_env("SREZERO_LLM_TEMPERATURE", default=0.0)
        timeout_seconds = _float_env("SREZERO_LLM_TIMEOUT_SECONDS", default=60.0)

        if not base_url:
            raise ValueError("Missing OPENAI_BASE_URL in environment or .env.")
        if not model:
            raise ValueError(
                f"Missing model for {profile!r}. Set {profile_prefix}_MODEL or OPENAI_MODEL."
            )
        if "api.openai.com" in base_url and not api_key:
            raise ValueError("OPENAI_API_KEY is required when OPENAI_BASE_URL points to OpenAI.")

        return cls(
            base_url=base_url,
            model=model,
            api_key=api_key,
            temperature=temperature,
            timeout_seconds=timeout_seconds,
        )


class OpenAICompatibleChatClient:
    """Minimal OpenAI-compatible chat completions client.

    This intentionally avoids adding an SDK dependency. It supports hosted OpenAI endpoints
    and local/open-source servers that expose `/chat/completions`.
    """

    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    def complete(self, messages: list[dict[str, str]], *, max_tokens: int = 256) -> str:
        endpoint = f"{self.config.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": max_tokens,
        }
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM provider returned HTTP {exc.code}: {error_body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Could not reach LLM provider: {exc.reason}") from exc

        data: dict[str, Any] = json.loads(body)
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected chat completions response: {data}") from exc
        if not isinstance(content, str):
            raise RuntimeError(f"Unexpected message content type: {type(content).__name__}")
        return content.strip()


def load_env_file(path: Path | None = None) -> dict[str, str]:
    """Load simple KEY=VALUE lines from `.env` without overriding existing env vars."""

    env_path = path or Path.cwd() / ".env"
    loaded: dict[str, str] = {}
    if not env_path.exists():
        return loaded

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = _strip_quotes(value.strip())
        loaded[key] = value
        os.environ.setdefault(key, value)
    return loaded


def _env_first(*keys: str) -> str:
    for key in keys:
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return ""


def _float_env(key: str, *, default: float) -> float:
    value = os.environ.get(key, "").strip()
    if not value:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{key} must be a float, got {value!r}") from exc


def _normalize_base_url(base_url: str) -> str:
    if not base_url:
        return base_url
    if base_url.startswith(("http://", "https://")):
        return base_url
    return f"https://{base_url}"


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
