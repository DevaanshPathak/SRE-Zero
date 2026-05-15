"""Episode and aggregate metrics."""

from __future__ import annotations

from statistics import mean
from typing import Any

from pydantic import BaseModel


class EpisodeMetrics(BaseModel):
    total_steps: int = 0
    invalid_actions: int = 0
    repeated_actions: int = 0
    evidence_actions: int = 0
    remediation_actions: int = 0
    wrong_remediations: int = 0
    distractor_failures: int = 0
    premature_resolutions: int = 0
    success: bool = False
    final_reward: float = 0.0


def aggregate_episode_records(records: list[dict[str, Any]]) -> dict[str, float]:
    """Aggregate evaluation records into benchmark metrics."""

    if not records:
        return {
            "success_rate": 0.0,
            "mean_reward": 0.0,
            "mean_steps": 0.0,
            "invalid_action_rate": 0.0,
            "evidence_coverage": 0.0,
            "wrong_remediation_rate": 0.0,
            "distractor_failure_rate": 0.0,
            "premature_resolution_rate": 0.0,
        }

    total_steps = sum(record["metrics"]["total_steps"] for record in records)
    total_invalid = sum(record["metrics"]["invalid_actions"] for record in records)
    total_remediations = sum(record["metrics"]["remediation_actions"] for record in records)
    total_wrong_remediations = sum(record["metrics"]["wrong_remediations"] for record in records)
    total_distractor_failures = sum(
        record["metrics"].get("distractor_failures", 0) for record in records
    )

    return {
        "success_rate": mean(1.0 if record["metrics"]["success"] else 0.0 for record in records),
        "mean_reward": mean(record["metrics"]["final_reward"] for record in records),
        "mean_steps": mean(record["metrics"]["total_steps"] for record in records),
        "invalid_action_rate": total_invalid / max(1, total_steps),
        "evidence_coverage": mean(record["evidence_coverage"] for record in records),
        "wrong_remediation_rate": total_wrong_remediations / max(1, total_remediations),
        "distractor_failure_rate": total_distractor_failures / max(1, total_remediations),
        "premature_resolution_rate": mean(
            1.0 if record["metrics"]["premature_resolutions"] > 0 else 0.0
            for record in records
        ),
    }
