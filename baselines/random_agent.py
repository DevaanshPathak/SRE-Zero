"""Deterministic random baseline."""

from __future__ import annotations

import random

from srezero.schemas import Action, ActionType, Observation


class RandomAgent:
    """Random action sampler with occasional invalid services."""

    def __init__(self, seed: int | None = None) -> None:
        self.rng = random.Random(seed)

    def reset(self) -> None:
        return None

    def act(self, observation: Observation) -> Action:
        del observation
        action_types: list[ActionType] = [
            "inspect_logs",
            "inspect_metrics",
            "check_status",
            "inspect_config",
            "restart_service",
            "update_config",
            "resolve_incident",
            "escalate",
        ]
        action_type = self.rng.choice(action_types)
        service = self._service()

        if action_type in {"inspect_logs", "inspect_metrics", "check_status", "restart_service"}:
            return Action(action_type=action_type, service=service)
        if action_type == "inspect_config":
            key = self.rng.choice(
                [
                    None,
                    "TIMEOUT_MS",
                    "DB_POOL_SIZE",
                    "TTL_SECONDS",
                    "CONSUMER_CONCURRENCY",
                    "MAX_CONNECTIONS",
                    "UNKNOWN",
                ]
            )
            return Action(action_type=action_type, service=service, key=key)
        if action_type == "update_config":
            service_key = {
                "web_server": "TIMEOUT_MS",
                "database": "DB_POOL_SIZE",
                "cache": "TTL_SECONDS",
                "message_queue": "CONSUMER_CONCURRENCY",
                "load_balancer": "MAX_CONNECTIONS",
            }.get(service, "UNKNOWN")
            return Action(
                action_type=action_type,
                service=service,
                key=service_key,
                value=self.rng.choice([10, 100, 300, 5000]),
            )
        if action_type == "resolve_incident":
            return Action(
                action_type="resolve_incident",
                root_cause=self.rng.choice(
                    [
                        "cache crashed",
                        "database pool exhaustion",
                        "web timeout misconfiguration",
                        "message queue backlog",
                        "load balancer misconfiguration",
                        "unknown root cause",
                    ]
                ),
                fix=self.rng.choice(
                    [
                        "restart cache",
                        "increase database pool",
                        "increase web timeout",
                        "increase queue consumers",
                        "update load balancer config",
                        "no fix",
                    ]
                ),
            )
        return Action(action_type="escalate", reason="random baseline escalation")

    def _service(self) -> str:
        return self.rng.choice(
            ["web_server", "database", "cache", "message_queue", "load_balancer", "queue"]
        )
