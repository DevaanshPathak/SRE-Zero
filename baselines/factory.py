"""Baseline agent factory."""

from __future__ import annotations

from typing import Protocol

from baselines.llm_agent import (
    FrontierLLMBaselineAgent,
    GuidedOpenSourceLLMBaselineAgent,
    OpenSourceLLMBaselineAgent,
    OpenSourceReActLLMBaselineAgent,
    PromptingBaselineAgent,
    ReActBaselineAgent,
)
from baselines.random_agent import RandomAgent
from baselines.scripted_expert import ScriptedExpertAgent
from srezero.llm_config import LLMConfig
from srezero.schemas import Action, Observation

AGENT_CHOICES = (
    "random",
    "scripted",
    "prompting",
    "react",
    "open_source",
    "open_source_react",
    "guided_open_source",
    "frontier",
)


class Agent(Protocol):
    def reset(self) -> None: ...

    def act(self, observation: Observation) -> Action | str: ...


def build_agent(
    agent_name: str,
    seed: int = 0,
    *,
    model_override: str | None = None,
    base_url_override: str | None = None,
) -> Agent:
    if agent_name == "random":
        return RandomAgent(seed=seed)
    if agent_name == "scripted":
        return ScriptedExpertAgent()
    if agent_name == "prompting":
        config = LLMConfig.from_env(
            "prompting",
            model_override=model_override,
            base_url_override=base_url_override,
        )
        return PromptingBaselineAgent(config=config)
    if agent_name == "react":
        config = LLMConfig.from_env(
            "react",
            model_override=model_override,
            base_url_override=base_url_override,
        )
        return ReActBaselineAgent(config=config)
    if agent_name == "open_source":
        config = LLMConfig.from_env(
            "open_source",
            model_override=model_override,
            base_url_override=base_url_override,
        )
        return OpenSourceLLMBaselineAgent(config=config)
    if agent_name == "open_source_react":
        config = LLMConfig.from_env(
            "open_source",
            model_override=model_override,
            base_url_override=base_url_override,
        )
        return OpenSourceReActLLMBaselineAgent(config=config)
    if agent_name == "guided_open_source":
        config = LLMConfig.from_env(
            "open_source",
            model_override=model_override,
            base_url_override=base_url_override,
        )
        return GuidedOpenSourceLLMBaselineAgent(config=config)
    if agent_name == "frontier":
        config = LLMConfig.from_env(
            "frontier",
            model_override=model_override,
            base_url_override=base_url_override,
        )
        return FrontierLLMBaselineAgent(config=config)
    raise ValueError(f"Unknown agent {agent_name!r}")
