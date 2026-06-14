"""Base incident task definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import ceil

from srezero.schemas import Action, ConfigValue, ServiceName
from srezero.services import Service


def normalize_text(value: str) -> str:
    return " ".join(value.lower().replace("_", " ").replace("-", " ").split())


def _service_text_matches(service: ServiceName, normalized_text: str) -> bool:
    service_text = normalize_text(service)
    aliases = {
        "web_server": ("web server", "web", "api"),
        "database": ("database", "db"),
        "cache": ("cache",),
        "message_queue": ("message queue", "queue", "mq"),
        "load_balancer": ("load balancer", "balancer", "lb"),
    }
    return service_text in normalized_text or any(
        alias in normalized_text for alias in aliases.get(service, ())
    )


def _config_key_matches(key: str, normalized_text: str) -> bool:
    key_text = normalize_text(key)
    if key_text in normalized_text:
        return True
    tokens = [token for token in key_text.split() if token not in {"enabled", "valid"}]
    if tokens and all(token in normalized_text for token in tokens):
        return True
    aliases = {
        "db pool size": ("connection pool", "pool size", "database pool"),
        "timeout ms": ("timeout",),
        "ttl seconds": ("ttl", "time to live"),
        "memory limit mb": ("memory limit",),
        "consumer concurrency": ("consumer concurrency", "consumers"),
        "health check path": ("health check",),
        "query timeout ms": ("query timeout",),
        "max connections": ("connection limit", "connections"),
        "retry limit": ("retry limit", "retries"),
        "sticky sessions": ("sticky sessions", "session affinity"),
        "visibility timeout seconds": ("visibility timeout",),
        "rate limit rps": ("rate limit",),
        "autovacuum enabled": ("autovacuum",),
        "compression enabled": ("compression",),
        "max in flight": ("in flight",),
        "idle timeout seconds": ("idle timeout",),
        "cache host": ("cache host",),
        "read replica enabled": ("read replica", "replica"),
        "backend weight canary": ("backend weight", "canary weight"),
        "auth token valid": ("auth token", "token"),
        "index enabled": ("index",),
    }
    return any(alias in normalized_text for alias in aliases.get(key_text, ()))


def _boolean_value_matches(value: ConfigValue, normalized_text: str) -> bool:
    if value is True:
        return any(term in normalized_text for term in ("enable", "enabled", "true", "valid"))
    if value is False:
        return any(term in normalized_text for term in ("disable", "disabled", "false"))
    return False


@dataclass(frozen=True)
class CorrectFix:
    """Task-level remediation validator."""

    action_type: str
    service: ServiceName
    key: str | None = None
    min_numeric_value: float | None = None
    exact_value: ConfigValue | None = None
    fix_keywords: tuple[str, ...] = ()

    def matches_action(self, action: Action) -> bool:
        if action.action_type != self.action_type or action.service != self.service:
            return False
        if self.action_type == "restart_service":
            return True
        if self.action_type != "update_config":
            return False
        if self.key is not None and (action.key or "").upper() != self.key.upper():
            return False
        if self.exact_value is not None:
            return action.value == self.exact_value
        if self.min_numeric_value is not None:
            try:
                return float(action.value) >= self.min_numeric_value  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return False
        return True

    def matches_fix_text(self, text: str) -> bool:
        normalized = normalize_text(text)
        if not self.fix_keywords:
            return True
        if all(normalize_text(keyword) in normalized for keyword in self.fix_keywords):
            return True
        return self._matches_canonical_fix_text(normalized)

    def _matches_canonical_fix_text(self, normalized_text: str) -> bool:
        service_matches = _service_text_matches(self.service, normalized_text)
        if self.action_type == "restart_service":
            restart_terms = ("restart", "restarted", "reboot", "recover", "bring back")
            return service_matches and any(term in normalized_text for term in restart_terms)
        if self.action_type != "update_config":
            return False
        key_matches = self.key is not None and _config_key_matches(self.key, normalized_text)
        value_matches = (
            self.exact_value is None
            or normalize_text(str(self.exact_value)) in normalized_text
            or _boolean_value_matches(self.exact_value, normalized_text)
        )
        return service_matches and key_matches and value_matches


@dataclass
class IncidentTask:
    """Immutable task metadata plus mutable service fixture factory."""

    task_id: str
    difficulty: str
    alert: str
    root_cause: str
    root_cause_keywords: tuple[str, ...]
    relevant_evidence: tuple[str, ...]
    evidence_descriptions: dict[str, str]
    correct_fix: CorrectFix
    services: dict[ServiceName, Service]
    expected_action_pattern: tuple[str, ...] = ()
    distractors: tuple[str, ...] = ()
    distractor_services: tuple[ServiceName, ...] = ()
    max_steps: int = 8
    terminal_on_wrong_resolution: bool = True
    metadata: dict[str, str] = field(default_factory=dict)

    def fresh_services(self) -> dict[ServiceName, Service]:
        return {name: service.model_copy(deep=True) for name, service in self.services.items()}

    def matching_evidence_keys(self, action: Action) -> list[str]:
        if action.service is None:
            return []
        base_key = f"{action.action_type}:{action.service}"
        candidates = [base_key]
        if action.action_type == "inspect_config":
            if action.key is not None:
                candidates.append(f"{base_key}:{action.key.upper()}")
            else:
                candidates.extend(
                    key
                    for key in self.relevant_evidence
                    if key.startswith(f"inspect_config:{action.service}:")
                )
        return [key for key in candidates if key in self.relevant_evidence]

    def evidence_description(self, key: str) -> str:
        return self.evidence_descriptions.get(key, key)

    def matches_root_cause(self, text: str) -> bool:
        normalized = normalize_text(text)
        if normalize_text(self.root_cause) in normalized:
            return True
        matches = sum(
            1 for keyword in self.root_cause_keywords if normalize_text(keyword) in normalized
        )
        required = max(1, ceil(len(self.root_cause_keywords) / 2))
        return matches >= required

    def remediation_matches(self, action: Action) -> bool:
        return self.correct_fix.matches_action(action)

    def fix_text_matches(self, text: str) -> bool:
        return self.correct_fix.matches_fix_text(text)
