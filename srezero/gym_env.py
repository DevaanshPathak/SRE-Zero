"""Gym-style API wrapper for SRE-Zero Mini.

This module intentionally does not depend on Gymnasium. It mirrors the common API shape:

- `reset(seed=None, options=None) -> (observation, info)`
- `step(action) -> (observation, reward, terminated, truncated, info)`
"""

from __future__ import annotations

from typing import Any

from srezero.env import SREEnv
from srezero.schemas import Action, Observation


class SREOpenEnv:
    """OpenEnv/Gym-style wrapper around `SREEnv`."""

    metadata = {"render_modes": ["text"]}

    def __init__(self, task_id: str | None = None) -> None:
        self.task_id = task_id
        self.env = SREEnv()
        self.action_space = self.env.available_actions()
        self.observation_space = {
            "incident_id": "str",
            "step": "int",
            "steps_remaining": "int",
            "alert": "str",
            "last_action": "str | None",
            "last_result": "ActionResult",
            "known_findings": "list[str]",
            "available_tools": "list[str]",
            "done": "bool",
        }
        self._last_observation: Observation | None = None

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[Observation, dict[str, Any]]:
        task_id = self.task_id
        if options is not None and isinstance(options.get("task_id"), str):
            task_id = options["task_id"]
        observation = self.env.reset(task_id=task_id, seed=seed)
        self._last_observation = observation
        return observation, {
            "task_id": observation.incident_id,
            "available_actions": self.action_space,
        }

    def step(
        self,
        action: Action | str,
    ) -> tuple[Observation, float, bool, bool, dict[str, Any]]:
        result = self.env.step(action)
        self._last_observation = result.observation
        terminal_reason = result.info.get("terminal_reason")
        truncated = result.done and terminal_reason == "step_budget_exhausted"
        terminated = result.done and not truncated
        return result.observation, result.reward, terminated, truncated, result.info

    def render(self) -> str:
        if self._last_observation is None:
            return "SREOpenEnv(uninitialized)"
        return (
            f"incident={self._last_observation.incident_id} "
            f"step={self._last_observation.step} "
            f"remaining={self._last_observation.steps_remaining} "
            f"alert={self._last_observation.alert}"
        )

    def close(self) -> None:
        return None


GymStyleSREEnv = SREOpenEnv
