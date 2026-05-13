"""Task registry for SRE-Zero Mini."""

from __future__ import annotations

from collections.abc import Callable

from srezero.tasks import (
    IncidentTask,
    cache_crash,
    cache_latency_degradation,
    db_pool_exhaustion,
    misleading_web_500_db_rootcause,
    web_timeout_misconfig,
)

TaskFactory = Callable[[], IncidentTask]

TASK_FACTORIES: dict[str, TaskFactory] = {
    "cache_crash": cache_crash.build_task,
    "db_pool_exhaustion": db_pool_exhaustion.build_task,
    "web_timeout_misconfig": web_timeout_misconfig.build_task,
    "cache_latency_degradation": cache_latency_degradation.build_task,
    "misleading_web_500_db_rootcause": misleading_web_500_db_rootcause.build_task,
}


def list_task_ids() -> list[str]:
    return list(TASK_FACTORIES)


def get_task(task_id: str) -> IncidentTask:
    try:
        return TASK_FACTORIES[task_id]()
    except KeyError as exc:
        available = ", ".join(list_task_ids())
        raise KeyError(f"Unknown task_id {task_id!r}. Available tasks: {available}") from exc


def task_catalog() -> list[dict[str, str]]:
    catalog = []
    for task_id in list_task_ids():
        task = get_task(task_id)
        catalog.append(
            {
                "task_id": task.task_id,
                "difficulty": task.difficulty,
                "alert": task.alert,
            }
        )
    return catalog

