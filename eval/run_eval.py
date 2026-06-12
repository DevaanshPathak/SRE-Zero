"""Evaluation runner for SRE-Zero Mini."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

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
        "seed": seed,
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
    task_ids_override: list[str] | None = None,
    progress_callback: ProgressCallback | None = None,
    existing_records: list[dict[str, object]] | None = None,
    checkpoint_path: Path | None = None,
    checkpoint_extra: dict[str, object] | None = None,
    pause_file: Path | None = None,
) -> dict[str, object]:
    records: list[dict[str, object]] = list(existing_records or [])
    completed = {
        episode_key
        for record in records
        if (episode_key := _episode_key(record)) is not None
    }
    task_ids = resolve_task_ids(
        difficulty=difficulty,
        split=split,
        task_ids=task_ids_override,
        task_range=None,
    )
    paused = False

    for task_index, task_id in enumerate(task_ids):
        for episode_index in range(episodes):
            episode_seed = seed + task_index * 10_000 + episode_index
            episode_key = (task_id, episode_seed)
            if episode_key in completed:
                if progress_callback is not None:
                    progress_callback(
                        task_id,
                        task_index + 1,
                        len(task_ids),
                        episode_index + 1,
                        episodes,
                        "finish",
                    )
                continue
            if pause_file is not None and pause_file.exists():
                paused = True
                result = _evaluation_result(
                    agent_name=agent_name,
                    episodes=episodes,
                    seed=seed,
                    model_override=model_override,
                    base_url_override=base_url_override,
                    difficulty=difficulty,
                    split=split,
                    selected_task_ids=task_ids_override,
                    task_ids=task_ids,
                    records=records,
                    paused=paused,
                    pause_file=pause_file,
                    checkpoint_extra=checkpoint_extra,
                )
                _write_checkpoint(checkpoint_path, result)
                return result
            if progress_callback is not None:
                progress_callback(
                    task_id,
                    task_index + 1,
                    len(task_ids),
                    episode_index + 1,
                    episodes,
                    "start",
                )
            agent = build_agent(
                agent_name,
                episode_seed,
                model_override=model_override,
                base_url_override=base_url_override,
            )
            record = run_episode(task_id=task_id, agent=agent, seed=episode_seed)
            records.append(record)
            completed.add(episode_key)
            if progress_callback is not None:
                progress_callback(
                    task_id,
                    task_index + 1,
                    len(task_ids),
                    episode_index + 1,
                    episodes,
                    "finish",
                )
            result = _evaluation_result(
                agent_name=agent_name,
                episodes=episodes,
                seed=seed,
                model_override=model_override,
                base_url_override=base_url_override,
                difficulty=difficulty,
                split=split,
                selected_task_ids=task_ids_override,
                task_ids=task_ids,
                records=records,
                paused=paused,
                pause_file=pause_file,
                checkpoint_extra=checkpoint_extra,
            )
            _write_checkpoint(checkpoint_path, result)

    return _evaluation_result(
        agent_name=agent_name,
        episodes=episodes,
        seed=seed,
        model_override=model_override,
        base_url_override=base_url_override,
        difficulty=difficulty,
        split=split,
        selected_task_ids=task_ids_override,
        task_ids=task_ids,
        records=records,
        paused=paused,
        pause_file=pause_file,
        checkpoint_extra=checkpoint_extra,
    )


def _episode_key(record: dict[str, object]) -> tuple[str, int] | None:
    task_id = record.get("task_id")
    seed = record.get("seed")
    if not isinstance(task_id, str) or not isinstance(seed, int):
        return None
    return (task_id, seed)


def _evaluation_result(
    *,
    agent_name: str,
    episodes: int,
    seed: int,
    model_override: str | None,
    base_url_override: str | None,
    difficulty: Difficulty | None,
    split: BenchmarkSplit | None,
    selected_task_ids: list[str] | None,
    task_ids: list[str],
    records: list[dict[str, object]],
    paused: bool,
    pause_file: Path | None,
    checkpoint_extra: dict[str, object] | None,
) -> dict[str, object]:
    all_task_ids = list_task_ids(difficulty=difficulty, split=split)
    by_task: dict[str, dict[str, float]] = {}
    for task_id in all_task_ids:
        task_records = [record for record in records if record.get("task_id") == task_id]
        if task_records:
            by_task[task_id] = aggregate_episode_records(cast(list[dict[str, Any]], task_records))

    overall = aggregate_episode_records(cast(list[dict[str, Any]], records))
    filtered_task_ids = task_ids if selected_task_ids is not None else None
    expected_task_episodes = len(all_task_ids) * episodes
    result: dict[str, object] = {
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
        "task_ids": all_task_ids,
        "filtered_task_ids": filtered_task_ids,
        "expected_task_episodes": expected_task_episodes,
        "completed_task_episodes": len(records),
        "complete": len(records) >= expected_task_episodes and not paused,
        "paused": paused,
    }
    if pause_file is not None:
        result["pause_file"] = str(pause_file)
    if checkpoint_extra:
        result.update(checkpoint_extra)
    return result


def resolve_task_ids(
    *,
    difficulty: Difficulty | None,
    split: BenchmarkSplit | None,
    task_ids: list[str] | None,
    task_range: str | None,
) -> list[str]:
    base_task_ids = list_task_ids(difficulty=difficulty, split=split)
    selected = base_task_ids
    if task_ids:
        requested = list(dict.fromkeys(task_ids))
        unknown = [task_id for task_id in requested if task_id not in base_task_ids]
        if unknown:
            available = ", ".join(base_task_ids)
            raise ValueError(
                "Task id(s) not available for the selected filters: "
                f"{', '.join(unknown)}. Available: {available}"
            )
        selected = requested
    if task_range:
        selected = apply_task_range(selected, task_range)
    if not selected:
        raise ValueError("Task selection is empty.")
    return selected


def apply_task_range(task_ids: list[str], task_range: str) -> list[str]:
    raw = task_range.strip()
    if not raw:
        return task_ids
    if "-" in raw:
        start_text, end_text = raw.split("-", 1)
        start = int(start_text.strip())
        end = int(end_text.strip())
    else:
        start = int(raw)
        end = start
    if start < 1 or end < start or end > len(task_ids):
        raise ValueError(
            f"Task range must be within 1-{len(task_ids)} and start <= end; got {task_range!r}."
        )
    return task_ids[start - 1 : end]


def _write_checkpoint(checkpoint_path: Path | None, result: dict[str, object]) -> None:
    if checkpoint_path is None:
        return
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_text(json.dumps(result, indent=2), encoding="utf-8")


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
    parser.add_argument(
        "--task-ids",
        nargs="*",
        default=None,
        help="Run only these task ids after difficulty/split filtering.",
    )
    parser.add_argument(
        "--task-range",
        default=None,
        help="Run a 1-based inclusive task range after filtering, for example 1-10.",
    )
    parser.add_argument("--output", type=Path, default=Path("notes/runs/eval_results.json"))
    args = parser.parse_args()
    output_path = output_file_path(args.output, default_name="eval_results.json")
    task_ids_override = (
        resolve_task_ids(
            difficulty=args.difficulty,
            split=args.split,
            task_ids=args.task_ids,
            task_range=args.task_range,
        )
        if args.task_ids or args.task_range
        else None
    )

    results = evaluate(
        agent_name=args.agent,
        episodes=args.episodes,
        seed=args.seed,
        model_override=args.model,
        base_url_override=args.base_url,
        difficulty=args.difficulty,
        split=args.split,
        task_ids_override=task_ids_override,
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
