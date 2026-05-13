"""Evaluation runner for SRE-Zero Mini."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Protocol

from rich.console import Console
from rich.table import Table

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from baselines import RandomAgent, ScriptedExpertAgent  # noqa: E402
from srezero.env import SREEnv  # noqa: E402
from srezero.metrics import aggregate_episode_records  # noqa: E402
from srezero.schemas import Action, Observation  # noqa: E402
from srezero.task_registry import list_task_ids  # noqa: E402


class Agent(Protocol):
    def reset(self) -> None: ...

    def act(self, observation: Observation) -> Action | str: ...


def build_agent(agent_name: str, seed: int) -> Agent:
    if agent_name == "random":
        return RandomAgent(seed=seed)
    if agent_name == "scripted":
        return ScriptedExpertAgent()
    raise ValueError(f"Unknown agent {agent_name!r}")


def run_episode(task_id: str, agent: Agent, seed: int) -> dict[str, object]:
    env = SREEnv()
    observation = env.reset(task_id=task_id, seed=seed)
    agent.reset()
    trajectory: list[dict[str, object]] = []

    while not env.is_done():
        action = agent.act(observation)
        result = env.step(action)
        trajectory.append(
            {
                "step": result.observation.step,
                "action": result.observation.last_action,
                "reward": result.reward,
                "summary": result.observation.last_result.summary,
            }
        )
        observation = result.observation

    final_info = result.info if trajectory else {}
    return {
        "task_id": task_id,
        "metrics": env.metrics.model_dump(),
        "evidence_coverage": final_info.get("evidence_coverage", 0.0),
        "trajectory": trajectory,
    }


def evaluate(agent_name: str, episodes: int, seed: int) -> dict[str, object]:
    records: list[dict[str, object]] = []
    by_task: dict[str, dict[str, float]] = {}

    for task_index, task_id in enumerate(list_task_ids()):
        task_records = []
        for episode_index in range(episodes):
            episode_seed = seed + task_index * 10_000 + episode_index
            agent = build_agent(agent_name, episode_seed)
            record = run_episode(task_id=task_id, agent=agent, seed=episode_seed)
            records.append(record)
            task_records.append(record)
        by_task[task_id] = aggregate_episode_records(task_records)

    return {
        "agent": agent_name,
        "episodes_per_task": episodes,
        "seed": seed,
        "overall": aggregate_episode_records(records),
        "by_task": by_task,
        "records": records,
    }


def print_results(results: dict[str, object]) -> None:
    console = Console()
    table = Table(title=f"SRE-Zero Mini Evaluation: {results['agent']}")
    table.add_column("Task")
    table.add_column("Success", justify="right")
    table.add_column("Reward", justify="right")
    table.add_column("Steps", justify="right")
    table.add_column("Invalid", justify="right")
    table.add_column("Evidence", justify="right")

    by_task = results["by_task"]
    assert isinstance(by_task, dict)
    for task_id, metrics in by_task.items():
        table.add_row(
            task_id,
            f"{metrics['success_rate']:.2f}",
            f"{metrics['mean_reward']:.3f}",
            f"{metrics['mean_steps']:.2f}",
            f"{metrics['invalid_action_rate']:.2f}",
            f"{metrics['evidence_coverage']:.2f}",
        )

    overall = results["overall"]
    assert isinstance(overall, dict)
    table.add_section()
    table.add_row(
        "overall",
        f"{overall['success_rate']:.2f}",
        f"{overall['mean_reward']:.3f}",
        f"{overall['mean_steps']:.2f}",
        f"{overall['invalid_action_rate']:.2f}",
        f"{overall['evidence_coverage']:.2f}",
    )
    console.print(table)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run SRE-Zero Mini evaluations.")
    parser.add_argument("--agent", choices=["random", "scripted"], default="random")
    parser.add_argument("--episodes", type=int, default=20)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output", type=Path, default=Path("eval/example_results.json"))
    args = parser.parse_args()

    results = evaluate(agent_name=args.agent, episodes=args.episodes, seed=args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print_results(results)
    print(f"Wrote results to {args.output}")


if __name__ == "__main__":
    main()

