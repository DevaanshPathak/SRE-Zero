"""Task-specific scripted expert baseline."""

from __future__ import annotations

from srezero.actions import parse_action
from srezero.schemas import Action, Observation
from srezero.task_registry import get_task


class ScriptedExpertAgent:
    """Approximate upper-bound baseline using documented task solution patterns.

    The policy reads each task's `expected_action_pattern` from the deterministic task config.
    This is useful as an upper-bound smoke test, but it is not a fair generalization baseline.
    """

    def __init__(self) -> None:
        self._positions: dict[str, int] = {}

    def reset(self) -> None:
        self._positions = {}

    def act(self, observation: Observation) -> Action:
        task = get_task(observation.incident_id)
        if not task.expected_action_pattern:
            return Action(action_type="escalate", reason="no scripted policy available")

        position = self._positions.get(observation.incident_id, 0)
        self._positions[observation.incident_id] = position + 1
        action_index = min(position, len(task.expected_action_pattern) - 1)
        action_text = task.expected_action_pattern[action_index]
        return parse_action(action_text)
