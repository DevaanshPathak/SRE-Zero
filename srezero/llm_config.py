"""Configuration and client utilities for optional LLM baselines."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Literal, cast

LLMProfile = Literal["prompting", "react", "open_source", "frontier"]


@dataclass(frozen=True)
class LLMConfig:
    """OpenAI-compatible chat completions configuration."""

    base_url: str
    model: str
    api_key: str = ""
    temperature: float = 0.0
    timeout_seconds: float = 60.0
    max_retries: int = 5
    min_request_interval_seconds: float = 15.0
    rate_limit_requests: int = 5
    rate_limit_window_seconds: float = 60.0
    rejection_pause_threshold: int = 3
    rejection_pause_seconds: float = 60.0

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError("max_retries must be non-negative.")
        if self.min_request_interval_seconds < 0:
            raise ValueError("min_request_interval_seconds must be non-negative.")
        if self.rate_limit_requests < 0:
            raise ValueError("rate_limit_requests must be non-negative.")
        if self.rate_limit_window_seconds < 0:
            raise ValueError("rate_limit_window_seconds must be non-negative.")
        if self.rejection_pause_threshold < 0:
            raise ValueError("rejection_pause_threshold must be non-negative.")
        if self.rejection_pause_seconds < 0:
            raise ValueError("rejection_pause_seconds must be non-negative.")

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
        max_retries = _int_env("SREZERO_LLM_MAX_RETRIES", default=5)
        min_request_interval_seconds = _float_env(
            "SREZERO_LLM_MIN_REQUEST_INTERVAL_SECONDS",
            default=15.0,
        )
        rate_limit_requests = _int_env("SREZERO_LLM_RATE_LIMIT_REQUESTS", default=5)
        rate_limit_window_seconds = _float_env(
            "SREZERO_LLM_RATE_LIMIT_WINDOW_SECONDS",
            default=60.0,
        )
        rejection_pause_threshold = _int_env(
            "SREZERO_LLM_REJECTION_PAUSE_THRESHOLD",
            default=3,
        )
        rejection_pause_seconds = _float_env(
            "SREZERO_LLM_REJECTION_PAUSE_SECONDS",
            default=60.0,
        )

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
            max_retries=max_retries,
            min_request_interval_seconds=min_request_interval_seconds,
            rate_limit_requests=rate_limit_requests,
            rate_limit_window_seconds=rate_limit_window_seconds,
            rejection_pause_threshold=rejection_pause_threshold,
            rejection_pause_seconds=rejection_pause_seconds,
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
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "SRE-Zero/0.1",
            "X-Title": "SRE-Zero",
            "HTTP-Referer": "https://github.com/DevaanshPathak/SRE-Zero",
        }
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        attempt_count = self.config.max_retries + 1
        errors: list[str] = []
        for attempt in range(1, attempt_count + 1):
            try:
                content = self._complete_once(endpoint, payload, headers)
                _RATE_LIMITER.note_request_succeeded()
                return content
            except RuntimeError as exc:
                errors.append(str(exc))
                _RATE_LIMITER.note_request_failed(self.config)
                if attempt >= attempt_count:
                    break

        last_error = errors[-1] if errors else "unknown provider error"
        if len(errors) == 1:
            raise RuntimeError(f"LLM request failed after 1 attempt: {last_error}")
        raise RuntimeError(
            f"LLM request failed after {attempt_count} attempts. "
            f"Last error: {last_error}"
        )

    def _complete_once(
        self,
        endpoint: str,
        payload: dict[str, object],
        headers: dict[str, str],
    ) -> str:
        body = self._post_json(endpoint, payload, headers)
        try:
            data: dict[str, Any] = json.loads(body)
        except json.JSONDecodeError as exc:
            raise RuntimeError("LLM provider returned invalid JSON.") from exc

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected chat completions response: {data}") from exc
        if not isinstance(content, str):
            raise RuntimeError(f"Unexpected message content type: {type(content).__name__}")
        return content.strip()

    def _post_json(
        self,
        endpoint: str,
        payload: dict[str, object],
        headers: dict[str, str],
    ) -> str:
        _RATE_LIMITER.wait_for_slot(self.config)
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                return cast(bytes, response.read()).decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM provider returned HTTP {exc.code}: {error_body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Could not reach LLM provider: {exc.reason}") from exc
        except TimeoutError as exc:
            raise RuntimeError("LLM provider request timed out.") from exc
        finally:
            _RATE_LIMITER.note_request_finished()


class _ProviderRateLimiter:
    """Process-wide throttle for optional LLM calls.

    `run_eval` creates a fresh agent/client for each task episode, so the throttle
    must live at module scope rather than on a client instance.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._request_starts: deque[float] = deque()
        self._last_finished: float | None = None
        self._consecutive_failures = 0

    def wait_for_slot(self, config: LLMConfig) -> None:
        while True:
            wait_seconds = self._seconds_until_available(config)
            if wait_seconds <= 0:
                return
            time.sleep(wait_seconds)

    def note_request_finished(self) -> None:
        with self._lock:
            self._last_finished = time.monotonic()

    def note_request_succeeded(self) -> None:
        with self._lock:
            self._consecutive_failures = 0

    def note_request_failed(self, config: LLMConfig) -> None:
        pause_seconds = 0.0
        with self._lock:
            if (
                config.rejection_pause_threshold <= 0
                or config.rejection_pause_seconds <= 0
            ):
                return
            self._consecutive_failures += 1
            if self._consecutive_failures >= config.rejection_pause_threshold:
                self._consecutive_failures = 0
                pause_seconds = config.rejection_pause_seconds
        if pause_seconds > 0:
            time.sleep(pause_seconds)

    def _seconds_until_available(self, config: LLMConfig) -> float:
        with self._lock:
            now = time.monotonic()
            self._prune_old_starts(now, config.rate_limit_window_seconds)

            wait_seconds = 0.0
            if (
                config.min_request_interval_seconds > 0
                and self._last_finished is not None
            ):
                since_last_finished = now - self._last_finished
                wait_seconds = max(
                    wait_seconds,
                    config.min_request_interval_seconds - since_last_finished,
                )

            if (
                config.rate_limit_requests > 0
                and config.rate_limit_window_seconds > 0
                and len(self._request_starts) >= config.rate_limit_requests
            ):
                oldest_start = self._request_starts[0]
                wait_seconds = max(
                    wait_seconds,
                    config.rate_limit_window_seconds - (now - oldest_start),
                )

            if wait_seconds <= 0:
                self._request_starts.append(now)
                return 0.0
            return wait_seconds

    def _prune_old_starts(self, now: float, window_seconds: float) -> None:
        if window_seconds <= 0:
            self._request_starts.clear()
            return
        while self._request_starts and now - self._request_starts[0] >= window_seconds:
            self._request_starts.popleft()


_RATE_LIMITER = _ProviderRateLimiter()


def load_env_file(path: Path | None = None) -> dict[str, str]:
    """Load simple KEY=VALUE lines from `.env` without overriding existing env vars."""

    env_path = path or _find_env_file()
    loaded: dict[str, str] = {}
    if env_path is None or not env_path.exists():
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


def _find_env_file() -> Path | None:
    """Find `.env` from common launch directories.

    Eval scripts are often run from either the repository root or `eval/`.
    Walking upward from cwd keeps both forms working without requiring secrets
    to be exported into the shell.
    """

    for start in (Path.cwd(), Path(__file__).resolve().parents[1]):
        for candidate_dir in (start, *start.parents):
            candidate = candidate_dir / ".env"
            if candidate.exists():
                return candidate
    return None


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


def _int_env(key: str, *, default: int) -> int:
    value = os.environ.get(key, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{key} must be an integer, got {value!r}") from exc


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
