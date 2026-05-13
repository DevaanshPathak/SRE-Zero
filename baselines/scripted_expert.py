"""Task-specific scripted expert baseline."""

from __future__ import annotations

from srezero.schemas import Action, Observation


class ScriptedExpertAgent:
    """Approximate upper-bound baseline using documented task-specific policies.

    The policy table intentionally uses known v0.1 task solutions. It does not inspect hidden
    environment fields at runtime, but it is not a fair generalization baseline.
    """

    def __init__(self) -> None:
        self._positions: dict[str, int] = {}

    def reset(self) -> None:
        self._positions = {}

    def act(self, observation: Observation) -> Action:
        policy = POLICIES[observation.incident_id]
        position = self._positions.get(observation.incident_id, 0)
        self._positions[observation.incident_id] = position + 1
        if position >= len(policy):
            return policy[-1]
        return policy[position]


POLICIES: dict[str, list[Action]] = {
    "cache_crash": [
        Action(action_type="check_status", service="cache"),
        Action(action_type="inspect_logs", service="cache"),
        Action(action_type="inspect_metrics", service="cache"),
        Action(action_type="restart_service", service="cache"),
        Action(
            action_type="resolve_incident",
            root_cause="cache service crashed",
            fix="restart cache service",
        ),
    ],
    "db_pool_exhaustion": [
        Action(action_type="inspect_logs", service="web_server"),
        Action(action_type="inspect_metrics", service="database"),
        Action(action_type="update_config", service="database", key="DB_POOL_SIZE", value=100),
        Action(
            action_type="resolve_incident",
            root_cause="database connection pool exhaustion",
            fix="increase database pool size",
        ),
    ],
    "web_timeout_misconfig": [
        Action(action_type="inspect_logs", service="web_server"),
        Action(action_type="inspect_config", service="web_server", key="TIMEOUT_MS"),
        Action(action_type="update_config", service="web_server", key="TIMEOUT_MS", value=5000),
        Action(
            action_type="resolve_incident",
            root_cause="web server timeout configuration too low",
            fix="increase web timeout",
        ),
    ],
    "cache_latency_degradation": [
        Action(action_type="inspect_metrics", service="cache"),
        Action(action_type="inspect_config", service="cache", key="TTL_SECONDS"),
        Action(action_type="update_config", service="cache", key="TTL_SECONDS", value=300),
        Action(
            action_type="resolve_incident",
            root_cause="cache hit rate degraded due to wrong cache TTL config",
            fix="increase cache TTL",
        ),
    ],
    "misleading_web_500_db_rootcause": [
        Action(action_type="inspect_logs", service="web_server"),
        Action(action_type="inspect_metrics", service="database"),
        Action(action_type="inspect_config", service="database", key="DB_POOL_SIZE"),
        Action(action_type="update_config", service="database", key="DB_POOL_SIZE", value=150),
        Action(
            action_type="resolve_incident",
            root_cause="database saturation causing web failures",
            fix="increase database pool size",
        ),
    ],
}

