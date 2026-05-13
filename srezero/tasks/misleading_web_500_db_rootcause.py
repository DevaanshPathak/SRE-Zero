"""Misleading web 500s with database root cause task."""

from srezero.services import base_services
from srezero.tasks.base import CorrectFix, IncidentTask


def build_task() -> IncidentTask:
    services = base_services()
    web = services["web_server"]
    database = services["database"]

    web.logs = [
        "ERROR request_id=5101 status=500 handler=/api/cart exception=InternalServerError",
        "ERROR request_id=5102 status=500 handler=/api/cart exception=InternalServerError",
        "WARN downstream database call failed reason=connection_wait_timeout",
    ]
    web.metrics = {
        "request_rate": 260,
        "error_rate": 0.19,
        "p95_latency_ms": 1300,
        "upstream_timeout_rate": 0.11,
    }

    database.logs = [
        "WARN saturation detected active_connections=98 max_connections=100",
        "WARN connection queue length=61",
        "INFO cpu within normal range pct=55",
    ]
    database.metrics = {
        "active_connections": 98,
        "max_connections": 100,
        "connection_wait_ms": 1400,
        "query_p95_latency_ms": 70,
    }
    database.config["DB_POOL_SIZE"] = 100

    return IncidentTask(
        task_id="misleading_web_500_db_rootcause",
        difficulty="hard",
        alert="Web server is producing frequent 500 errors.",
        root_cause="database saturation causing web failures",
        root_cause_keywords=("database", "saturation", "web"),
        relevant_evidence=("inspect_logs:web_server", "inspect_metrics:database"),
        evidence_descriptions={
            "inspect_logs:web_server": (
                "Web logs are severe but point to downstream database waits."
            ),
            "inspect_metrics:database": (
                "Database metrics show connection saturation at the root cause."
            ),
        },
        correct_fix=CorrectFix(
            action_type="update_config",
            service="database",
            key="DB_POOL_SIZE",
            min_numeric_value=120,
            fix_keywords=("database", "pool"),
        ),
        services=services,
        expected_action_pattern=(
            "inspect_logs(web_server)",
            "inspect_metrics(database)",
            "update_config(database, DB_POOL_SIZE, 150)",
            (
                "resolve_incident(database saturation causing web failures, "
                "increase database pool size)"
            ),
        ),
        distractors=(
            "Restarting web_server may look plausible but does not address database saturation.",
        ),
        max_steps=8,
    )
