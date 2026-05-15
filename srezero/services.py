"""Simulated service state used by incident tasks."""

from __future__ import annotations

from pydantic import BaseModel, Field

from srezero.schemas import ConfigValue, ServiceName


class Service(BaseModel):
    """In-memory representation of a service in the simulator."""

    name: ServiceName
    status: str
    logs: list[str] = Field(default_factory=list)
    metrics: dict[str, int | float | str] = Field(default_factory=dict)
    config: dict[str, ConfigValue] = Field(default_factory=dict)
    dependencies: list[ServiceName] = Field(default_factory=list)


def base_services() -> dict[ServiceName, Service]:
    """Return healthy baseline services for task fixtures to modify."""

    return {
        "web_server": Service(
            name="web_server",
            status="healthy",
            logs=[
                "INFO request_id=1001 path=/ status=200 latency_ms=42",
                "INFO request_id=1002 path=/checkout status=200 latency_ms=88",
            ],
            metrics={
                "request_rate": 240,
                "error_rate": 0.01,
                "p95_latency_ms": 120,
                "upstream_timeout_rate": 0.0,
            },
            config={"TIMEOUT_MS": 3000, "MAX_WORKERS": 16},
            dependencies=["database", "cache", "message_queue"],
        ),
        "database": Service(
            name="database",
            status="healthy",
            logs=[
                "INFO connection pool initialized size=50",
                "INFO query completed table=orders latency_ms=18",
            ],
            metrics={
                "active_connections": 14,
                "max_connections": 50,
                "connection_wait_ms": 3,
                "query_p95_latency_ms": 35,
            },
            config={"DB_POOL_SIZE": 50, "QUERY_TIMEOUT_MS": 2000},
            dependencies=[],
        ),
        "cache": Service(
            name="cache",
            status="healthy",
            logs=[
                "INFO cache warmed namespace=products keys=4200",
                "INFO eviction cycle completed evicted=12",
            ],
            metrics={"hit_rate": 0.92, "p95_latency_ms": 5, "memory_used_pct": 45},
            config={"TTL_SECONDS": 300, "MAX_MEMORY_MB": 512},
            dependencies=[],
        ),
        "message_queue": Service(
            name="message_queue",
            status="healthy",
            logs=[
                "INFO queue=checkout_jobs consumers=8 backlog=24",
                "INFO publish latency_ms=12 ack_rate=0.99",
            ],
            metrics={
                "queue_depth": 24,
                "oldest_message_age_ms": 1200,
                "publish_error_rate": 0.0,
                "consumer_lag_ms": 250,
                "dead_letter_rate": 0.0,
            },
            config={
                "CONSUMER_CONCURRENCY": 8,
                "MAX_IN_FLIGHT": 500,
                "RETRY_LIMIT": 3,
                "VISIBILITY_TIMEOUT_MS": 30000,
            },
            dependencies=["database"],
        ),
        "load_balancer": Service(
            name="load_balancer",
            status="healthy",
            logs=[
                "INFO backend=web_server healthy=true weight=50",
                "INFO listener=https status=active tls_days_remaining=45",
            ],
            metrics={
                "request_rate": 260,
                "backend_5xx_rate": 0.01,
                "healthy_backends": 2,
                "connection_utilization_pct": 42,
                "p95_latency_ms": 55,
            },
            config={
                "HEALTH_CHECK_PATH": "/healthz",
                "MAX_CONNECTIONS": 2000,
                "STICKY_SESSIONS": False,
                "WEB_WEIGHT_PRIMARY": 50,
            },
            dependencies=["web_server"],
        ),
    }
