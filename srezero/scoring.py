"""Standard benchmark scoring for SRE-Zero."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, Field

STANDARD_MARK_WEIGHTS = {
    "success": 40.0,
    "reward": 25.0,
    "evidence": 20.0,
    "efficiency": 10.0,
    "validity": 5.0,
}

PAPER_METRIC_KEYS = (
    "success_rate",
    "mean_reward",
    "mean_steps",
    "invalid_action_rate",
    "evidence_coverage",
    "wrong_remediation_rate",
    "distractor_failure_rate",
    "premature_resolution_rate",
    "root_cause_identification_rate",
    "fix_identification_rate",
    "correct_service_remediation_rate",
    "correct_remediation_rate",
    "remediation_precision",
)

ZERO_METRICS = {
    "success_rate": 0.0,
    "mean_reward": 0.0,
    "mean_steps": 0.0,
    "invalid_action_rate": 0.0,
    "evidence_coverage": 0.0,
    "wrong_remediation_rate": 0.0,
    "distractor_failure_rate": 0.0,
    "premature_resolution_rate": 0.0,
    "root_cause_identification_rate": 0.0,
    "fix_identification_rate": 0.0,
    "correct_service_remediation_rate": 0.0,
    "correct_remediation_rate": 0.0,
    "remediation_precision": 0.0,
}


class StandardScore(BaseModel):
    """Paper-facing normalized score and component marks."""

    score: float
    max_score: float = 100.0
    components: dict[str, float] = Field(default_factory=dict)
    metrics: dict[str, float] = Field(default_factory=dict)
    target_steps: float = 8.0


def score_metrics(
    overall: Mapping[str, object],
    *,
    target_steps: float = 8.0,
) -> StandardScore:
    """Convert aggregate metrics into the standard 100-point marks score."""

    success_rate = metric(overall, "success_rate")
    mean_reward = metric(overall, "mean_reward")
    evidence_coverage = metric(overall, "evidence_coverage")
    invalid_action_rate = metric(overall, "invalid_action_rate")
    mean_steps = metric(overall, "mean_steps")
    efficiency_rate = success_rate * max(
        0.0,
        1.0 - max(0.0, mean_steps - 1.0) / max(1.0, target_steps - 1.0),
    )
    validity_rate = max(0.0, 1.0 - invalid_action_rate)
    components = {
        "success": success_rate * STANDARD_MARK_WEIGHTS["success"],
        "reward": mean_reward * STANDARD_MARK_WEIGHTS["reward"],
        "evidence": evidence_coverage * STANDARD_MARK_WEIGHTS["evidence"],
        "efficiency": efficiency_rate * STANDARD_MARK_WEIGHTS["efficiency"],
        "validity": validity_rate * STANDARD_MARK_WEIGHTS["validity"],
    }
    metrics = {key: metric(overall, key) for key in PAPER_METRIC_KEYS}
    return StandardScore(
        score=round(sum(components.values()), 3),
        components={key: round(value, 3) for key, value in components.items()},
        metrics=metrics,
        target_steps=target_steps,
    )


def metric(overall: Mapping[str, object], key: str) -> float:
    value = overall.get(key, 0.0)
    if isinstance(value, int | float):
        return float(value)
    return 0.0
