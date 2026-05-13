"""Reward bookkeeping for SRE-Zero Mini."""

from __future__ import annotations

from pydantic import BaseModel, Field

COMPONENT_MAX = {
    "evidence": 0.20,
    "root_cause": 0.25,
    "remediation": 0.25,
    "resolution": 0.20,
    "efficiency": 0.10,
}

PENALTY_VALUES = {
    "invalid_action": -0.05,
    "repeated_invalid_action": -0.10,
    "wrong_remediation": -0.15,
    "premature_resolution": -0.20,
    "restart_unrelated_service": -0.10,
    "repeated_useless_action": -0.05,
}


class RewardBreakdown(BaseModel):
    components: dict[str, float] = Field(default_factory=dict)
    penalties: dict[str, float] = Field(default_factory=dict)
    raw_total: float
    total: float


class RewardTracker:
    """Mutable reward state for one episode."""

    def __init__(self, total_evidence: int) -> None:
        self.total_evidence = max(total_evidence, 1)
        self.components = {name: 0.0 for name in COMPONENT_MAX}
        self.penalties = {name: 0.0 for name in PENALTY_VALUES}

    def mark_evidence(self, evidence_found: int) -> None:
        coverage = min(1.0, evidence_found / self.total_evidence)
        self.components["evidence"] = COMPONENT_MAX["evidence"] * coverage

    def mark_root_cause(self) -> None:
        self.components["root_cause"] = COMPONENT_MAX["root_cause"]

    def mark_remediation(self) -> None:
        self.components["remediation"] = COMPONENT_MAX["remediation"]

    def mark_resolution(self) -> None:
        self.components["resolution"] = COMPONENT_MAX["resolution"]

    def mark_efficiency(self, steps_used: int, max_steps: int) -> None:
        if max_steps <= 0:
            return
        remaining_fraction = max(0.0, (max_steps - steps_used) / max_steps)
        self.components["efficiency"] = COMPONENT_MAX["efficiency"] * remaining_fraction

    def add_penalty(self, penalty_name: str) -> None:
        if penalty_name not in PENALTY_VALUES:
            raise KeyError(f"Unknown penalty {penalty_name!r}")
        self.penalties[penalty_name] += PENALTY_VALUES[penalty_name]

    def raw_score(self) -> float:
        return sum(self.components.values()) + sum(self.penalties.values())

    def episode_score(self) -> float:
        return max(0.0, min(1.0, self.raw_score()))

    def snapshot(self) -> RewardBreakdown:
        return RewardBreakdown(
            components=dict(self.components),
            penalties=dict(self.penalties),
            raw_total=self.raw_score(),
            total=self.episode_score(),
        )

