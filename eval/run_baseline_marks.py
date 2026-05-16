"""Run SRE-Zero baselines and write model-wise marks to JSON.

This script is intended for local benchmark sweeps. It saves full evaluation
records and a compact marks table in one JSON artifact under notes/runs/ by
default. Secrets from .env are never written to the output.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping
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

from run_eval import ProgressCallback, evaluate  # noqa: E402

from baselines import AGENT_CHOICES  # noqa: E402
from srezero.llm_config import load_env_file  # noqa: E402
from srezero.scoring import STANDARD_MARK_WEIGHTS, ZERO_METRICS, score_metrics  # noqa: E402

LLM_BASELINES = {"prompting", "react", "open_source", "frontier"}
MARK_WEIGHTS = STANDARD_MARK_WEIGHTS
ZERO_OVERALL = ZERO_METRICS


def main() -> None:
    args = parse_args()
    args.output = output_file_path(args.output, default_name="baseline_marks.json")
    baselines = expand_baselines(args.baselines)
    skipped_baselines: list[str] = []
    if args.no_api:
        skipped_baselines = [baseline for baseline in baselines if baseline in LLM_BASELINES]
        baselines = [baseline for baseline in baselines if baseline not in LLM_BASELINES]
    models = args.models or []
    runs: list[dict[str, Any]] = []
    mark_rows: list[dict[str, Any]] = []

    for baseline in baselines:
        for model_label, model_override in run_targets(baseline, models):
            result = run_one(
                baseline=baseline,
                model_label=model_label,
                model_override=model_override,
                episodes=args.episodes,
                seed=args.seed,
                base_url_override=args.base_url,
                difficulty=args.difficulty,
                split=args.split,
            )
            runs.append(result)
            mark_rows.append(make_mark_row(result, target_steps=args.target_steps))

    mark_rows.sort(key=lambda row: row["score"], reverse=True)
    output = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "config": {
            "baselines": baselines,
            "skipped_baselines": skipped_baselines,
            "no_api": args.no_api,
            "models": models,
            "episodes_per_task": args.episodes,
            "seed": args.seed,
            "difficulty": args.difficulty,
            "split": args.split,
            "target_steps": args.target_steps,
        },
        "marks_formula": {
            "max_score": 100.0,
            "components": MARK_WEIGHTS,
            "notes": (
                "efficiency marks are gated by success_rate; validity marks use "
                "1 - invalid_action_rate"
            ),
        },
        "marks": {
            "rows": mark_rows,
            "by_model": group_marks_by_model(mark_rows),
            "by_baseline": group_marks_by_baseline(mark_rows),
            "pairwise_deltas": pairwise_deltas_by_baseline(mark_rows),
        },
        "runs": runs,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print_marks(mark_rows, args.output)
    if skipped_baselines:
        print(f"Skipped API-backed baselines due to --no-api: {', '.join(skipped_baselines)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run selected baselines and generate model-wise marks."
    )
    parser.add_argument(
        "--baselines",
        nargs="+",
        default=["all"],
        choices=[*AGENT_CHOICES, "all"],
        help="Baselines to run. Use 'all' for every registered baseline.",
    )
    parser.add_argument(
        "--models",
        nargs="*",
        default=[],
        help=(
            "Optional model slugs for LLM baselines. If omitted, each LLM "
            "baseline uses its .env/default model."
        ),
    )
    parser.add_argument("--episodes", type=int, default=1)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--base-url", default=None, help="Optional provider base URL override.")
    parser.add_argument(
        "--no-api",
        action="store_true",
        help="Skip API-backed LLM baselines even if selected.",
    )
    parser.add_argument("--difficulty", choices=["easy", "medium", "hard"], default=None)
    parser.add_argument(
        "--split",
        choices=["train", "dev", "test", "unseen_incident"],
        default=None,
        help="Optional benchmark split. Can be combined with --difficulty.",
    )
    parser.add_argument(
        "--target-steps",
        type=float,
        default=8.0,
        help="Reference step budget used for efficiency marks.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("notes/runs/baseline_marks.json"),
        help="JSON output path.",
    )
    return parser.parse_args()


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


def expand_baselines(raw_baselines: list[str]) -> list[str]:
    if "all" in raw_baselines:
        return list(AGENT_CHOICES)
    return raw_baselines


def run_targets(baseline: str, models: list[str]) -> list[tuple[str, str | None]]:
    if baseline not in LLM_BASELINES:
        return [(f"deterministic/{baseline}", None)]
    if models:
        return [(model, model) for model in models]
    return [(default_model_label(baseline), None)]


def default_model_label(baseline: str) -> str:
    load_env_file()
    profile_key = f"SREZERO_{baseline.upper()}_MODEL"
    return os.environ.get(profile_key) or os.environ.get("OPENAI_MODEL") or "unconfigured"


def run_one(
    *,
    baseline: str,
    model_label: str,
    model_override: str | None,
    episodes: int,
    seed: int,
    base_url_override: str | None,
    difficulty: str | None,
    split: str | None = None,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    try:
        result = evaluate(
            agent_name=baseline,
            episodes=episodes,
            seed=seed,
            model_override=model_override,
            base_url_override=base_url_override,
            difficulty=difficulty,  # type: ignore[arg-type]
            split=split,  # type: ignore[arg-type]
            progress_callback=progress_callback,
        )
    except Exception as exc:  # noqa: BLE001
        result = {
            "agent": baseline,
            "episodes_per_task": episodes,
            "seed": seed,
            "model_override": model_override,
            "base_url_override": base_url_override,
            "difficulty": difficulty,
            "split": split,
            "overall": ZERO_OVERALL,
            "by_task": {},
            "records": [],
            "run_error": f"{type(exc).__name__}: {exc}",
        }

    result["baseline"] = baseline
    result["model"] = model_label
    return result


def make_mark_row(result: Mapping[str, Any], *, target_steps: float) -> dict[str, Any]:
    overall = as_mapping(result.get("overall"))
    standard_score = score_metrics(overall, target_steps=target_steps)
    records = result.get("records", [])
    agent_error_count = 0
    if isinstance(records, list):
        agent_error_count = sum(
            1 for record in records if isinstance(record, dict) and "agent_error" in record
        )
    return {
        "baseline": result.get("baseline", result.get("agent", "unknown")),
        "model": result.get("model", "unknown"),
        "score": standard_score.score,
        "components": standard_score.components,
        "metrics": standard_score.metrics,
        "agent_error_count": agent_error_count,
        "run_error": result.get("run_error"),
    }


def as_mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    return ZERO_OVERALL


def group_marks_by_model(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        model = str(row["model"])
        grouped.setdefault(model, []).append(row)
    return grouped


def group_marks_by_baseline(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        baseline = str(row["baseline"])
        grouped.setdefault(baseline, []).append(row)
    for baseline_rows in grouped.values():
        baseline_rows.sort(key=lambda row: row["score"], reverse=True)
    return grouped


def pairwise_deltas_by_baseline(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    deltas: dict[str, list[dict[str, Any]]] = {}
    for baseline, baseline_rows in group_marks_by_baseline(rows).items():
        baseline_deltas: list[dict[str, Any]] = []
        for left_index, left in enumerate(baseline_rows):
            for right in baseline_rows[left_index + 1 :]:
                baseline_deltas.append(
                    {
                        "better_model": left["model"],
                        "worse_model": right["model"],
                        "score_delta": round(float(left["score"]) - float(right["score"]), 3),
                        "better_score": left["score"],
                        "worse_score": right["score"],
                    }
                )
        deltas[baseline] = baseline_deltas
    return deltas


def print_marks(rows: list[dict[str, Any]], output_path: Path) -> None:
    table = Table(title="SRE-Zero Baseline Marks")
    table.add_column("Baseline")
    table.add_column("Model")
    table.add_column("Marks", justify="right")
    table.add_column("Success", justify="right")
    table.add_column("Reward", justify="right")
    table.add_column("Evidence", justify="right")
    table.add_column("Invalid", justify="right")
    table.add_column("Steps", justify="right")
    table.add_column("Errors", justify="right")

    for row in rows:
        metrics = row["metrics"]
        table.add_row(
            str(row["baseline"]),
            str(row["model"]),
            f"{row['score']:.1f}",
            f"{metrics['success_rate']:.2f}",
            f"{metrics['mean_reward']:.3f}",
            f"{metrics['evidence_coverage']:.2f}",
            f"{metrics['invalid_action_rate']:.2f}",
            f"{metrics['mean_steps']:.2f}",
            str(row["agent_error_count"] or ("run" if row["run_error"] else 0)),
        )

    console = Console()
    console.print(table)
    console.print(f"Wrote records and marks to {output_path}")


if __name__ == "__main__":
    main()
