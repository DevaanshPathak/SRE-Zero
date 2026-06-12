"""Run the full SRE-Zero baseline sweep.

This is the one-command runner for local experiment sweeps. It runs:

- random baseline
- scripted expert baseline
- prompting baseline over selected models
- ReAct baseline over selected models
- open-source LLM baseline over selected models
- frontier model baseline over selected models

Each run is written to its own JSON file, and a combined marks JSON is written
for paper/blog tables. Secrets from .env are never written to outputs.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = Path(__file__).resolve().parent
for import_path in (ROOT, EVAL_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from run_baseline_marks import (  # noqa: E402
    MARK_WEIGHTS,
    group_marks_by_baseline,
    group_marks_by_model,
    make_mark_row,
    pairwise_deltas_by_baseline,
    print_marks,
    run_one,
)
from run_eval import ProgressCallback, resolve_task_ids  # noqa: E402

from srezero.task_registry import Difficulty, list_task_ids  # noqa: E402

QUICK_PROMPTING_MODELS = ("openai/gpt-5-mini",)
QUICK_REACT_MODELS = ("openai/gpt-5-mini",)
QUICK_OPEN_SOURCE_MODELS = (
    "ibm-granite/granite-4.1-8b",
    "inclusionai/ring-2.6-1t:free",
)
QUICK_FRONTIER_MODELS = (
    "openai/gpt-5.5",
    "anthropic/claude-opus-4.7-fast",
)
PAPER_PROMPTING_MODELS = (
    "openai/gpt-5-mini",
    "openai/gpt-5.4-mini",
    "google/gemini-3.1-flash-lite",
    "qwen/qwen3.6-flash",
    "mistralai/mistral-medium-3-5",
)
PAPER_REACT_MODELS = (
    "openai/gpt-5-mini",
    "openai/gpt-5.4",
    "anthropic/claude-sonnet-4.6",
    "google/gemini-3.1-pro-preview",
    "x-ai/grok-4.3",
)
PAPER_OPEN_SOURCE_MODELS = (
    "ibm-granite/granite-4.1-8b",
    "inclusionai/ring-2.6-1t:free",
    "qwen/qwen3.6-35b-a3b",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "google/gemma-4-26b-a4b-it:free",
)
PAPER_FRONTIER_MODELS = (
    "openai/gpt-5.5",
    "anthropic/claude-opus-4.7-fast",
    "google/gemini-3.1-pro-preview",
    "x-ai/grok-4.3",
    "mistralai/mistral-medium-3-5",
)
BASELINE_CHOICES = ("random", "scripted", "prompting", "react", "open_source", "frontier")


def main() -> None:
    args = parse_args()
    normalize_paths(args)
    if args.timeout_seconds is not None:
        os.environ["SREZERO_LLM_TIMEOUT_SECONDS"] = str(args.timeout_seconds)
    if args.llm_max_retries is not None:
        os.environ["SREZERO_LLM_MAX_RETRIES"] = str(args.llm_max_retries)
    if args.llm_min_request_interval_seconds is not None:
        os.environ["SREZERO_LLM_MIN_REQUEST_INTERVAL_SECONDS"] = str(
            args.llm_min_request_interval_seconds
        )
    if args.llm_rate_limit_requests is not None:
        os.environ["SREZERO_LLM_RATE_LIMIT_REQUESTS"] = str(args.llm_rate_limit_requests)
    if args.llm_rate_limit_window_seconds is not None:
        os.environ["SREZERO_LLM_RATE_LIMIT_WINDOW_SECONDS"] = str(
            args.llm_rate_limit_window_seconds
        )
    if args.llm_rejection_pause_threshold is not None:
        os.environ["SREZERO_LLM_REJECTION_PAUSE_THRESHOLD"] = str(
            args.llm_rejection_pause_threshold
        )
    if args.llm_rejection_pause_seconds is not None:
        os.environ["SREZERO_LLM_REJECTION_PAUSE_SECONDS"] = str(
            args.llm_rejection_pause_seconds
        )

    console = Console()
    plan = build_plan(args)
    print_plan(plan)
    if args.dry_run:
        return

    args.output_dir.mkdir(parents=True, exist_ok=True)
    selected_task_ids = selected_task_ids_from_args(args)
    log_path = None if args.no_log_file else args.log_file
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            f"SRE-Zero full eval started {datetime.now(UTC).isoformat()}\n",
            encoding="utf-8",
        )
        append_log(log_path, f"preset={args.preset} runs={len(plan)}")

    runs: list[dict[str, Any]] = []
    mark_rows: list[dict[str, Any]] = []
    run_files: list[dict[str, str]] = []
    status = "complete"
    pause_file = None if args.no_pause_file else args.pause_file

    try:
        with make_progress(console) as progress:
            sweep_task = progress.add_task("full sweep", total=len(plan))
            for index, item in enumerate(plan, start=1):
                if pause_file is not None and pause_file.exists():
                    status = "paused"
                    pause_message = f"PAUSE requested by {pause_file}; stopping before run {index}"
                    console.log(pause_message)
                    append_log(log_path, pause_message)
                    break

                run_total = task_count(args, selected_task_ids=selected_task_ids) * item.episodes
                run_task = progress.add_task(
                    run_description(item, index, len(plan)),
                    total=run_total,
                )
                output_path = args.output_dir / item.output_name
                existing_result = load_existing_result(output_path) if args.resume else None
                if existing_result is not None and result_is_complete(
                    existing_result,
                    episodes=item.episodes,
                    args=args,
                    selected_task_ids=selected_task_ids,
                ):
                    result = existing_result
                    result["run_kind"] = result.get("run_kind", item.kind)
                    result["command_hint"] = result.get("command_hint", item.command_hint)
                    runs.append(result)
                    mark_row = make_mark_row(result, target_steps=args.target_steps)
                    mark_rows.append(mark_row)
                    run_files.append(run_file_row(item, output_path))
                    progress.update(run_task, completed=run_total)
                    progress.update(sweep_task, advance=1)
                    skip_message = (
                        f"SKIP run={index}/{len(plan)} baseline={item.baseline} "
                        f"model={item.model_label} output={output_path}"
                    )
                    console.log(skip_message)
                    append_log(log_path, skip_message)
                    continue

                existing_records = records_from_result(existing_result)
                log_message = (
                    f"START run={index}/{len(plan)} baseline={item.baseline} "
                    f"model={item.model_label} episodes={item.episodes}"
                )
                if existing_records:
                    log_message += f" resume_records={len(existing_records)}"
                console.log(log_message)
                append_log(log_path, log_message)

                result = run_one(
                    baseline=item.baseline,
                    model_label=item.model_label,
                    model_override=item.model_override,
                    episodes=item.episodes,
                    seed=args.seed,
                    base_url_override=args.base_url,
                    difficulty=args.difficulty,
                    task_ids_override=selected_task_ids,
                    progress_callback=progress_callback(
                        progress,
                        run_task,
                        item,
                        index,
                        len(plan),
                        log_path=log_path,
                    ),
                    existing_records=existing_records,
                    checkpoint_path=output_path,
                    checkpoint_extra={
                        "baseline": item.baseline,
                        "model": item.model_label,
                        "run_kind": item.kind,
                        "command_hint": item.command_hint,
                    },
                    pause_file=pause_file,
                )
                result["run_kind"] = item.kind
                result["command_hint"] = item.command_hint
                output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
                runs.append(result)
                mark_row = make_mark_row(result, target_steps=args.target_steps)
                mark_rows.append(mark_row)
                run_files.append(run_file_row(item, output_path))
                completed_episodes = int(result.get("completed_task_episodes", run_total))
                progress.update(run_task, completed=min(run_total, completed_episodes))
                progress.update(sweep_task, advance=1)
                error_label = mark_row["agent_error_count"] or (
                    "run" if mark_row["run_error"] else 0
                )
                done_message = (
                    f"END run={index}/{len(plan)} baseline={item.baseline} "
                    f"model={item.model_label} score={mark_row['score']:.3f} "
                    f"success={mark_row['metrics']['success_rate']:.3f} "
                    f"errors={error_label} "
                    f"output={output_path}"
                )
                console.log(done_message)
                append_log(log_path, done_message)
                if result.get("paused"):
                    status = "paused"
                    break
    except KeyboardInterrupt:
        status = "interrupted"
        interrupt_message = "INTERRUPTED by keyboard; completed run files remain resumable"
        console.log(interrupt_message)
        append_log(log_path, interrupt_message)

    mark_rows.sort(key=lambda row: row["score"], reverse=True)
    summary = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "config": {
            "preset": args.preset,
            "only_baselines": args.only_baselines,
            "resume": args.resume,
            "pause_file": str(pause_file) if pause_file is not None else None,
            "seed": args.seed,
            "difficulty": args.difficulty,
            "task_ids": args.task_ids,
            "task_range": args.task_range,
            "selected_task_ids": selected_task_ids,
            "target_steps": args.target_steps,
            "deterministic_episodes": args.deterministic_episodes,
            "llm_episodes": args.llm_episodes,
            "base_url_override": bool(args.base_url),
            "timeout_seconds": args.timeout_seconds,
            "llm_max_retries": args.llm_max_retries,
            "llm_min_request_interval_seconds": args.llm_min_request_interval_seconds,
            "llm_rate_limit_requests": args.llm_rate_limit_requests,
            "llm_rate_limit_window_seconds": args.llm_rate_limit_window_seconds,
            "llm_rejection_pause_threshold": args.llm_rejection_pause_threshold,
            "llm_rejection_pause_seconds": args.llm_rejection_pause_seconds,
        },
        "model_sets": model_sets_from_args(args),
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
        "run_files": run_files,
        "runs": runs,
    }
    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    append_log(log_path, f"SUMMARY output={args.summary_output}")
    print_marks(mark_rows, args.summary_output)
    if log_path is not None:
        console.print(f"Wrote run log to {log_path}")


class PlanItem:
    def __init__(
        self,
        *,
        kind: str,
        baseline: str,
        model_label: str,
        model_override: str | None,
        episodes: int,
        output_name: str,
    ) -> None:
        self.kind = kind
        self.baseline = baseline
        self.model_label = model_label
        self.model_override = model_override
        self.episodes = episodes
        self.output_name = output_name
        model_arg = f" --model {model_override}" if model_override else ""
        self.command_hint = (
            f"python eval/run_eval.py --agent {baseline}{model_arg} "
            f"--episodes {episodes} --output {output_name}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the complete SRE-Zero eval sweep.")
    parser.add_argument("--output-dir", type=Path, default=Path("notes/runs"))
    parser.add_argument(
        "--preset",
        choices=["quick", "paper"],
        default="paper",
        help="quick uses 1-2 models per bucket; paper uses 4-5 models per bucket.",
    )
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=Path("notes/runs/all_eval_summary.json"),
    )
    parser.add_argument("--deterministic-episodes", type=int, default=5)
    parser.add_argument("--llm-episodes", type=int, default=1)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--only-baselines",
        nargs="*",
        choices=BASELINE_CHOICES,
        default=None,
        help="Run only these baseline buckets.",
    )
    parser.add_argument("--base-url", default=None, help="Optional provider base URL override.")
    parser.add_argument("--difficulty", choices=["easy", "medium", "hard"], default=None)
    parser.add_argument(
        "--task-ids",
        nargs="*",
        default=None,
        help="Run only these task ids after difficulty filtering.",
    )
    parser.add_argument(
        "--task-range",
        default=None,
        help="Run a 1-based inclusive task range after filtering, for example 1-10.",
    )
    parser.add_argument("--target-steps", type=float, default=8.0)
    parser.add_argument(
        "--log-file",
        type=Path,
        default=Path("notes/runs/run_all_eval.log"),
        help="Write timestamped run logs to this file.",
    )
    parser.add_argument("--no-log-file", action="store_true")
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=None,
        help="Set SREZERO_LLM_TIMEOUT_SECONDS for this run.",
    )
    parser.add_argument(
        "--llm-max-retries",
        type=int,
        default=None,
        help="Set SREZERO_LLM_MAX_RETRIES for provider calls.",
    )
    parser.add_argument(
        "--llm-min-request-interval-seconds",
        type=float,
        default=None,
        help="Set minimum seconds to wait after one LLM request before sending another.",
    )
    parser.add_argument(
        "--llm-rate-limit-requests",
        type=int,
        default=None,
        help="Set maximum LLM requests per rate-limit window.",
    )
    parser.add_argument(
        "--llm-rate-limit-window-seconds",
        type=float,
        default=None,
        help="Set the LLM rate-limit window length in seconds.",
    )
    parser.add_argument(
        "--llm-rejection-pause-threshold",
        type=int,
        default=None,
        help="Pause after this many consecutive failed provider calls.",
    )
    parser.add_argument(
        "--llm-rejection-pause-seconds",
        type=float,
        default=None,
        help="Pause this many seconds after the rejection threshold is hit.",
    )
    parser.add_argument(
        "--prompting-models",
        nargs="*",
        default=None,
        help="Models for the prompting baseline.",
    )
    parser.add_argument(
        "--react-models",
        nargs="*",
        default=None,
        help="Models for the ReAct baseline.",
    )
    parser.add_argument(
        "--open-source-models",
        nargs="*",
        default=None,
        help="Models for the open_source baseline.",
    )
    parser.add_argument(
        "--frontier-models",
        nargs="*",
        default=None,
        help="Models for the frontier baseline.",
    )
    parser.add_argument(
        "--all-llm-models",
        nargs="*",
        default=None,
        help="Use the same model list for prompting, react, open_source, and frontier.",
    )
    parser.add_argument("--skip-llm", action="store_true")
    parser.add_argument("--skip-deterministic", action="store_true")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from existing per-run JSON files in --output-dir.",
    )
    parser.add_argument(
        "--pause-file",
        type=Path,
        default=Path("notes/runs/pause.flag"),
        help=(
            "If this file exists, stop cleanly before the next task or model run. "
            "Delete it before resuming."
        ),
    )
    parser.add_argument(
        "--no-pause-file",
        action="store_true",
        help="Disable pause-file checks.",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def normalize_paths(args: argparse.Namespace) -> None:
    args.output_dir = repo_path(args.output_dir)
    args.summary_output = output_file_path(args.summary_output, default_name="summary.json")
    args.log_file = output_file_path(args.log_file, default_name="run.log")
    args.pause_file = repo_path(args.pause_file)


def repo_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return ROOT / path


def output_file_path(path: Path, *, default_name: str) -> Path:
    resolved = repo_path(path)
    if resolved.exists() and resolved.is_dir():
        return resolved / default_name
    if path.as_posix().endswith("/") or path.as_posix().endswith("\\"):
        return resolved / default_name
    if resolved.suffix:
        return resolved
    return resolved / default_name


def load_existing_result(output_path: Path) -> dict[str, Any] | None:
    if not output_path.exists():
        return None
    try:
        data = json.loads(output_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if isinstance(data, dict):
        return data
    return None


def result_is_complete(
    result: dict[str, Any],
    *,
    episodes: int,
    args: argparse.Namespace,
    selected_task_ids: list[str] | None,
) -> bool:
    if result.get("run_error") or result.get("paused"):
        return False
    if selected_task_ids is None and result.get("complete") is True:
        return True
    records = records_from_result(result)
    expected_keys = expected_episode_keys(
        seed=args.seed,
        episodes=episodes,
        difficulty=args.difficulty,
        task_ids_override=selected_task_ids,
    )
    completed_keys = {
        (record.get("task_id"), record.get("seed"))
        for record in records
        if isinstance(record.get("task_id"), str) and isinstance(record.get("seed"), int)
    }
    return expected_keys.issubset(completed_keys)


def records_from_result(result: dict[str, Any] | None) -> list[dict[str, object]]:
    if result is None:
        return []
    records = result.get("records")
    if not isinstance(records, list):
        return []
    typed_records: list[dict[str, object]] = []
    for record in records:
        if isinstance(record, dict):
            typed_records.append(cast(dict[str, object], record))
    return typed_records


def run_file_row(item: PlanItem, output_path: Path) -> dict[str, str]:
    return {
        "baseline": item.baseline,
        "model": item.model_label,
        "path": str(output_path),
    }


def build_plan(args: argparse.Namespace) -> list[PlanItem]:
    plan: list[PlanItem] = []
    selected_baselines = set(args.only_baselines or BASELINE_CHOICES)
    if not args.skip_deterministic:
        for baseline in ("random", "scripted"):
            if baseline not in selected_baselines:
                continue
            plan.append(
                PlanItem(
                    kind="deterministic",
                    baseline=baseline,
                    model_label=f"deterministic/{baseline}",
                    model_override=None,
                    episodes=args.deterministic_episodes,
                    output_name=f"{baseline}_episodes{args.deterministic_episodes}.json",
                )
            )

    if args.skip_llm:
        return plan

    for baseline, models in model_sets_from_args(args).items():
        if baseline not in selected_baselines:
            continue
        for model in models:
            plan.append(
                PlanItem(
                    kind="llm",
                    baseline=baseline,
                    model_label=model,
                    model_override=model,
                    episodes=args.llm_episodes,
                    output_name=(
                        f"{baseline}_{safe_slug(model)}_episodes{args.llm_episodes}.json"
                    ),
                )
            )
    return plan


def model_sets_from_args(args: argparse.Namespace) -> dict[str, list[str]]:
    if args.all_llm_models:
        shared = clean_models(args.all_llm_models)
        return {
            "prompting": shared,
            "react": shared,
            "open_source": shared,
            "frontier": shared,
        }
    defaults = default_model_sets(args.preset)
    return {
        "prompting": clean_models(args.prompting_models or defaults["prompting"]),
        "react": clean_models(args.react_models or defaults["react"]),
        "open_source": clean_models(args.open_source_models or defaults["open_source"]),
        "frontier": clean_models(args.frontier_models or defaults["frontier"]),
    }


def default_model_sets(preset: str) -> dict[str, tuple[str, ...]]:
    if preset == "quick":
        return {
            "prompting": QUICK_PROMPTING_MODELS,
            "react": QUICK_REACT_MODELS,
            "open_source": QUICK_OPEN_SOURCE_MODELS,
            "frontier": QUICK_FRONTIER_MODELS,
        }
    return {
        "prompting": PAPER_PROMPTING_MODELS,
        "react": PAPER_REACT_MODELS,
        "open_source": PAPER_OPEN_SOURCE_MODELS,
        "frontier": PAPER_FRONTIER_MODELS,
    }


def clean_models(models: Sequence[str]) -> list[str]:
    cleaned: list[str] = []
    for model in models:
        candidate = model.strip()
        if candidate and candidate not in cleaned:
            cleaned.append(candidate)
    return cleaned


def safe_slug(value: str) -> str:
    return (
        value.replace("~", "")
        .replace("/", "_")
        .replace(":", "-")
        .replace("\\", "_")
        .replace(" ", "_")
    )


def print_plan(plan: list[PlanItem]) -> None:
    table = Table(title="SRE-Zero Full Eval Plan")
    table.add_column("Kind")
    table.add_column("Baseline")
    table.add_column("Model")
    table.add_column("Episodes", justify="right")
    table.add_column("Output")
    for item in plan:
        table.add_row(
            item.kind,
            item.baseline,
            item.model_label,
            str(item.episodes),
            item.output_name,
        )
    Console().print(table)


def make_progress(console: Console) -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=False,
    )


def progress_callback(
    progress: Progress,
    run_task: TaskID,
    item: PlanItem,
    run_index: int,
    total_runs: int,
    *,
    log_path: Path | None,
) -> ProgressCallback:
    def update(
        task_id: str,
        task_index: int,
        total_tasks: int,
        episode_index: int,
        total_episodes: int,
        phase: str,
    ) -> None:
        completed = (task_index - 1) * total_episodes + episode_index
        if phase == "start":
            completed -= 1
        progress.update(
            run_task,
            completed=max(0, completed),
            description=(
                f"{run_index}/{total_runs} {item.baseline} | {short_model(item.model_label)} "
                f"| {task_id} {task_index}/{total_tasks} ep {episode_index}/{total_episodes}"
            ),
        )
        append_log(
            log_path,
            (
                f"TASK {phase} run={run_index}/{total_runs} "
                f"baseline={item.baseline} model={item.model_label} "
                f"task={task_id} task_index={task_index}/{total_tasks} "
                f"episode={episode_index}/{total_episodes} completed={max(0, completed)}"
            ),
        )

    return update


def selected_task_ids_from_args(args: argparse.Namespace) -> list[str] | None:
    if not args.task_ids and not args.task_range:
        return None
    return resolve_task_ids(
        difficulty=cast(Difficulty | None, args.difficulty),
        split=None,
        task_ids=args.task_ids,
        task_range=args.task_range,
    )


def task_count(
    args: argparse.Namespace,
    *,
    selected_task_ids: list[str] | None,
) -> int:
    if selected_task_ids is not None:
        return len(selected_task_ids)
    return len(list_task_ids(difficulty=cast(Difficulty | None, args.difficulty)))


def expected_episode_keys(
    *,
    seed: int,
    episodes: int,
    difficulty: str | None,
    task_ids_override: list[str] | None,
) -> set[tuple[str, int]]:
    task_ids = task_ids_override or list_task_ids(difficulty=cast(Difficulty | None, difficulty))
    return {
        (task_id, seed + task_index * 10_000 + episode_index)
        for task_index, task_id in enumerate(task_ids)
        for episode_index in range(episodes)
    }


def run_description(item: PlanItem, run_index: int, total_runs: int) -> str:
    return f"{run_index}/{total_runs} {item.baseline} | {short_model(item.model_label)}"


def short_model(model: str, *, limit: int = 44) -> str:
    if len(model) <= limit:
        return model
    return f"{model[: limit - 1]}..."


def append_log(log_path: Path | None, message: str) -> None:
    if log_path is None:
        return
    timestamp = datetime.now(UTC).isoformat()
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"{timestamp} {message}\n")


if __name__ == "__main__":
    main()
