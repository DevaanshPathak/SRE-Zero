"""Cache crash task."""

from srezero.services import base_services
from srezero.tasks.base import CorrectFix, IncidentTask


def build_task() -> IncidentTask:
    services = base_services()
    cache = services["cache"]
    cache.status = "crashed"
    cache.logs = [
        "ERROR process exited signal=SIGKILL component=cache",
        "WARN cache unavailable; falling back to database reads",
        "ERROR healthcheck failed reason=connection_refused",
    ]
    cache.metrics = {"hit_rate": 0.03, "p95_latency_ms": 0, "memory_used_pct": 0}

    return IncidentTask(
        task_id="cache_crash",
        difficulty="easy",
        alert="Users are seeing elevated latency. Cache hit rate has dropped suddenly.",
        root_cause="cache service crashed",
        root_cause_keywords=("cache", "crashed"),
        relevant_evidence=("check_status:cache", "inspect_logs:cache", "inspect_metrics:cache"),
        evidence_descriptions={
            "check_status:cache": "Cache service status is crashed.",
            "inspect_logs:cache": "Cache logs show the process exited and health checks failing.",
            "inspect_metrics:cache": "Cache hit rate collapsed after the service stopped.",
        },
        correct_fix=CorrectFix(
            action_type="restart_service",
            service="cache",
            fix_keywords=("restart", "cache"),
        ),
        services=services,
        expected_action_pattern=(
            "check_status(cache)",
            "inspect_logs(cache)",
            "restart_service(cache)",
            "resolve_incident(cache service crashed, restart cache)",
        ),
        max_steps=8,
    )

