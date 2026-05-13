"""Task registry for SRE-Zero Mini."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from importlib.resources.abc import Traversable
from typing import Literal

from srezero.tasks import IncidentTask
from srezero.tasks.config_loader import build_task_from_config, load_task_config

Difficulty = Literal["easy", "medium", "hard"]
TASK_CONFIG_PACKAGE = "srezero.task_configs"
SPLIT_RESOURCE = "task_splits.json"


@lru_cache(maxsize=1)
def task_config_ids() -> tuple[str, ...]:
    return tuple(resource.name.removesuffix(".json") for resource in _task_config_resources())


@lru_cache(maxsize=1)
def task_splits() -> dict[Difficulty, list[str]]:
    resource = files("srezero").joinpath(SPLIT_RESOURCE)
    raw = json.loads(resource.read_text(encoding="utf-8"))
    splits: dict[Difficulty, list[str]] = {
        "easy": list(raw.get("easy", [])),
        "medium": list(raw.get("medium", [])),
        "hard": list(raw.get("hard", [])),
    }
    _validate_splits(splits)
    return splits


def list_task_ids(difficulty: Difficulty | None = None) -> list[str]:
    if difficulty is not None:
        return list(task_splits()[difficulty])

    ordered: list[str] = []
    for split_name in ("easy", "medium", "hard"):
        ordered.extend(task_splits()[split_name])
    ordered.extend(task_id for task_id in task_config_ids() if task_id not in ordered)
    return ordered


def get_task(task_id: str) -> IncidentTask:
    resource = _task_config_resource(task_id)
    if resource is None:
        available = ", ".join(list_task_ids())
        raise KeyError(f"Unknown task_id {task_id!r}. Available tasks: {available}")
    config = load_task_config(resource)
    return build_task_from_config(config)


def task_catalog(difficulty: Difficulty | None = None) -> list[dict[str, str]]:
    catalog = []
    for task_id in list_task_ids(difficulty=difficulty):
        task = get_task(task_id)
        catalog.append(
            {
                "task_id": task.task_id,
                "difficulty": task.difficulty,
                "alert": task.alert,
            }
        )
    return catalog


def _task_config_resources() -> list[Traversable]:
    return sorted(
        (
            resource
            for resource in files(TASK_CONFIG_PACKAGE).iterdir()
            if resource.is_file() and resource.name.endswith(".json")
        ),
        key=lambda resource: resource.name,
    )


def _task_config_resource(task_id: str) -> Traversable | None:
    resource = files(TASK_CONFIG_PACKAGE).joinpath(f"{task_id}.json")
    if not resource.is_file():
        return None
    return resource


def _validate_splits(splits: dict[Difficulty, list[str]]) -> None:
    configured = set(task_config_ids())
    split_ids = [task_id for task_ids in splits.values() for task_id in task_ids]
    missing = sorted(set(split_ids) - configured)
    if missing:
        raise ValueError(f"Task split references missing config(s): {', '.join(missing)}")

    duplicates = sorted(task_id for task_id in set(split_ids) if split_ids.count(task_id) > 1)
    if duplicates:
        raise ValueError(f"Task split contains duplicate task id(s): {', '.join(duplicates)}")

