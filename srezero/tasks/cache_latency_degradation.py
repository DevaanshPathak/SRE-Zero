"""Cache latency degradation task."""

from srezero.services import base_services
from srezero.tasks.base import CorrectFix, IncidentTask


def build_task() -> IncidentTask:
    services = base_services()
    cache = services["cache"]
    web = services["web_server"]

    web.logs = [
        "INFO product page requests shifted to database fallback",
        "WARN product page p95 latency elevated latency_ms=720",
    ]
    web.metrics["p95_latency_ms"] = 740

    cache.logs = [
        "INFO cache keys expiring rapidly namespace=products",
        "WARN frequent miss burst observed namespace=products",
    ]
    cache.metrics = {"hit_rate": 0.31, "p95_latency_ms": 18, "memory_used_pct": 28}
    cache.config["TTL_SECONDS"] = 5

    return IncidentTask(
        task_id="cache_latency_degradation",
        difficulty="medium",
        alert="Application latency has increased across product pages.",
        root_cause="cache hit rate degraded due to wrong cache TTL config",
        root_cause_keywords=("cache", "ttl", "hit rate"),
        relevant_evidence=("inspect_metrics:cache", "inspect_config:cache:TTL_SECONDS"),
        evidence_descriptions={
            "inspect_metrics:cache": (
                "Cache metrics show a low hit rate during the latency increase."
            ),
            "inspect_config:cache:TTL_SECONDS": (
                "Cache TTL_SECONDS is too low, causing frequent expirations."
            ),
        },
        correct_fix=CorrectFix(
            action_type="update_config",
            service="cache",
            key="TTL_SECONDS",
            min_numeric_value=120,
            fix_keywords=("cache", "ttl"),
        ),
        services=services,
        expected_action_pattern=(
            "inspect_metrics(cache)",
            "inspect_config(cache, TTL_SECONDS)",
            "update_config(cache, TTL_SECONDS, 300)",
            "resolve_incident(cache TTL config too low, increase cache TTL)",
        ),
        max_steps=8,
    )
