"""Optional OpenAI-compatible LLM baselines."""

from __future__ import annotations

import json
import re

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
            {"role": "system", "content": _system_prompt()},
            {
                "role": "user",
                "content": (
                    "Choose the next incident-response action from this observation.\n"
                    f"{_observation_json(observation)}"
                ),
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
        self.messages = [{"role": "system", "content": _react_system_prompt()}]

    def act(self, observation: Observation) -> Action | str:
        if not self.messages:
            self.reset()
        self.messages.append(
            {
                "role": "user",
                "content": (
                    "Observation:\n"
                    f"{_observation_json(observation)}\n\n"
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


class FrontierLLMBaselineAgent(ReActBaselineAgent):
    """ReAct baseline profile intended for frontier hosted models."""

    def __init__(self, *, config: LLMConfig | None = None) -> None:
        super().__init__(profile="frontier", config=config)


def _system_prompt() -> str:
    return (
        "You are evaluating SRE-Zero, a simulated incident-response benchmark. "
        "Use only the available simulator actions. Do not invent tools. "
        "Gather evidence before remediation. Apply minimal fixes. "
        "Return exactly one action call and no extra text.\n\n"
        "The action must include required arguments in parentheses. "
        "Bad: inspect_metrics. Good: inspect_metrics(cache).\n\n"
        "Allowed actions:\n"
        "- inspect_logs(service)\n"
        "- inspect_metrics(service)\n"
        "- check_status(service)\n"
        "- inspect_config(service, key?)\n"
        "- restart_service(service)\n"
        "- update_config(service, key, value)\n"
        "- resolve_incident(root_cause, fix)\n"
        "- escalate(reason)\n\n"
        "Valid services: web_server, database, cache."
    )


def _react_system_prompt() -> str:
    return (
        "You are evaluating SRE-Zero, a simulated incident-response benchmark. "
        "Use ReAct style internally, but only one simulator action may be issued per turn. "
        "Do not invent tools. Gather evidence before remediation. Apply minimal fixes.\n\n"
        "Respond in this format:\n"
        "Thought: <brief reasoning>\n"
        "Action: <one valid action call>\n\n"
        "The action must include required arguments in parentheses. "
        "Bad: inspect_logs. Good: inspect_logs(web_server).\n\n"
        "Valid services: web_server, database, cache."
    )


def _observation_json(observation: Observation) -> str:
    return json.dumps(observation.model_dump(mode="json"), indent=2)


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
