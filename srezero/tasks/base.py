"""Base incident task definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import ceil

from srezero.schemas import Action, ConfigValue, ServiceName
from srezero.services import Service


def normalize_text(value: str) -> str:
    return " ".join(value.lower().replace("_", " ").replace("-", " ").split())


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
        return all(normalize_text(keyword) in normalized for keyword in self.fix_keywords)


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
