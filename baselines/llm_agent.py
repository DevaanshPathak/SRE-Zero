"""Optional OpenAI-compatible LLM baselines."""

from __future__ import annotations

import json
import re

from baselines.prompts import template_for_profile
from srezero.actions import parse_action
from srezero.llm_config import LLMConfig, LLMProfile, OpenAICompatibleChatClient
from srezero.schemas import Action, Observation

ACTION_NAMES = (
    "inspect_logs",
    "inspect_metrics",
    "check_status",
    "inspect_config",
    "restart_service",
    "update_config",
    "resolve_incident",
    "escalate",
)
ACTION_RE = re.compile(
    rf"(?P<action>(?:{'|'.join(ACTION_NAMES)})\s*\([^\n\r]*\))",
    re.IGNORECASE,
)
BARE_EVIDENCE_ACTION_RE = re.compile(
    r"^\s*(?:Action:\s*)?"
    r"(?P<action>inspect_logs|inspect_metrics|check_status)\s*\.?\s*$",
    re.IGNORECASE,
)
SERVICE_HINTS = {
    "web_server": ("web_server", "web server", "api", "timeout"),
    "database": ("database", "db", "connection", "query"),
    "cache": ("cache", "hit rate", "ttl", "eviction"),
    "message_queue": ("message_queue", "message queue", "queue", "backlog", "consumer"),
    "load_balancer": ("load_balancer", "load balancer", "balancer", "backend", "502"),
}


class PromptingBaselineAgent:
    """LLM baseline that prompts from the current observation only."""

    def __init__(
        self,
        *,
        profile: LLMProfile = "prompting",
        config: LLMConfig | None = None,
    ) -> None:
        self.profile = profile
        self.config = config or LLMConfig.from_env(profile)
        self.client = OpenAICompatibleChatClient(self.config)

    def reset(self) -> None:
        return None

    def act(self, observation: Observation) -> Action | str:
        messages = [
            {"role": "system", "content": template_for_profile("prompting").system},
            {
                "role": "user",
                "content": template_for_profile("prompting").user_message(observation),
            },
        ]
        response = self.client.complete(messages)
        return _extract_action(response, observation)


class ReActBaselineAgent:
    """LLM baseline that keeps a compact Thought/Action interaction history."""

    def __init__(
        self,
        *,
        profile: LLMProfile = "react",
        config: LLMConfig | None = None,
    ) -> None:
        self.profile = profile
        self.config = config or LLMConfig.from_env(profile)
        self.client = OpenAICompatibleChatClient(self.config)
        self.messages: list[dict[str, str]] = []

    def reset(self) -> None:
        self.messages = [{"role": "system", "content": template_for_profile("react").system}]

    def act(self, observation: Observation) -> Action | str:
        if not self.messages:
            self.reset()
        self.messages.append(
            {
                "role": "user",
                "content": (
                    f"{template_for_profile('react').user_message(observation)}\n\n"
                    "Respond with one brief Thought and one Action."
                ),
            }
        )
        response = self.client.complete(self.messages)
        self.messages.append({"role": "assistant", "content": response})
        return _extract_action(response, observation)


class OpenSourceLLMBaselineAgent(PromptingBaselineAgent):
    """Prompting baseline profile intended for OpenAI-compatible open-source servers."""

    def __init__(self, *, config: LLMConfig | None = None) -> None:
        super().__init__(profile="open_source", config=config)


class OpenSourceReActLLMBaselineAgent(ReActBaselineAgent):
    """ReAct loop using the open-source model profile."""

    def __init__(self, *, config: LLMConfig | None = None) -> None:
        super().__init__(profile="open_source", config=config)


class GuidedOpenSourceLLMBaselineAgent:
    """Open-source LLM baseline with a small protocol controller.

    The controller does not inspect hidden task state. It enforces the public action
    contract, asks for evidence before remediation while budget allows, and blocks
    final resolution until the agent has attempted a remediation.
    """

    def __init__(self, *, config: LLMConfig | None = None, max_repairs: int = 2) -> None:
        self.config = config or LLMConfig.from_env("open_source")
        self.client = OpenAICompatibleChatClient(self.config)
        self.max_repairs = max_repairs
        self.messages: list[dict[str, str]] = []
        self.remediation_attempted = False

    def reset(self) -> None:
        self.remediation_attempted = False
        self.messages = [
            {
                "role": "system",
                "content": (
                    f"{template_for_profile('react').system}\n\n"
                    "Controller policy: output exactly one valid SRE-Zero Action line. "
                    "Gather at least two pieces of evidence before remediation when step "
                    "budget allows. Do not call resolve_incident until after a remediation "
                    "action has been attempted."
                ),
            }
        ]

    def act(self, observation: Observation) -> Action | str:
        if not self.messages:
            self.reset()
        prompt = (
            f"{template_for_profile('react').user_message(observation)}\n\n"
            f"Known findings count: {len(observation.known_findings)}.\n"
            f"Remediation attempted: {self.remediation_attempted}.\n"
            "Respond with one brief Thought and one Action."
        )
        self.messages.append({"role": "user", "content": prompt})
        for _ in range(self.max_repairs + 1):
            response = self.client.complete(self.messages)
            self.messages.append({"role": "assistant", "content": response})
            candidate = _extract_action(response, observation)
            action = _as_action(candidate)
            violation = self._guided_violation(action, observation)
            if violation is None and action is not None:
                self._record_guided_action(action)
                return action
            self.messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Previous output rejected: {violation}. "
                        "Return exactly one valid SRE-Zero action call now."
                    ),
                }
            )

        fallback = _guided_fallback_action(observation, self.remediation_attempted)
        self._record_guided_action(fallback)
        return fallback

    def _guided_violation(
        self,
        action: Action | None,
        observation: Observation,
    ) -> str | None:
        if action is None:
            return "malformed or unsupported action"
        if _needs_more_evidence(observation) and action.action_type in {
            "restart_service",
            "update_config",
            "resolve_incident",
        }:
            return "gather evidence before remediation or resolution"
        if action.action_type == "resolve_incident" and not self.remediation_attempted:
            return "resolve_incident is only allowed after a remediation attempt"
        return None

    def _record_guided_action(self, action: Action) -> None:
        if action.action_type in {"restart_service", "update_config"}:
            self.remediation_attempted = True


class FrontierLLMBaselineAgent(ReActBaselineAgent):
    """ReAct baseline profile intended for frontier hosted models."""

    def __init__(self, *, config: LLMConfig | None = None) -> None:
        super().__init__(profile="frontier", config=config)


def _extract_action(response: str, observation: Observation | None = None) -> Action | str:
    for line in reversed(response.strip().splitlines()):
        candidate = _candidate_from_text(line)
        if candidate is not None:
            return _normalize_or_return(candidate)
        repaired = _repair_bare_evidence_action(line, observation)
        if repaired is not None:
            return repaired
    candidate = _candidate_from_text(response)
    if candidate is not None:
        return _normalize_or_return(candidate)
    repaired = _repair_bare_evidence_action(response, observation)
    if repaired is not None:
        return repaired
    return response.strip()


def _candidate_from_text(text: str) -> str | None:
    match = ACTION_RE.search(text)
    if match is None:
        return None
    return match.group("action").strip()


def _normalize_or_return(candidate: str) -> Action | str:
    try:
        return parse_action(candidate)
    except ValueError:
        return candidate


def _as_action(candidate: Action | str) -> Action | None:
    if isinstance(candidate, Action):
        return candidate
    try:
        parsed = parse_action(candidate)
    except ValueError:
        return None
    return parsed


def _needs_more_evidence(observation: Observation) -> bool:
    return len(observation.known_findings) < 2 and observation.steps_remaining > 3


def _guided_fallback_action(
    observation: Observation,
    remediation_attempted: bool,
) -> Action:
    service = _infer_service(observation) or "web_server"
    if _needs_more_evidence(observation):
        action_cycle = ("check_status", "inspect_logs", "inspect_metrics", "inspect_config")
        action_name = action_cycle[observation.step % len(action_cycle)]
        return parse_action(f"{action_name}({service})")
    if not remediation_attempted:
        return parse_action(f"inspect_config({service})")
    return parse_action(f"inspect_metrics({service})")


def _repair_bare_evidence_action(
    response: str,
    observation: Observation | None,
) -> Action | str | None:
    if observation is None:
        return None
    match = BARE_EVIDENCE_ACTION_RE.match(response)
    if match is None:
        return None
    service = _infer_service(observation)
    if service is None:
        return None
    return _normalize_or_return(f"{match.group('action').lower()}({service})")


def _infer_service(observation: Observation) -> str | None:
    text = " ".join(
        [
            observation.alert,
            observation.last_result.summary if observation.last_result else "",
            _details_text(observation),
            " ".join(observation.known_findings),
        ]
    ).lower()
    scores = {
        service: sum(1 for hint in hints if hint in text)
        for service, hints in SERVICE_HINTS.items()
    }
    best_service, best_score = max(scores.items(), key=lambda item: item[1])
    if best_score <= 0:
        return None
    return best_service


def _details_text(observation: Observation) -> str:
    if observation.last_result is None:
        return ""
    details = observation.last_result.details
    if isinstance(details, str):
        return details
    return json.dumps(details, sort_keys=True)
