"""Run the canonical SRE-Zero benchmark command."""

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
EVAL_DIR = Path(__file__).resolve().parent
for import_path in (ROOT, EVAL_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from run_eval import evaluate, output_file_path  # noqa: E402

from baselines import AGENT_CHOICES  # noqa: E402
from srezero.benchmark import DEFAULT_SEED, benchmark_spec, benchmark_task_ids  # noqa: E402
from srezero.scoring import score_metrics  # noqa: E402


def main() -> None:
    args = parse_args()
    output_path = output_file_path(args.output, default_name="benchmark_results.json")
    result = evaluate(
        agent_name=args.agent,
        episodes=args.episodes,
        seed=args.seed,
        model_override=args.model,
        base_url_override=args.base_url,
        difficulty=args.difficulty,
        split=args.split,
    )
    standard_score = score_metrics(result["overall"], target_steps=args.target_steps)  # type: ignore[arg-type]
    output = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "benchmark": benchmark_spec().model_dump(),
        "command": {
            "agent": args.agent,
            "split": args.split,
            "difficulty": args.difficulty,
            "episodes": args.episodes,
            "seed": args.seed,
            "target_steps": args.target_steps,
            "task_count": len(benchmark_task_ids(split=args.split, difficulty=args.difficulty)),
        },
        "score": standard_score.model_dump(),
        "result": result,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print_benchmark(output, output_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the canonical SRE-Zero benchmark.")
    parser.add_argument("--agent", choices=AGENT_CHOICES, default="scripted")
    parser.add_argument(
        "--split",
        choices=["train", "dev", "test", "unseen_incident"],
        default="test",
    )
    parser.add_argument("--difficulty", choices=["easy", "medium", "hard"], default=None)
    parser.add_argument("--episodes", type=int, default=1)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--model", default=None, help="Override the .env model for LLM agents.")
    parser.add_argument("--base-url", default=None, help="Override the .env base URL.")
    parser.add_argument("--target-steps", type=float, default=8.0)
    parser.add_argument("--output", type=Path, default=Path("notes/runs/benchmark_results.json"))
    return parser.parse_args()


def print_benchmark(output: dict[str, Any], output_path: Path) -> None:
    score = output["score"]
    metrics = score["metrics"]
    table = Table(title="SRE-Zero Benchmark Result")
    table.add_column("Field")
    table.add_column("Value", justify="right")
    table.add_row("agent", output["command"]["agent"])
    table.add_row("split", output["command"]["split"])
    table.add_row("tasks", str(output["command"]["task_count"]))
    table.add_row("marks", f"{score['score']:.1f}")
    table.add_row("success_rate", f"{metrics['success_rate']:.2f}")
    table.add_row("mean_reward", f"{metrics['mean_reward']:.3f}")
    table.add_row("mean_steps", f"{metrics['mean_steps']:.2f}")
    table.add_row("invalid_action_rate", f"{metrics['invalid_action_rate']:.2f}")
    table.add_row("evidence_coverage", f"{metrics['evidence_coverage']:.2f}")
    table.add_row("wrong_remediation_rate", f"{metrics['wrong_remediation_rate']:.2f}")
    table.add_row("distractor_failure_rate", f"{metrics['distractor_failure_rate']:.2f}")
    Console().print(table)
    Console().print(f"Wrote benchmark results to {output_path}")


if __name__ == "__main__":
    main()
