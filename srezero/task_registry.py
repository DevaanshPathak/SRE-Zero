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
BenchmarkSplit = Literal["train", "dev", "test", "unseen_incident"]
TASK_CONFIG_PACKAGE = "srezero.task_configs"
SPLIT_RESOURCE = "task_splits.json"
PRIMARY_BENCHMARK_SPLITS: tuple[BenchmarkSplit, ...] = ("train", "dev", "test")


@lru_cache(maxsize=1)
def task_config_ids() -> tuple[str, ...]:
    return tuple(resource.name.removesuffix(".json") for resource in _task_config_resources())


@lru_cache(maxsize=1)
def task_splits() -> dict[Difficulty, list[str]]:
    """Return difficulty splits for backwards compatibility."""

    return difficulty_splits()


@lru_cache(maxsize=1)
def difficulty_splits() -> dict[Difficulty, list[str]]:
    resource = files("srezero").joinpath(SPLIT_RESOURCE)
    raw = json.loads(resource.read_text(encoding="utf-8"))
    splits: dict[Difficulty, list[str]] = {
        "easy": list(raw.get("easy", [])),
        "medium": list(raw.get("medium", [])),
        "hard": list(raw.get("hard", [])),
    }
    _validate_difficulty_splits(splits)
    return splits


@lru_cache(maxsize=1)
def benchmark_splits() -> dict[BenchmarkSplit, list[str]]:
    resource = files("srezero").joinpath(SPLIT_RESOURCE)
    raw = json.loads(resource.read_text(encoding="utf-8"))
    splits: dict[BenchmarkSplit, list[str]] = {
        "train": list(raw.get("train", [])),
        "dev": list(raw.get("dev", [])),
        "test": list(raw.get("test", [])),
        "unseen_incident": list(raw.get("unseen_incident", [])),
    }
    _validate_benchmark_splits(splits)
    return splits


def list_task_ids(
    difficulty: Difficulty | None = None,
    split: BenchmarkSplit | None = None,
) -> list[str]:
    if split is not None:
        ordered = list(benchmark_splits()[split])
    else:
        ordered = []
        for split_name in ("easy", "medium", "hard"):
            ordered.extend(difficulty_splits()[split_name])
        ordered.extend(task_id for task_id in task_config_ids() if task_id not in ordered)

    if difficulty is not None:
        allowed = set(difficulty_splits()[difficulty])
        ordered = [task_id for task_id in ordered if task_id in allowed]
    return ordered


def get_task(task_id: str) -> IncidentTask:
    resource = _task_config_resource(task_id)
    if resource is None:
        available = ", ".join(list_task_ids())
        raise KeyError(f"Unknown task_id {task_id!r}. Available tasks: {available}")
    config = load_task_config(resource)
    return build_task_from_config(config)


def task_catalog(
    difficulty: Difficulty | None = None,
    split: BenchmarkSplit | None = None,
) -> list[dict[str, str]]:
    catalog = []
    for task_id in list_task_ids(difficulty=difficulty, split=split):
        task = get_task(task_id)
        catalog.append(
            {
                "task_id": task.task_id,
                "difficulty": task.difficulty,
                "alert": task.alert,
                "benchmark_split": _benchmark_split_for_task(task_id),
                "is_unseen_incident": str(task_id in benchmark_splits()["unseen_incident"]),
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


def _validate_difficulty_splits(splits: dict[Difficulty, list[str]]) -> None:
    configured = set(task_config_ids())
    split_ids = [task_id for task_ids in splits.values() for task_id in task_ids]
    missing = sorted(set(split_ids) - configured)
    if missing:
        raise ValueError(f"Task split references missing config(s): {', '.join(missing)}")

    duplicates = sorted(task_id for task_id in set(split_ids) if split_ids.count(task_id) > 1)
    if duplicates:
        raise ValueError(f"Task split contains duplicate task id(s): {', '.join(duplicates)}")

    omitted = sorted(configured - set(split_ids))
    if omitted:
        raise ValueError(f"Difficulty split omits task id(s): {', '.join(omitted)}")


def _validate_benchmark_splits(splits: dict[BenchmarkSplit, list[str]]) -> None:
    configured = set(task_config_ids())
    primary_split_ids = [
        task_id for split_name in PRIMARY_BENCHMARK_SPLITS for task_id in splits[split_name]
    ]
    missing = sorted(set(primary_split_ids) - configured)
    if missing:
        raise ValueError(f"Benchmark split references missing config(s): {', '.join(missing)}")

    duplicates = sorted(
        task_id for task_id in set(primary_split_ids) if primary_split_ids.count(task_id) > 1
    )
    if duplicates:
        duplicate_text = ", ".join(duplicates)
        raise ValueError(f"Train/dev/test split contains duplicate task id(s): {duplicate_text}")

    omitted = sorted(configured - set(primary_split_ids))
    if omitted:
        raise ValueError(f"Train/dev/test split omits task id(s): {', '.join(omitted)}")

    unseen = set(splits["unseen_incident"])
    unseen_missing = sorted(unseen - configured)
    if unseen_missing:
        raise ValueError(
            f"Unseen incident split references missing config(s): {', '.join(unseen_missing)}"
        )
    unseen_outside_test = sorted(unseen - set(splits["test"]))
    if unseen_outside_test:
        raise ValueError(
            "Unseen incident split must be a subset of test; found "
            f"{', '.join(unseen_outside_test)}"
        )


def _benchmark_split_for_task(task_id: str) -> str:
    for split_name in PRIMARY_BENCHMARK_SPLITS:
        if task_id in benchmark_splits()[split_name]:
            return split_name
    return "unassigned"
