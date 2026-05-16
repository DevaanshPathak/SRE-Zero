"""Evaluation runner for SRE-Zero Mini."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path

from rich.console import Console
from rich.table import Table

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from baselines import AGENT_CHOICES, Agent, build_agent  # noqa: E402
from srezero.env import SREEnv  # noqa: E402
from srezero.metrics import aggregate_episode_records  # noqa: E402
from srezero.scoring import score_metrics  # noqa: E402
from srezero.task_registry import BenchmarkSplit, Difficulty, list_task_ids  # noqa: E402

ProgressCallback = Callable[[str, int, int, int, int, str], None]


def run_episode(task_id: str, agent: Agent, seed: int) -> dict[str, object]:
    env = SREEnv()
    observation = env.reset(task_id=task_id, seed=seed)
    agent.reset()
    trajectory: list[dict[str, object]] = []
    agent_error: str | None = None
    final_info: dict[str, object] = {}

    while not env.is_done():
        try:
            action = agent.act(observation)
        except Exception as exc:  # noqa: BLE001
            agent_error = f"{type(exc).__name__}: {exc}"
            break
        result = env.step(action)
        final_info = result.info
        trajectory.append(
            {
                "step": result.observation.step,
                "action": result.observation.last_action,
                "reward": result.reward,
                "summary": result.observation.last_result.summary,
            }
        )
        observation = result.observation

    record: dict[str, object] = {
        "task_id": task_id,
        "metrics": env.metrics.model_dump(),
        "evidence_coverage": final_info.get("evidence_coverage", 0.0),
        "trajectory": trajectory,
    }
    if agent_error is not None:
        record["agent_error"] = agent_error
    return record


def evaluate(
    agent_name: str,
    episodes: int,
    seed: int,
    *,
    model_override: str | None = None,
    base_url_override: str | None = None,
    difficulty: Difficulty | None = None,
    split: BenchmarkSplit | None = None,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, object]:
    records: list[dict[str, object]] = []
    by_task: dict[str, dict[str, float]] = {}
    task_ids = list_task_ids(difficulty=difficulty, split=split)

    for task_index, task_id in enumerate(task_ids):
        task_records = []
        for episode_index in range(episodes):
            if progress_callback is not None:
                progress_callback(
                    task_id,
                    task_index + 1,
                    len(task_ids),
                    episode_index + 1,
                    episodes,
                    "start",
                )
            episode_seed = seed + task_index * 10_000 + episode_index
            agent = build_agent(
                agent_name,
                episode_seed,
                model_override=model_override,
                base_url_override=base_url_override,
            )
            record = run_episode(task_id=task_id, agent=agent, seed=episode_seed)
            records.append(record)
            task_records.append(record)
            if progress_callback is not None:
                progress_callback(
                    task_id,
                    task_index + 1,
                    len(task_ids),
                    episode_index + 1,
                    episodes,
                    "finish",
                )
        by_task[task_id] = aggregate_episode_records(task_records)

    overall = aggregate_episode_records(records)
    return {
        "agent": agent_name,
        "episodes_per_task": episodes,
        "seed": seed,
        "model_override": model_override,
        "base_url_override": base_url_override,
        "difficulty": difficulty,
        "split": split,
        "overall": overall,
        "standard_score": score_metrics(overall).model_dump(),
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
    parser.add_argument("--agent", choices=AGENT_CHOICES, default="random")
    parser.add_argument("--episodes", type=int, default=20)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--model", default=None, help="Override the .env model for this run.")
    parser.add_argument("--base-url", default=None, help="Override the .env base URL for this run.")
    parser.add_argument("--difficulty", choices=["easy", "medium", "hard"], default=None)
    parser.add_argument(
        "--split",
        choices=["train", "dev", "test", "unseen_incident"],
        default=None,
        help="Optional benchmark split. Can be combined with --difficulty.",
    )
    parser.add_argument("--output", type=Path, default=Path("notes/runs/eval_results.json"))
    args = parser.parse_args()
    output_path = output_file_path(args.output, default_name="eval_results.json")

    results = evaluate(
        agent_name=args.agent,
        episodes=args.episodes,
        seed=args.seed,
        model_override=args.model,
        base_url_override=args.base_url,
        difficulty=args.difficulty,
        split=args.split,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print_results(results)
    print(f"Wrote results to {output_path}")


def repo_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return ROOT / path


def output_file_path(path: Path, *, default_name: str) -> Path:
    resolved = repo_path(path)
    if resolved.exists() and resolved.is_dir():
        return resolved / default_name
    if resolved.suffix:
        return resolved
    return resolved / default_name


if __name__ == "__main__":
    main()
