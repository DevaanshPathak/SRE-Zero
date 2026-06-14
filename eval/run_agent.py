"""Run one baseline agent episode and save a trajectory JSON."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from baselines import AGENT_CHOICES, build_agent  # noqa: E402
from srezero.env import SREEnv  # noqa: E402

LLM_BASELINES = {
    "prompting",
    "react",
    "open_source",
    "open_source_react",
    "guided_open_source",
    "frontier",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one SRE-Zero baseline episode.")
    parser.add_argument("--task", default="cache_crash")
    parser.add_argument("--agent", choices=AGENT_CHOICES, default="scripted")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--model", default=None, help="Override the .env model for LLM agents.")
    parser.add_argument("--base-url", default=None, help="Override the .env base URL.")
    parser.add_argument("--allow-api", action="store_true", help="Allow API-backed LLM agents.")
    parser.add_argument("--output", type=Path, default=Path("notes/runs/agent_episode.json"))
    args = parser.parse_args()

    if args.agent in LLM_BASELINES and not args.allow_api:
        raise SystemExit(
            f"{args.agent!r} is API-backed. Re-run with --allow-api if you intend to call it."
        )

    output_path = repo_path(args.output)
    result = run_agent_episode(
        task_id=args.task,
        agent_name=args.agent,
        seed=args.seed,
        model_override=args.model,
        base_url_override=args.base_url,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print_episode(result, output_path)


def run_agent_episode(
    *,
    task_id: str,
    agent_name: str,
    seed: int,
    model_override: str | None,
    base_url_override: str | None,
) -> dict[str, Any]:
    env = SREEnv()
    observation = env.reset(task_id=task_id, seed=seed)
    agent = build_agent(
        agent_name,
        seed,
        model_override=model_override,
        base_url_override=base_url_override,
    )
    agent.reset()
    trajectory: list[dict[str, Any]] = []
    agent_error: str | None = None
    terminal_reason: str | None = None

    while not env.is_done():
        try:
            action = agent.act(observation)
        except Exception as exc:  # noqa: BLE001
            agent_error = f"{type(exc).__name__}: {exc}"
            break
        step_result = env.step(action)
        observation = step_result.observation
        terminal_reason = step_result.info.get("terminal_reason")
        trajectory.append(
            {
                "step": observation.step,
                "action": observation.last_action,
                "reward": step_result.reward,
                "summary": observation.last_result.summary,
                "error": observation.last_result.error,
                "known_findings": list(observation.known_findings),
            }
        )

    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "task_id": task_id,
        "agent": agent_name,
        "seed": seed,
        "model_override": model_override,
        "success": env.metrics.success,
        "final_reward": env.metrics.final_reward,
        "terminal_reason": terminal_reason,
        "agent_error": agent_error,
        "metrics": env.metrics.model_dump(),
        "trajectory": trajectory,
    }


def print_episode(result: dict[str, Any], output_path: Path) -> None:
    table = Table(title=f"{result['agent']} on {result['task_id']}")
    table.add_column("Step", justify="right")
    table.add_column("Action")
    table.add_column("Reward", justify="right")
    table.add_column("Result")
    for step in result["trajectory"]:
        table.add_row(
            str(step["step"]),
            str(step["action"]),
            f"{step['reward']:.3f}",
            str(step["summary"]),
        )
    console = Console()
    console.print(table)
    console.print(
        f"success={result['success']} final_reward={result['final_reward']:.3f} "
        f"output={output_path}"
    )


def repo_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return ROOT / path


if __name__ == "__main__":
    main()
