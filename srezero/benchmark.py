"""Public benchmark API for SRE-Zero."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from srezero.gym_env import SREOpenEnv
from srezero.scoring import PAPER_METRIC_KEYS, STANDARD_MARK_WEIGHTS, StandardScore, score_metrics
from srezero.task_registry import (
    BenchmarkSplit,
    Difficulty,
    benchmark_splits,
    list_task_ids,
    task_catalog,
)

BENCHMARK_VERSION = "v0.6"
DEFAULT_SEED = 0
DEFAULT_TARGET_STEPS = 8.0


class BenchmarkSpec(BaseModel):
    """Static metadata for a SRE-Zero benchmark run."""

    name: str = "SRE-Zero"
    version: str = BENCHMARK_VERSION
    task_count: int
    train_count: int
    dev_count: int
    test_count: int
    unseen_incident_count: int
    metrics: tuple[str, ...] = PAPER_METRIC_KEYS
    scoring_weights: dict[str, float] = Field(default_factory=lambda: dict(STANDARD_MARK_WEIGHTS))


def benchmark_spec() -> BenchmarkSpec:
    splits = benchmark_splits()
    return BenchmarkSpec(
        task_count=len(list_task_ids()),
        train_count=len(splits["train"]),
        dev_count=len(splits["dev"]),
        test_count=len(splits["test"]),
        unseen_incident_count=len(splits["unseen_incident"]),
    )


def benchmark_task_ids(
    *,
    split: BenchmarkSplit | None = None,
    difficulty: Difficulty | None = None,
) -> list[str]:
    """Return canonical benchmark task ids, optionally filtered by split/difficulty."""

    return list_task_ids(split=split, difficulty=difficulty)


def benchmark_catalog(
    *,
    split: BenchmarkSplit | None = None,
    difficulty: Difficulty | None = None,
) -> list[dict[str, str]]:
    """Return public task metadata without hidden solutions."""

    return task_catalog(split=split, difficulty=difficulty)


def make_env(task_id: str | None = None) -> SREOpenEnv:
    """Create the final Gym-style benchmark environment wrapper."""

    return SREOpenEnv(task_id=task_id)


def standard_score(overall_metrics: dict[str, Any], *, target_steps: float = 8.0) -> StandardScore:
    """Score aggregate metrics with the public 100-point formula."""

    return score_metrics(overall_metrics, target_steps=target_steps)
