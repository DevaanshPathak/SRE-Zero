"""Load deterministic incident task configs."""

from __future__ import annotations

import json
from importlib.resources.abc import Traversable

from pydantic import BaseModel, ConfigDict, Field

from srezero.schemas import ActionType, ConfigValue, ServiceName
from srezero.services import Service, base_services
from srezero.tasks.base import CorrectFix, IncidentTask


class CorrectFixConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_type: ActionType
    service: ServiceName
    key: str | None = None
    min_numeric_value: float | None = None
    exact_value: ConfigValue | None = None
    fix_keywords: list[str] = Field(default_factory=list)


class ServicePatchConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str | None = None
    logs: list[str] | None = None
    metrics: dict[str, int | float | str] | None = None
    config: dict[str, ConfigValue] | None = None
    dependencies: list[ServiceName] | None = None


class IncidentTaskConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    difficulty: str
    alert: str
    root_cause: str
    root_cause_keywords: list[str]
    relevant_evidence: list[str]
    evidence_descriptions: dict[str, str]
    correct_fix: CorrectFixConfig
    service_patches: dict[ServiceName, ServicePatchConfig]
    expected_action_pattern: list[str] = Field(default_factory=list)
    distractors: list[str] = Field(default_factory=list)
    distractor_services: list[ServiceName] = Field(default_factory=list)
    max_steps: int = 8
    terminal_on_wrong_resolution: bool = True
    metadata: dict[str, str] = Field(default_factory=dict)


def load_task_config(resource: Traversable) -> IncidentTaskConfig:
    raw = json.loads(resource.read_text(encoding="utf-8"))
    return IncidentTaskConfig.model_validate(raw)


def build_task_from_config(config: IncidentTaskConfig) -> IncidentTask:
    services = base_services()
    for service_name, patch in config.service_patches.items():
        service = services[service_name]
        _apply_patch(service, patch)

    correct_fix = CorrectFix(
        action_type=config.correct_fix.action_type,
        service=config.correct_fix.service,
        key=config.correct_fix.key,
        min_numeric_value=config.correct_fix.min_numeric_value,
        exact_value=config.correct_fix.exact_value,
        fix_keywords=tuple(config.correct_fix.fix_keywords),
    )
    return IncidentTask(
        task_id=config.task_id,
        difficulty=config.difficulty,
        alert=config.alert,
        root_cause=config.root_cause,
        root_cause_keywords=tuple(config.root_cause_keywords),
        relevant_evidence=tuple(config.relevant_evidence),
        evidence_descriptions=dict(config.evidence_descriptions),
        correct_fix=correct_fix,
        services=services,
        expected_action_pattern=tuple(config.expected_action_pattern),
        distractors=tuple(config.distractors),
        distractor_services=tuple(config.distractor_services),
        max_steps=config.max_steps,
        terminal_on_wrong_resolution=config.terminal_on_wrong_resolution,
        metadata=dict(config.metadata),
    )


def _apply_patch(service: Service, patch: ServicePatchConfig) -> None:
    if patch.status is not None:
        service.status = patch.status
    if patch.logs is not None:
        service.logs = list(patch.logs)
    if patch.metrics is not None:
        service.metrics.update(patch.metrics)
    if patch.config is not None:
        service.config.update(patch.config)
    if patch.dependencies is not None:
        service.dependencies = list(patch.dependencies)
