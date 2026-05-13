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
            dependencies=["database", "cache"],
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
    }

