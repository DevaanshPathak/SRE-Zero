"""Prompt templates for optional LLM baselines."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from srezero.schemas import Observation

PromptProfile = Literal["prompting", "react"]

VALID_SERVICES_TEXT = "web_server, database, cache, message_queue, load_balancer"
ALLOWED_ACTIONS_TEXT = """Allowed actions:
- inspect_logs(service)
- inspect_metrics(service)
- check_status(service)
- inspect_config(service, key?)
- restart_service(service)
- update_config(service, key, value)
- resolve_incident(root_cause, fix)
- escalate(reason)"""

ACTION_CONTRACT_TEXT = """Action-call contract:
- Use exactly one simulator action call.
- If the prompt asks for Thought/Action format, put the call only on the Action line.
- Do not use Markdown, JSON, code fences, bullets, or prose.
- Do not prefix actions with a namespace such as sre_zero.
- Valid examples:
  inspect_logs(database)
  inspect_metrics(cache)
  inspect_config(web_server, TIMEOUT_MS)
  update_config(database, DB_POOL_SIZE, 200)
  restart_service(cache)
  resolve_incident(database connection pool exhaustion, increase database DB_POOL_SIZE)
- Invalid examples:
  sre_zero.check_cache_status()
  Action: I would inspect cache logs
  {"action": "inspect_logs", "service": "cache"}"""


@dataclass(frozen=True)
class PromptTemplate:
    """System/user prompt pair for one baseline profile."""

    profile: PromptProfile
    system: str
    user_prefix: str

    def user_message(self, observation: Observation) -> str:
        return f"{self.user_prefix}\n{observation_json(observation)}"


PROMPTING_TEMPLATE = PromptTemplate(
    profile="prompting",
    system=(
        "You are evaluating SRE-Zero, a simulated incident-response benchmark. "
        "Use only the available simulator actions. Do not invent tools. "
        "Gather evidence before remediation. Apply minimal fixes. "
        "Return exactly one action call and no extra text.\n\n"
        "The action must include required arguments in parentheses. "
        "Bad: inspect_metrics. Good: inspect_metrics(cache).\n\n"
        f"{ALLOWED_ACTIONS_TEXT}\n\n"
        f"{ACTION_CONTRACT_TEXT}\n\n"
        f"Valid services: {VALID_SERVICES_TEXT}."
    ),
    user_prefix="Choose the next incident-response action from this observation.",
)

REACT_TEMPLATE = PromptTemplate(
    profile="react",
    system=(
        "You are evaluating SRE-Zero, a simulated incident-response benchmark. "
        "Use ReAct style internally, but only one simulator action may be issued per turn. "
        "Do not invent tools. Gather evidence before remediation. Apply minimal fixes.\n\n"
        "Respond in this format:\n"
        "Thought: <brief reasoning>\n"
        "Action: <one valid action call>\n\n"
        "The action must include required arguments in parentheses. "
        "Bad: inspect_logs. Good: inspect_logs(web_server).\n\n"
        f"{ACTION_CONTRACT_TEXT}\n\n"
        f"Valid services: {VALID_SERVICES_TEXT}."
    ),
    user_prefix="Observation:",
)


def template_for_profile(profile: PromptProfile) -> PromptTemplate:
    if profile == "prompting":
        return PROMPTING_TEMPLATE
    return REACT_TEMPLATE


def observation_json(observation: Observation) -> str:
    return json.dumps(observation.model_dump(mode="json"), indent=2)
