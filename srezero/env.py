"""Core SRE-Zero Mini environment."""

from __future__ import annotations

import random
from collections import Counter
from typing import Any

from srezero.actions import (
    AVAILABLE_ACTION_TEMPLATES,
    ActionParseError,
    format_action,
    parse_action,
)
from srezero.metrics import EpisodeMetrics
from srezero.rewards import RewardTracker
from srezero.schemas import Action, ActionResult, Observation, ServiceName, StepResult
from srezero.services import Service
from srezero.task_registry import get_task, list_task_ids
from srezero.tasks import IncidentTask

SERVICE_TOOL_ACTIONS = {
    "inspect_logs",
    "inspect_metrics",
    "check_status",
    "inspect_config",
    "restart_service",
    "update_config",
}


class SREEnv:
    """Deterministic incident-response environment."""

    def __init__(self) -> None:
        self.task: IncidentTask | None = None
        self.services: dict[ServiceName, Service] = {}
        self.step_count = 0
        self.done = False
        self.known_findings: list[str] = []
        self.evidence_found: set[str] = set()
        self.metrics = EpisodeMetrics()
        self.reward_tracker = RewardTracker(total_evidence=1)
        self._seen_actions: Counter[str] = Counter()
        self._seen_invalid_actions: Counter[str] = Counter()
        self._correct_remediation_applied = False
        self._last_terminal_reason: str | None = None

    def reset(self, task_id: str | None = None, seed: int | None = None) -> Observation:
        rng = random.Random(seed)
        selected_task_id = task_id if task_id is not None else rng.choice(list_task_ids())
        self.task = get_task(selected_task_id)
        self.services = self.task.fresh_services()
        self.step_count = 0
        self.done = False
        self.known_findings = []
        self.evidence_found = set()
        self.metrics = EpisodeMetrics()
        self.reward_tracker = RewardTracker(total_evidence=len(self.task.relevant_evidence))
        self._seen_actions = Counter()
        self._seen_invalid_actions = Counter()
        self._correct_remediation_applied = False
        self._last_terminal_reason = None
        return self._observation(
            last_action=None,
            result=ActionResult(
                summary="Incident opened.",
                details={"difficulty": self.task.difficulty},
            ),
        )

    def step(self, action: Action | str) -> StepResult:
        self._require_reset()
        if self.done:
            result = ActionResult(
                summary="Episode is already done.",
                error="episode_done",
                details={"terminal_reason": self._last_terminal_reason},
            )
            return StepResult(
                observation=self._observation(last_action=None, result=result),
                reward=0.0,
                done=True,
                info=self._info(invalid_action=False, terminal_reason=self._last_terminal_reason),
            )

        previous_raw_score = self.reward_tracker.raw_score()
        invalid_action = False
        terminal_reason: str | None = None
        canonical_action: str | None

        try:
            parsed_action = parse_action(action)
            canonical_action = format_action(parsed_action)
        except ActionParseError as exc:
            canonical_action = str(action)
            invalid_action = True
            result = self._record_invalid_action(canonical_action, str(exc))
        else:
            self.step_count += 1
            self.metrics.total_steps += 1
            if self._has_invalid_service(parsed_action):
                invalid_action = True
                result = self._record_invalid_action(
                    canonical_action,
                    "invalid_service",
                    increment_step=False,
                    details={"service": parsed_action.service},
                )
            else:
                repeated = self._seen_actions[canonical_action] > 0
                self._seen_actions[canonical_action] += 1
                result, terminal_reason = self._execute_action(parsed_action)
                new_evidence = self._record_evidence(parsed_action)

                if repeated and not new_evidence and parsed_action.action_type not in {
                    "resolve_incident",
                    "escalate",
                }:
                    self.metrics.repeated_actions += 1
                    self.reward_tracker.add_penalty("repeated_useless_action")

        if not self.done and self.step_count >= self._task.max_steps:
            self.done = True
            terminal_reason = terminal_reason or "step_budget_exhausted"

        if self.done:
            self._last_terminal_reason = terminal_reason
            self.metrics.final_reward = self.reward_tracker.episode_score()

        reward = max(-1.0, min(1.0, self.reward_tracker.raw_score() - previous_raw_score))
        observation = self._observation(last_action=canonical_action, result=result)
        return StepResult(
            observation=observation,
            reward=reward,
            done=self.done,
            info=self._info(invalid_action=invalid_action, terminal_reason=terminal_reason),
        )

    def available_actions(self) -> list[str]:
        return list(AVAILABLE_ACTION_TEMPLATES)

    def current_state(self) -> dict[str, Any]:
        self._require_reset()
        return {
            "task_id": self._task.task_id,
            "step": self.step_count,
            "done": self.done,
            "known_findings": list(self.known_findings),
            "evidence_found": sorted(self.evidence_found),
            "services": {
                name: {
                    "status": service.status,
                    "metrics": dict(service.metrics),
                    "config": dict(service.config),
                    "dependencies": list(service.dependencies),
                }
                for name, service in self.services.items()
            },
            "metrics": self.metrics.model_dump(),
        }

    def is_done(self) -> bool:
        return self.done

    @property
    def _task(self) -> IncidentTask:
        if self.task is None:
            raise RuntimeError("Environment must be reset before use.")
        return self.task

    def _require_reset(self) -> None:
        _ = self._task

    def _record_invalid_action(
        self,
        canonical_action: str,
        error: str,
        *,
        increment_step: bool = True,
        details: dict[str, object] | None = None,
    ) -> ActionResult:
        if increment_step:
            self.step_count += 1
            self.metrics.total_steps += 1
        self.metrics.invalid_actions += 1
        self._seen_invalid_actions[canonical_action] += 1
        if self._seen_invalid_actions[canonical_action] > 1:
            self.metrics.repeated_actions += 1
            self.reward_tracker.add_penalty("repeated_invalid_action")
        else:
            self.reward_tracker.add_penalty("invalid_action")
        return ActionResult(
            summary="Invalid action.",
            error=error,
            details={"action": canonical_action, **(details or {})},
        )

    def _has_invalid_service(self, action: Action) -> bool:
        if action.action_type not in SERVICE_TOOL_ACTIONS:
            return False
        return action.service is None or action.service not in self.services

    def _service(self, service_name: str | None) -> Service:
        if service_name is None or service_name not in self.services:
            raise RuntimeError(f"Invalid service access: {service_name!r}")
        return self.services[service_name]

    def _observation(self, last_action: str | None, result: ActionResult) -> Observation:
        return Observation(
            incident_id=self._task.task_id,
            step=self.step_count,
            steps_remaining=max(0, self._task.max_steps - self.step_count),
            alert=self._task.alert,
            last_action=last_action,
            last_result=result,
            known_findings=list(self.known_findings),
            available_tools=self.available_actions(),
            done=self.done,
        )

    def _info(self, invalid_action: bool, terminal_reason: str | None) -> dict[str, Any]:
        return {
            "reward_components": self.reward_tracker.snapshot().model_dump(),
            "invalid_action": invalid_action,
            "terminal_reason": terminal_reason,
            "metrics_so_far": self.metrics.model_dump(),
            "evidence_coverage": len(self.evidence_found)
            / max(1, len(self._task.relevant_evidence)),
        }

    def _execute_action(self, action: Action) -> tuple[ActionResult, str | None]:
        match action.action_type:
            case "inspect_logs":
                service = self._service(action.service)
                return (
                    ActionResult(
                        summary=f"Inspected logs for {service.name}.",
                        details={"service": service.name, "logs": list(service.logs)},
                    ),
                    None,
                )
            case "inspect_metrics":
                service = self._service(action.service)
                return (
                    ActionResult(
                        summary=f"Inspected metrics for {service.name}.",
                        details={"service": service.name, "metrics": dict(service.metrics)},
                    ),
                    None,
                )
            case "check_status":
                service = self._service(action.service)
                return (
                    ActionResult(
                        summary=f"{service.name} status is {service.status}.",
                        details={"service": service.name, "status": service.status},
                    ),
                    None,
                )
            case "inspect_config":
                service = self._service(action.service)
                config = (
                    dict(service.config)
                    if action.key is None
                    else {action.key: service.config.get(action.key)}
                )
                return (
                    ActionResult(
                        summary=f"Inspected config for {service.name}.",
                        details={"service": service.name, "config": config},
                    ),
                    None,
                )
            case "restart_service":
                return self._restart_service(action), None
            case "update_config":
                return self._update_config(action), None
            case "resolve_incident":
                return self._resolve_incident(action)
            case "escalate":
                self.done = True
                return (
                    ActionResult(
                        summary="Incident escalated.",
                        details={"reason": action.reason},
                    ),
                    "escalated",
                )

    def _restart_service(self, action: Action) -> ActionResult:
        self.metrics.remediation_actions += 1
        if action.service == self._task.correct_fix.service:
            self.metrics.correct_service_remediations += 1
        service = self._service(action.service)
        service.status = "healthy"
        service.logs.append("INFO service restarted by incident responder")

        if self._task.remediation_matches(action):
            self._correct_remediation_applied = True
            self.metrics.correct_remediations += 1
            self.metrics.correct_remediation_applied = True
            self.reward_tracker.mark_remediation()
            return ActionResult(
                summary=f"Restarted {service.name}.",
                details={
                    "service": service.name,
                    "status": service.status,
                    "correct_remediation": True,
                },
            )

        self.metrics.wrong_remediations += 1
        self._record_distractor_failure(action)
        self.reward_tracker.add_penalty("wrong_remediation")
        if action.service != self._task.correct_fix.service:
            self.reward_tracker.add_penalty("restart_unrelated_service")
        return ActionResult(
            summary=f"Restarted {service.name}, but the incident persists.",
            details={"service": service.name, "correct_remediation": False},
        )

    def _update_config(self, action: Action) -> ActionResult:
        self.metrics.remediation_actions += 1
        if action.service == self._task.correct_fix.service:
            self.metrics.correct_service_remediations += 1
        service = self._service(action.service)
        previous = service.config.get(action.key or "")
        if action.key is not None and action.value is not None:
            service.config[action.key] = action.value

        if self._task.remediation_matches(action):
            self._correct_remediation_applied = True
            self.metrics.correct_remediations += 1
            self.metrics.correct_remediation_applied = True
            self.reward_tracker.mark_remediation()
            return ActionResult(
                summary=f"Updated {service.name} config {action.key}.",
                details={
                    "service": service.name,
                    "key": action.key,
                    "previous": previous,
                    "value": action.value,
                    "correct_remediation": True,
                },
            )

        self.metrics.wrong_remediations += 1
        self._record_distractor_failure(action)
        self.reward_tracker.add_penalty("wrong_remediation")
        return ActionResult(
            summary=f"Updated {service.name} config, but the incident persists.",
            details={
                "service": service.name,
                "key": action.key,
                "previous": previous,
                "value": action.value,
                "correct_remediation": False,
            },
        )

    def _resolve_incident(self, action: Action) -> tuple[ActionResult, str | None]:
        root_ok = self._task.matches_root_cause(action.root_cause or "")
        fix_ok = self._task.fix_text_matches(action.fix or "")

        if root_ok:
            self.metrics.root_cause_identified = True
            self.reward_tracker.mark_root_cause()
        if fix_ok:
            self.metrics.fix_identified = True

        if root_ok and fix_ok and self._correct_remediation_applied:
            self.reward_tracker.mark_resolution()
            self.reward_tracker.mark_efficiency(self.step_count, self._task.max_steps)
            self.done = True
            self.metrics.success = True
            return (
                ActionResult(
                    summary="Incident resolved.",
                    details={"root_cause_match": True, "fix_match": True},
                ),
                "resolved",
            )

        self.metrics.premature_resolutions += 1
        self.reward_tracker.add_penalty("premature_resolution")
        if self._task.terminal_on_wrong_resolution:
            self.done = True
            terminal_reason = "premature_or_incorrect_resolution"
        else:
            terminal_reason = None
        return (
            ActionResult(
                summary="Resolution rejected.",
                details={
                    "root_cause_match": root_ok,
                    "fix_match": fix_ok,
                    "remediation_applied": self._correct_remediation_applied,
                },
                error="resolution_rejected",
            ),
            terminal_reason,
        )

    def _record_evidence(self, action: Action) -> bool:
        matching_keys = self._task.matching_evidence_keys(action)
        new_keys = [key for key in matching_keys if key not in self.evidence_found]
        if not new_keys:
            return False

        for key in new_keys:
            self.evidence_found.add(key)
            finding = self._task.evidence_description(key)
            if finding not in self.known_findings:
                self.known_findings.append(finding)

        self.metrics.evidence_actions += 1
        self.reward_tracker.mark_evidence(len(self.evidence_found))
        return True

    def _record_distractor_failure(self, action: Action) -> None:
        if action.service in self._task.distractor_services:
            self.metrics.distractor_failures += 1
