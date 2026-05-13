"""Database connection pool exhaustion task."""

from srezero.services import base_services
from srezero.tasks.base import CorrectFix, IncidentTask


def build_task() -> IncidentTask:
    services = base_services()
    web = services["web_server"]
    database = services["database"]

    web.logs = [
        "ERROR request_id=2101 path=/checkout status=500 error=database_connection_timeout",
        "WARN checkout dependency database connection wait exceeded 900ms",
        "ERROR request_id=2104 path=/checkout status=500 error=pool_timeout",
    ]
    web.metrics["error_rate"] = 0.12
    web.metrics["p95_latency_ms"] = 980

    database.logs = [
        "WARN connection pool waiters=42 pool_size=50",
        "WARN connection acquisition timeout after_ms=1000",
        "INFO slow query sample table=orders latency_ms=84",
    ]
    database.metrics = {
        "active_connections": 49,
        "max_connections": 50,
        "connection_wait_ms": 920,
        "query_p95_latency_ms": 82,
    }
    database.config["DB_POOL_SIZE"] = 50

    return IncidentTask(
        task_id="db_pool_exhaustion",
        difficulty="medium",
        alert="Checkout is returning intermittent 500 errors.",
        root_cause="database connection pool exhaustion",
        root_cause_keywords=("database", "pool", "exhaustion"),
        relevant_evidence=("inspect_logs:web_server", "inspect_metrics:database"),
        evidence_descriptions={
            "inspect_logs:web_server": (
                "Web logs show checkout 500s caused by database pool timeouts."
            ),
            "inspect_metrics:database": (
                "Database metrics show active connections near the configured max."
            ),
        },
        correct_fix=CorrectFix(
            action_type="update_config",
            service="database",
            key="DB_POOL_SIZE",
            min_numeric_value=80,
            fix_keywords=("database", "pool"),
        ),
        services=services,
        expected_action_pattern=(
            "inspect_logs(web_server)",
            "inspect_metrics(database)",
            "update_config(database, DB_POOL_SIZE, 100)",
            "resolve_incident(database connection pool exhaustion, increase database pool size)",
        ),
        max_steps=8,
    )
