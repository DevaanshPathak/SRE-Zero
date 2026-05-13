"""Run one SRE-Zero Mini episode."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from baselines import RandomAgent, ScriptedExpertAgent  # noqa: E402
from srezero.env import SREEnv  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a single SRE-Zero episode.")
    parser.add_argument("--task", default="cache_crash")
    parser.add_argument("--agent", choices=["random", "scripted"], default="scripted")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    env = SREEnv()
    observation = env.reset(task_id=args.task, seed=args.seed)
    agent = RandomAgent(seed=args.seed) if args.agent == "random" else ScriptedExpertAgent()
    agent.reset()

    table = Table(title=f"Episode: {args.task} ({args.agent})")
    table.add_column("Step", justify="right")
    table.add_column("Action")
    table.add_column("Reward", justify="right")
    table.add_column("Result")

    while not env.is_done():
        action = agent.act(observation)
        result = env.step(action)
        observation = result.observation
        table.add_row(
            str(observation.step),
            observation.last_action or "",
            f"{result.reward:.3f}",
            observation.last_result.summary,
        )

    console = Console()
    console.print(f"[bold]Alert:[/bold] {observation.alert}")
    console.print(table)
    console.print(f"[bold]Success:[/bold] {env.metrics.success}")
    console.print(f"[bold]Final reward:[/bold] {env.metrics.final_reward:.3f}")


if __name__ == "__main__":
    main()

