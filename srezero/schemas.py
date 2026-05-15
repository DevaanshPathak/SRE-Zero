"""Pydantic schemas for actions, observations, and step results."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ServiceName = Literal["web_server", "database", "cache", "message_queue", "load_balancer"]
ActionType = Literal[
    "inspect_logs",
    "inspect_metrics",
    "check_status",
    "inspect_config",
    "restart_service",
    "update_config",
    "resolve_incident",
    "escalate",
]
ConfigValue = str | int | float | bool


class Action(BaseModel):
    """Structured environment action."""

    model_config = ConfigDict(extra="forbid")

    action_type: ActionType
    service: str | None = None
    key: str | None = None
    value: ConfigValue | None = None
    root_cause: str | None = None
    fix: str | None = None
    reason: str | None = None


class ActionResult(BaseModel):
    """Text and structured result returned by a tool action."""

    summary: str
    details: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class Observation(BaseModel):
    """Agent-visible observation.

    Hidden task solution fields such as root cause and correct fix are intentionally omitted.
    """

    incident_id: str
    step: int
    steps_remaining: int
    alert: str
    last_action: str | None = None
    last_result: ActionResult
    known_findings: list[str] = Field(default_factory=list)
    available_tools: list[str] = Field(default_factory=list)
    done: bool = False


class StepResult(BaseModel):
    """Environment response after one action."""

    observation: Observation
    reward: float
    done: bool
    info: dict[str, Any] = Field(default_factory=dict)
