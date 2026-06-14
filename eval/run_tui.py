"""Rich terminal manager for resumable SRE-Zero baseline runs."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table
from rich.text import Text

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = Path(__file__).resolve().parent
for import_path in (ROOT, EVAL_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from run_all_eval import (  # noqa: E402
    BASELINE_CHOICES,
    EASY_SPLIT_BLOG_OPEN_WEIGHT_MODELS,
    OPEN_WEIGHT_FALLBACK_MODELS,
    PAPER_FRONTIER_MODELS,
    PAPER_GUIDED_OPEN_SOURCE_MODELS,
    PAPER_OPEN_SOURCE_MODELS,
    PAPER_OPEN_SOURCE_REACT_MODELS,
    PAPER_PROMPTING_MODELS,
    PAPER_REACT_MODELS,
    group_marks_by_baseline,
    group_marks_by_difficulty,
    group_marks_by_model,
    make_difficulty_mark_rows,
    make_mark_row,
    pairwise_deltas_by_baseline,
    safe_slug,
)
from run_eval import resolve_task_ids  # noqa: E402

from srezero.task_registry import Difficulty, list_task_ids  # noqa: E402

console = Console()
STALE_PROCESS_SECONDS = 300.0

LLM_BASELINES = {
    "prompting",
    "react",
    "open_source",
    "open_source_react",
    "guided_open_source",
    "frontier",
}
DETERMINISTIC_BASELINES = {"random", "scripted"}
MODEL_ARG_BY_BASELINE = {
    "prompting": "--prompting-models",
    "react": "--react-models",
    "open_source": "--open-source-models",
    "open_source_react": "--open-source-react-models",
    "guided_open_source": "--guided-open-source-models",
    "frontier": "--frontier-models",
}
DEFAULT_MODELS = {
    "prompting": list(PAPER_PROMPTING_MODELS),
    "react": list(PAPER_REACT_MODELS),
    "open_source": list(PAPER_OPEN_SOURCE_MODELS),
    "open_source_react": list(PAPER_OPEN_SOURCE_REACT_MODELS),
    "guided_open_source": list(PAPER_GUIDED_OPEN_SOURCE_MODELS),
    "frontier": list(PAPER_FRONTIER_MODELS),
}
EXTRA_MODEL_CANDIDATES = {
    "open_source": list(EASY_SPLIT_BLOG_OPEN_WEIGHT_MODELS + OPEN_WEIGHT_FALLBACK_MODELS),
    "open_source_react": list(EASY_SPLIT_BLOG_OPEN_WEIGHT_MODELS + OPEN_WEIGHT_FALLBACK_MODELS),
    "guided_open_source": list(EASY_SPLIT_BLOG_OPEN_WEIGHT_MODELS + OPEN_WEIGHT_FALLBACK_MODELS),
}
MODEL_SLUG_RE = re.compile(r"^~?[a-z0-9][a-z0-9_.-]*/[a-z0-9][a-z0-9_.:-]*$", re.I)
RunStatus = Literal["pending", "partial", "paused", "complete", "error", "running"]
ChecklistMode = Literal["toggle", "select", "drop"]
ChecklistAction = Literal[
    "continue",
    "done",
    "next",
    "prev",
    "search",
    "clear_filter",
    "manual",
    "invalid",
]


@dataclass(frozen=True)
class ChecklistCommandResult:
    candidates: list[str]
    selected: set[str]
    action: ChecklistAction


@dataclass(frozen=True)
class RunTarget:
    baseline: str
    model: str | None = None

    @property
    def label(self) -> str:
        if self.model is not None:
            return self.model
        return f"deterministic/{self.baseline}"

    @property
    def key(self) -> str:
        return safe_target_key(self.baseline, self.model)

    def output_name(self, config: ManagedRunConfig) -> str:
        if self.baseline in DETERMINISTIC_BASELINES:
            return f"{self.baseline}_episodes{config.deterministic_episodes}.json"
        if self.model is None:
            raise ValueError(f"LLM target {self.baseline!r} requires a model.")
        return f"{self.baseline}_{safe_slug(self.model)}_episodes{config.llm_episodes}.json"

    def to_json(self) -> dict[str, str | None]:
        return {"baseline": self.baseline, "model": self.model}

    @classmethod
    def from_json(cls, data: dict[str, object]) -> RunTarget:
        baseline = data.get("baseline")
        model = data.get("model")
        if not isinstance(baseline, str):
            raise ValueError("target baseline must be a string")
        if model is not None and not isinstance(model, str):
            raise ValueError("target model must be a string or null")
        return cls(baseline=baseline, model=model)


@dataclass(frozen=True)
class ManagedRunConfig:
    run_id: str
    created_at: str
    difficulty: str | None
    seed: int
    deterministic_episodes: int
    llm_episodes: int
    target_steps: float
    timeout_seconds: float
    llm_max_tokens: int
    llm_max_retries: int
    llm_min_request_interval_seconds: float
    llm_rate_limit_requests: int
    llm_rate_limit_window_seconds: float
    llm_rejection_pause_threshold: int
    llm_rejection_pause_seconds: float
    llm_reasoning_exclude: bool
    llm_qwen_no_think: bool
    targets: list[RunTarget]

    def to_json(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "run_id": self.run_id,
            "created_at": self.created_at,
            "difficulty": self.difficulty,
            "seed": self.seed,
            "deterministic_episodes": self.deterministic_episodes,
            "llm_episodes": self.llm_episodes,
            "target_steps": self.target_steps,
            "timeout_seconds": self.timeout_seconds,
            "llm_max_tokens": self.llm_max_tokens,
            "llm_max_retries": self.llm_max_retries,
            "llm_min_request_interval_seconds": self.llm_min_request_interval_seconds,
            "llm_rate_limit_requests": self.llm_rate_limit_requests,
            "llm_rate_limit_window_seconds": self.llm_rate_limit_window_seconds,
            "llm_rejection_pause_threshold": self.llm_rejection_pause_threshold,
            "llm_rejection_pause_seconds": self.llm_rejection_pause_seconds,
            "llm_reasoning_exclude": self.llm_reasoning_exclude,
            "llm_qwen_no_think": self.llm_qwen_no_think,
            "targets": [target.to_json() for target in self.targets],
        }

    @classmethod
    def from_json(cls, data: dict[str, object]) -> ManagedRunConfig:
        targets_raw = data.get("targets")
        if not isinstance(targets_raw, list):
            raise ValueError("run config targets must be a list")
        targets = [RunTarget.from_json(cast(dict[str, object], item)) for item in targets_raw]
        return cls(
            run_id=required_str(data, "run_id"),
            created_at=required_str(data, "created_at"),
            difficulty=optional_str(data, "difficulty"),
            seed=required_int(data, "seed"),
            deterministic_episodes=required_int(data, "deterministic_episodes"),
            llm_episodes=required_int(data, "llm_episodes"),
            target_steps=required_float(data, "target_steps"),
            timeout_seconds=required_float(data, "timeout_seconds"),
            llm_max_tokens=int_or_default(data, "llm_max_tokens", 1536),
            llm_max_retries=required_int(data, "llm_max_retries"),
            llm_min_request_interval_seconds=required_float(
                data, "llm_min_request_interval_seconds"
            ),
            llm_rate_limit_requests=required_int(data, "llm_rate_limit_requests"),
            llm_rate_limit_window_seconds=required_float(
                data, "llm_rate_limit_window_seconds"
            ),
            llm_rejection_pause_threshold=required_int(
                data, "llm_rejection_pause_threshold"
            ),
            llm_rejection_pause_seconds=required_float(data, "llm_rejection_pause_seconds"),
            llm_reasoning_exclude=bool_or_default(
                data,
                "llm_reasoning_exclude",
                True,
            ),
            llm_qwen_no_think=bool_or_default(data, "llm_qwen_no_think", True),
            targets=targets,
        )


@dataclass(frozen=True)
class ManagedRun:
    config: ManagedRunConfig
    run_dir: Path

    @property
    def config_path(self) -> Path:
        return self.run_dir / "run.json"

    @property
    def output_dir(self) -> Path:
        return self.run_dir / "outputs"

    @property
    def logs_dir(self) -> Path:
        return self.run_dir / "logs"

    @property
    def summaries_dir(self) -> Path:
        return self.run_dir / "target_summaries"

    @property
    def commands_dir(self) -> Path:
        return self.run_dir / "commands"

    @property
    def state_path(self) -> Path:
        return self.run_dir / "manager_state.json"

    @property
    def summary_path(self) -> Path:
        return self.run_dir / "summary.json"

    @property
    def pause_file(self) -> Path:
        return self.run_dir / "pause.flag"

    @property
    def queue_path(self) -> Path:
        return self.run_dir / "queue.json"

    def target_output_path(self, target: RunTarget) -> Path:
        return self.output_dir / target.output_name(self.config)

    def target_log_path(self, target: RunTarget) -> Path:
        return self.logs_dir / f"{target.key}.run.log"

    def target_console_log_path(self, target: RunTarget) -> Path:
        return self.logs_dir / f"{target.key}.console.log"

    def target_summary_path(self, target: RunTarget) -> Path:
        return self.summaries_dir / f"{target.key}.summary.json"

    def target_command_path(self, target: RunTarget) -> Path:
        return self.commands_dir / f"{target.key}.ps1"


def main() -> None:
    args = parse_args()
    if args.run:
        open_run(load_run(args.run))
        return

    while True:
        console.rule("[bold]SRE-Zero Baseline TUI")
        show_run_list()
        console.print(
            Panel(
                "1. Create run\n"
                "2. Open run\n"
                "3. Refresh\n"
                "4. Delete run\n"
                "q. Quit",
                title="Menu",
            )
        )
        choice = Prompt.ask("Choose", default="1").strip().lower()
        if choice == "1":
            create_run()
        elif choice == "2":
            managed = choose_managed_run("Open run")
            if managed is not None:
                open_run(managed)
        elif choice == "3":
            continue
        elif choice == "4":
            managed = choose_managed_run("Delete run")
            if managed is not None:
                delete_run(managed)
        elif choice in {"q", "quit", "exit"}:
            return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage SRE-Zero baseline runs in a TUI.")
    parser.add_argument("--run", default=None, help="Open a managed run id directly.")
    return parser.parse_args()


def create_run() -> None:
    default_run_id = f"run-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
    run_id = Prompt.ask("Run id", default=default_run_id).strip()
    difficulty_raw = Prompt.ask(
        "Difficulty",
        choices=["all", "easy", "medium", "hard"],
        default="all",
    )
    difficulty = None if difficulty_raw == "all" else difficulty_raw
    seed = IntPrompt.ask("Seed", default=0)
    deterministic_episodes = IntPrompt.ask("Deterministic episodes per task", default=5)
    llm_episodes = IntPrompt.ask("LLM episodes per task", default=1)
    target_steps = float(Prompt.ask("Target steps for marks", default="8"))
    baseline_defaults = "random,scripted,open_source,open_source_react,guided_open_source"
    baselines = choose_baselines(baseline_defaults)
    targets = choose_targets(baselines)
    if not targets:
        console.print("[red]No targets selected; run not created.[/red]")
        return

    config = ManagedRunConfig(
        run_id=run_id,
        created_at=datetime.now(UTC).isoformat(),
        difficulty=difficulty,
        seed=seed,
        deterministic_episodes=deterministic_episodes,
        llm_episodes=llm_episodes,
        target_steps=target_steps,
        timeout_seconds=float(Prompt.ask("LLM timeout seconds", default="30")),
        llm_max_tokens=IntPrompt.ask("LLM max output tokens", default=1536),
        llm_max_retries=IntPrompt.ask("LLM max retries", default=5),
        llm_min_request_interval_seconds=float(
            Prompt.ask("Seconds between LLM requests", default="15")
        ),
        llm_rate_limit_requests=IntPrompt.ask("LLM requests per window", default=5),
        llm_rate_limit_window_seconds=float(
            Prompt.ask("LLM rate-limit window seconds", default="60")
        ),
        llm_rejection_pause_threshold=IntPrompt.ask(
            "Consecutive rejected requests before cooldown",
            default=3,
        ),
        llm_rejection_pause_seconds=float(
            Prompt.ask("Cooldown seconds after rejection threshold", default="60")
        ),
        llm_reasoning_exclude=Confirm.ask(
            "Exclude reasoning payloads for Hack Club/OpenRouter",
            default=True,
        ),
        llm_qwen_no_think=Confirm.ask("Append /no_think for Qwen models", default=True),
        targets=targets,
    )
    managed = ManagedRun(config=config, run_dir=managed_root() / run_id)
    save_run(managed)
    write_all_target_commands(managed)
    console.print(f"[green]Created run[/green] {managed.run_dir}")
    open_run(managed)


def choose_baselines(default_value: str) -> list[str]:
    console.print(f"Available baselines: {', '.join(BASELINE_CHOICES)}")
    raw = Prompt.ask(
        "Baselines, comma-separated",
        default=default_value,
    )
    selected = unique_items(item.strip() for item in raw.split(","))
    invalid = [item for item in selected if item not in BASELINE_CHOICES]
    if invalid:
        raise ValueError(f"Unknown baselines: {', '.join(invalid)}")
    return selected


def choose_targets(baselines: list[str]) -> list[RunTarget]:
    targets: list[RunTarget] = []
    available_models = load_available_model_slugs()
    for baseline in baselines:
        if baseline in DETERMINISTIC_BASELINES:
            targets.append(RunTarget(baseline=baseline))
            continue
        models = choose_models_for_baseline(baseline, available_models)
        targets.extend(RunTarget(baseline=baseline, model=model) for model in models)
    return targets


def choose_models_for_baseline(
    baseline: str,
    available_models: list[str],
) -> list[str]:
    if interactive_terminal():
        return choose_models_for_baseline_keyboard(baseline, available_models)
    return choose_models_for_baseline_prompt(baseline, available_models)


def choose_models_for_baseline_keyboard(
    baseline: str,
    available_models: list[str],
) -> list[str]:
    defaults = DEFAULT_MODELS.get(baseline, [])
    candidates = model_checklist_candidates(
        [*defaults, *EXTRA_MODEL_CANDIDATES.get(baseline, [])],
        available_models,
    )
    selected = set(defaults)
    filter_text = ""
    page = 0
    cursor = 0
    while True:
        visible = filtered_models(candidates, filter_text)
        visible_page, page, page_count, cursor = checklist_page(
            visible,
            page=page,
            cursor=cursor,
        )
        console.clear()
        render_model_checklist(
            baseline=baseline,
            candidates=visible_page,
            selected=selected,
            filter_text=filter_text,
            page=page,
            page_count=page_count,
            cursor=cursor,
        )
        key = read_key()
        if key == "enter":
            return selected_models_in_order(candidates, selected)
        if key in {"escape", "q"}:
            return selected_models_in_order(candidates, selected)
        if key == "up":
            cursor = max(0, cursor - 1)
            continue
        if key == "down":
            cursor = min(max(0, len(visible_page) - 1), cursor + 1)
            continue
        if key in {"left", "pageup"}:
            page = max(0, page - 1)
            cursor = 0
            continue
        if key in {"right", "pagedown"}:
            page = min(page + 1, page_count - 1)
            cursor = 0
            continue
        if key == "home":
            page = 0
            cursor = 0
            continue
        if key == "end":
            page = page_count - 1
            cursor = 0
            continue
        if key == "space":
            if visible_page:
                toggle_selected_value(selected, visible_page[cursor])
            continue
        if key == "a":
            selected.update(visible_page)
            continue
        if key == "u":
            selected.difference_update(visible_page)
            continue
        if key == "c":
            selected.clear()
            continue
        if key == "d":
            selected = set(defaults)
            continue
        if key in {"/", "s"}:
            filter_text = Prompt.ask("Filter text", default="").strip()
            page = 0
            cursor = 0
            continue
        if key == "f":
            filter_text = ""
            page = 0
            cursor = 0
            continue
        if key == "m":
            raw = Prompt.ask("Model slugs, comma-separated").strip()
            manual_models = unique_items(item.strip() for item in raw.split(","))
            candidates = unique_items([*candidates, *manual_models])
            selected.update(manual_models)
            continue
        if key == ":":
            command = Prompt.ask("Typed checklist command").strip()
            result = apply_model_checklist_command(
                command=command,
                candidates=candidates,
                visible_page=visible_page,
                selected=selected,
                defaults=defaults,
            )
            candidates = result.candidates
            selected = result.selected
            if result.action == "done":
                return selected_models_in_order(candidates, selected)
            if result.action == "next":
                page = min(page + 1, page_count - 1)
            elif result.action == "prev":
                page = max(0, page - 1)
            elif result.action == "search":
                filter_text = Prompt.ask("Filter text", default="").strip()
                page = 0
                cursor = 0
            elif result.action == "clear_filter":
                filter_text = ""
                page = 0
                cursor = 0
            elif result.action == "manual":
                raw = Prompt.ask("Model slugs, comma-separated").strip()
                manual_models = unique_items(item.strip() for item in raw.split(","))
                candidates = unique_items([*candidates, *manual_models])
                selected.update(manual_models)
            elif result.action == "invalid":
                console.print("[yellow]No valid checklist items matched that input.[/yellow]")


def choose_models_for_baseline_prompt(
    baseline: str,
    available_models: list[str],
) -> list[str]:
    defaults = DEFAULT_MODELS.get(baseline, [])
    candidates = model_checklist_candidates(
        [*defaults, *EXTRA_MODEL_CANDIDATES.get(baseline, [])],
        available_models,
    )
    selected = set(defaults)
    filter_text = ""
    page = 0
    while True:
        visible = filtered_models(candidates, filter_text)
        page_count = max(1, (len(visible) + 14) // 15)
        page = min(page, page_count - 1)
        visible_page = visible[page * 15 : page * 15 + 15]
        render_model_checklist(
            baseline=baseline,
            candidates=visible_page,
            selected=selected,
            filter_text=filter_text,
            page=page,
            page_count=page_count,
            cursor=None,
        )
        command = Prompt.ask(
            "Rows/ranges, select/drop rows, or search/manual/defaults/all/none/next/prev/done",
            default="done",
        ).strip()
        lowered = command.lower()
        if lowered == "keys":
            return choose_models_for_baseline_keyboard(baseline, available_models)
        result = apply_model_checklist_command(
            command=command,
            candidates=candidates,
            visible_page=visible_page,
            selected=selected,
            defaults=defaults,
        )
        candidates = result.candidates
        selected = result.selected
        if result.action == "done":
            return selected_models_in_order(candidates, selected)
        if result.action == "next":
            page = min(page + 1, page_count - 1)
            continue
        if result.action == "prev":
            page = max(0, page - 1)
            continue
        if result.action == "search":
            filter_text = Prompt.ask("Filter text", default="").strip()
            page = 0
            continue
        if result.action == "clear_filter":
            filter_text = ""
            page = 0
            continue
        if result.action == "manual":
            raw = Prompt.ask("Model slugs, comma-separated").strip()
            manual_models = unique_items(item.strip() for item in raw.split(","))
            candidates = unique_items([*candidates, *manual_models])
            selected.update(manual_models)
            continue
        if result.action == "invalid":
            console.print("[yellow]No valid checklist items matched that input.[/yellow]")


def model_checklist_candidates(defaults: list[str], available_models: list[str]) -> list[str]:
    return unique_items([*defaults, *available_models])


def filtered_models(candidates: list[str], filter_text: str) -> list[str]:
    if not filter_text:
        return candidates
    lowered = filter_text.lower()
    return [model for model in candidates if lowered in model.lower()]


def selected_models_in_order(candidates: list[str], selected: set[str]) -> list[str]:
    ordered = [model for model in candidates if model in selected]
    extras = sorted(model for model in selected if model not in candidates)
    return [*ordered, *extras]


def apply_model_checklist_command(
    *,
    command: str,
    candidates: list[str],
    visible_page: list[str],
    selected: set[str],
    defaults: list[str],
) -> ChecklistCommandResult:
    lowered = command.strip().lower()
    if lowered in {"done", "d"}:
        return ChecklistCommandResult(candidates, set(selected), "done")
    if lowered in {"next", "n"}:
        return ChecklistCommandResult(candidates, set(selected), "next")
    if lowered in {"prev", "p"}:
        return ChecklistCommandResult(candidates, set(selected), "prev")
    if lowered in {"search", "s", "/"}:
        return ChecklistCommandResult(candidates, set(selected), "search")
    if lowered in {"clear-filter", "cf"}:
        return ChecklistCommandResult(candidates, set(selected), "clear_filter")
    if lowered in {"manual", "m"}:
        return ChecklistCommandResult(candidates, set(selected), "manual")
    if lowered in {"defaults", "reset"}:
        return ChecklistCommandResult(candidates, set(defaults), "continue")
    if lowered in {"all", "a"}:
        return ChecklistCommandResult(candidates, selected | set(visible_page), "continue")
    if lowered in {"none", "u"}:
        return ChecklistCommandResult(
            candidates,
            selected.difference(visible_page),
            "continue",
        )
    if lowered in {"clear", "c"}:
        return ChecklistCommandResult(candidates, set(), "continue")

    mode, index_text = parse_checklist_selection_command(command)
    indexes = parse_checklist_indexes(index_text, max_index=len(visible_page))
    if not indexes:
        return ChecklistCommandResult(candidates, set(selected), "invalid")
    updated = set(selected)
    for index in indexes:
        model = visible_page[index - 1]
        apply_selection_mode(updated, model, mode)
    return ChecklistCommandResult(candidates, updated, "continue")


def render_model_checklist(
    *,
    baseline: str,
    candidates: list[str],
    selected: set[str],
    filter_text: str,
    page: int,
    page_count: int,
    cursor: int | None,
) -> None:
    table = Table(
        title=(
            f"{baseline} Model Checklist "
            f"(selected={len(selected)}, filter={filter_text or 'none'}, "
            f"page={page + 1}/{page_count})"
        )
    )
    table.add_column("", justify="center")
    table.add_column("#", justify="right")
    table.add_column("Use", justify="center")
    table.add_column("Model")
    if not candidates:
        table.add_row("", "-", "-", "[dim]No models match the current filter.[/dim]")
    for index, model in enumerate(candidates, start=1):
        marker = Text(">", style="bold cyan") if cursor == index - 1 else Text("")
        table.add_row(marker, str(index), checkbox(model in selected), model)
    console.print(table)
    console.print(
        "[dim]Keys: Up/Down move, Space toggles, Left/Right pages, Enter accepts, "
        "/ searches, f clears filter, a selects visible, u clears visible, c clears all, "
        "d resets defaults, m adds manual slugs, : typed command.[/dim]"
    )


def checkbox(checked: bool) -> Text:
    return Text("[x]" if checked else "[]", style="green" if checked else "dim")


def toggle_selected_value(selected: set[str], value: str) -> None:
    if value in selected:
        selected.remove(value)
    else:
        selected.add(value)


def apply_selection_mode(selected: set[str], value: str, mode: ChecklistMode) -> None:
    if mode == "select":
        selected.add(value)
    elif mode == "drop":
        selected.discard(value)
    else:
        toggle_selected_value(selected, value)


def checklist_page(
    values: list[str],
    *,
    page: int,
    cursor: int,
    page_size: int = 15,
) -> tuple[list[str], int, int, int]:
    page_count = max(1, (len(values) + page_size - 1) // page_size)
    safe_page = min(max(0, page), page_count - 1)
    visible_page = values[safe_page * page_size : safe_page * page_size + page_size]
    safe_cursor = min(max(0, cursor), max(0, len(visible_page) - 1))
    return visible_page, safe_page, page_count, safe_cursor


def interactive_terminal() -> bool:
    return console.is_terminal and sys.stdin.isatty()


def read_key() -> str:
    if os.name == "nt":
        return read_key_windows()
    return read_key_posix()


def read_key_or_none(timeout_seconds: float) -> str | None:
    if not interactive_terminal():
        time.sleep(timeout_seconds)
        return None
    if os.name == "nt":
        import msvcrt

        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if msvcrt.kbhit():
                return read_key_windows()
            time.sleep(0.05)
        return None
    return read_key_posix_or_none(timeout_seconds)


def read_key_windows() -> str:
    import msvcrt

    char = msvcrt.getwch()
    if char == "\x03":
        raise KeyboardInterrupt
    if char in {"\x00", "\xe0"}:
        second = msvcrt.getwch()
        return {
            "H": "up",
            "P": "down",
            "K": "left",
            "M": "right",
            "I": "pageup",
            "Q": "pagedown",
            "G": "home",
            "O": "end",
        }.get(second, "")
    return normalize_key(char)


def read_key_posix() -> str:
    import select
    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        char = sys.stdin.read(1)
        if char == "\x03":
            raise KeyboardInterrupt
        if char == "\x1b":
            if not select.select([sys.stdin], [], [], 0.02)[0]:
                return "escape"
            second = sys.stdin.read(1)
            if second != "[":
                return "escape"
            third = sys.stdin.read(1)
            if third.isdigit():
                tilde = sys.stdin.read(1)
                if tilde != "~":
                    return ""
                return {
                    "5": "pageup",
                    "6": "pagedown",
                    "1": "home",
                    "4": "end",
                }.get(third, "")
            return {
                "A": "up",
                "B": "down",
                "C": "right",
                "D": "left",
                "H": "home",
                "F": "end",
            }.get(third, "")
        return normalize_key(char)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def read_key_posix_or_none(timeout_seconds: float) -> str | None:
    import select
    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ready, _, _ = select.select([sys.stdin], [], [], timeout_seconds)
        if not ready:
            return None
        char = sys.stdin.read(1)
        return parse_posix_key_from_char(char)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def parse_posix_key_from_char(char: str) -> str:
    import select

    if char == "\x03":
        raise KeyboardInterrupt
    if char == "\x1b":
        if not select.select([sys.stdin], [], [], 0.02)[0]:
            return "escape"
        second = sys.stdin.read(1)
        if second != "[":
            return "escape"
        third = sys.stdin.read(1)
        if third.isdigit():
            tilde = sys.stdin.read(1)
            if tilde != "~":
                return ""
            return {
                "5": "pageup",
                "6": "pagedown",
                "1": "home",
                "4": "end",
            }.get(third, "")
        return {
            "A": "up",
            "B": "down",
            "C": "right",
            "D": "left",
            "H": "home",
            "F": "end",
        }.get(third, "")
    return normalize_key(char)


def normalize_key(char: str) -> str:
    if char in {"\r", "\n"}:
        return "enter"
    if char == "\x1b":
        return "escape"
    if char == " ":
        return "space"
    if len(char) == 1:
        return char.lower()
    return char


def parse_checklist_selection_command(raw: str) -> tuple[ChecklistMode, str]:
    stripped = raw.strip()
    lowered = stripped.lower()
    for prefix, mode in (
        ("select ", "select"),
        ("add ", "select"),
        ("use ", "select"),
        ("on ", "select"),
        ("drop ", "drop"),
        ("remove ", "drop"),
        ("unselect ", "drop"),
        ("rm ", "drop"),
        ("off ", "drop"),
    ):
        if lowered.startswith(prefix):
            return cast(ChecklistMode, mode), stripped[len(prefix) :].strip()
    return "toggle", stripped


def parse_checklist_indexes(raw: str, *, max_index: int) -> list[int]:
    indexes: list[int] = []
    for part in raw.split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            start_raw, end_raw = token.split("-", 1)
            if not start_raw.strip().isdigit() or not end_raw.strip().isdigit():
                continue
            start = int(start_raw)
            end = int(end_raw)
            if start > end:
                start, end = end, start
            indexes.extend(range(start, end + 1))
            continue
        if token.isdigit():
            indexes.append(int(token))
    deduped: list[int] = []
    seen: set[int] = set()
    for index in indexes:
        if 1 <= index <= max_index and index not in seen:
            seen.add(index)
            deduped.append(index)
    return deduped


def search_models(available_models: list[str]) -> list[str]:
    if not available_models:
        console.print("[yellow]No notes/available_models.md slugs found.[/yellow]")
        return []
    query = Prompt.ask("Search text").strip().lower()
    matches = [model for model in available_models if query in model.lower()][:25]
    if not matches:
        console.print("[yellow]No matches.[/yellow]")
        return []
    table = Table(title=f"Model Matches: {query}")
    table.add_column("#", justify="right")
    table.add_column("Model")
    for index, model in enumerate(matches, start=1):
        table.add_row(str(index), model)
    console.print(table)
    raw = Prompt.ask("Indexes or raw slugs, comma-separated").strip()
    selected: list[str] = []
    for item in (part.strip() for part in raw.split(",")):
        if not item:
            continue
        if item.isdigit() and 1 <= int(item) <= len(matches):
            selected.append(matches[int(item) - 1])
        else:
            selected.append(item)
    return selected


def open_run(managed: ManagedRun) -> None:
    while True:
        refresh_state_if_needed(managed)
        console.rule(f"[bold]Run: {managed.config.run_id}")
        show_dashboard(managed)
        console.print(
            Panel(
                "1. Play queued targets\n"
                "2. Queue manager\n"
                "3. Play next pending/partial target\n"
                "4. Run one selected target\n"
                "5. Rerun one selected target from scratch\n"
                "6. Run selected target over task range\n"
                "7. Rerun errored/missing tasks for one target\n"
                "8. Add targets/models\n"
                "9. Remove targets from run\n"
                "10. Pause after current task/episode\n"
                "11. Pause and stop active process now\n"
                "12. Clear pause flag\n"
                "13. Watch live status/logs\n"
                "14. Show target details\n"
                "15. Show log tail\n"
                "16. Rebuild combined summary\n"
                "17. Write/print command for selected target\n"
                "18. Delete selected target artifacts\n"
                "19. Show run folder\n"
                "20. Delete this run\n"
                "b. Back",
                title="Run Menu",
            )
        )
        choice = Prompt.ask("Choose", default="1").strip().lower()
        if choice == "1":
            play_queue(managed)
        elif choice == "2":
            manage_queue(managed)
        elif choice == "3":
            target = next_runnable_target(managed)
            if target is None:
                console.print("[green]No pending or partial targets.[/green]")
                continue
            launch_target(managed, target)
        elif choice == "4":
            targets = select_targets_checklist(managed, title="Run Target")
            if len(targets) == 1:
                launch_target(managed, targets[0])
            elif len(targets) > 1:
                added = append_targets_to_queue(managed, targets)
                queue_path = write_queue_script(managed, targets)
                console.print(
                    "[yellow]Only one background target can run at once.[/yellow] "
                    f"Added {added} target(s) to the managed queue and wrote script: "
                    f"{queue_path}"
                )
                if Confirm.ask("Launch the first selected target now?", default=True):
                    launch_target(managed, targets[0])
        elif choice == "5":
            rerun_one_target(managed)
        elif choice == "6":
            run_target_task_range(managed)
        elif choice == "7":
            rerun_errored_tasks(managed)
        elif choice == "8":
            managed = add_targets_to_run(managed)
        elif choice == "9":
            managed = remove_targets_from_run(managed)
        elif choice == "10":
            pause_run(managed)
            watch_run_live(managed, target=active_target(managed), exit_when_inactive=True)
        elif choice == "11":
            target = active_target(managed)
            pause_run(managed)
            stop_active_process(managed, confirm=True, force=True)
            watch_run_live(managed, target=target, exit_when_inactive=True)
        elif choice == "12":
            clear_pause(managed)
        elif choice == "13":
            watch_run_live(managed, target=active_target(managed), exit_when_inactive=False)
        elif choice == "14":
            target = select_target(managed)
            if target is not None:
                show_target_details(managed, target)
        elif choice == "15":
            target = select_target(managed)
            if target is not None:
                show_log_tail(managed, target)
        elif choice == "16":
            rebuild_summary(managed)
        elif choice == "17":
            target = select_target(managed)
            if target is not None:
                write_target_command(managed, target)
                console.print(read_text(managed.target_command_path(target)))
        elif choice == "18":
            delete_selected_target_artifacts(managed)
        elif choice == "19":
            console.print(str(managed.run_dir))
        elif choice == "20":
            if delete_run(managed):
                return
        elif choice in {"b", "back"}:
            return


def show_run_list() -> None:
    runs = list_runs()
    if not runs:
        console.print("[dim]No managed runs yet.[/dim]")
        return
    table = Table(title="Managed Runs")
    table.add_column("#", justify="right")
    table.add_column("Run id")
    table.add_column("Difficulty")
    table.add_column("Targets", justify="right")
    table.add_column("Done", justify="right")
    table.add_column("Partial", justify="right")
    table.add_column("Running", justify="right")
    for index, managed in enumerate(runs, start=1):
        statuses = [target_status(managed, target) for target in managed.config.targets]
        table.add_row(
            str(index),
            managed.config.run_id,
            managed.config.difficulty or "all",
            str(len(statuses)),
            str(sum(1 for status in statuses if status == "complete")),
            str(sum(1 for status in statuses if status in {"partial", "paused"})),
            str(sum(1 for status in statuses if status == "running")),
        )
    console.print(table)


def choose_managed_run(prompt: str) -> ManagedRun | None:
    runs = list_runs()
    if not runs:
        console.print("[dim]No managed runs yet.[/dim]")
        return None
    show_run_list()
    raw = Prompt.ask(f"{prompt} by run id or #").strip()
    if raw.isdigit():
        index = int(raw)
        if 1 <= index <= len(runs):
            return runs[index - 1]
    try:
        return load_run(raw)
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as exc:
        console.print(f"[red]Could not load run:[/red] {exc}")
        return None


def show_dashboard(managed: ManagedRun) -> None:
    state = load_state(managed)
    pause_status = "present" if managed.pause_file.exists() else "clear"
    active = active_status_text(state, pause_requested=managed.pause_file.exists())
    heartbeat = heartbeat_status_text(managed)
    console.print(
        Panel(
            f"folder: {managed.run_dir}\n"
            f"difficulty: {managed.config.difficulty or 'all'}\n"
            f"queue: {queue_status_text(managed)}\n"
            f"pause file: {pause_status}\n"
            f"active: {active}\n"
            f"heartbeat: {heartbeat}",
            title="State",
        )
    )
    table = Table(title="Targets")
    table.add_column("#", justify="right")
    table.add_column("Q", justify="right")
    table.add_column("Status")
    table.add_column("Baseline")
    table.add_column("Model")
    table.add_column("Done", justify="right")
    table.add_column("Score", justify="right")
    table.add_column("Success", justify="right")
    table.add_column("Evidence", justify="right")
    table.add_column("Errors", justify="right")
    queue_positions = queued_position_map(managed)
    for index, target in enumerate(managed.config.targets, start=1):
        result = load_result(managed.target_output_path(target))
        status = target_status(managed, target)
        records = records_count(result)
        expected = expected_records(managed, target)
        row = mark_row_or_none(managed, result)
        score = "-" if row is None else f"{row['score']:.1f}"
        metrics = {} if row is None else cast(dict[str, float], row["metrics"])
        success = "-" if row is None else f"{metrics['success_rate']:.2f}"
        evidence = "-" if row is None else f"{metrics['evidence_coverage']:.2f}"
        errors = "-" if row is None else str(row["agent_error_count"] or 0)
        table.add_row(
            str(index),
            queue_positions.get(target.key, "-"),
            status_label(status),
            target.baseline,
            target.label,
            f"{records}/{expected}",
            score,
            success,
            evidence,
            errors,
        )
    console.print(table)


def status_label(status: RunStatus) -> str:
    styles = {
        "pending": "[dim]pending[/dim]",
        "partial": "[yellow]partial[/yellow]",
        "paused": "[yellow]paused[/yellow]",
        "complete": "[green]complete[/green]",
        "error": "[red]error[/red]",
        "running": "[cyan]running[/cyan]",
    }
    return styles[status]


def select_targets_checklist(
    managed: ManagedRun,
    *,
    title: str,
    preselected: set[str] | None = None,
    candidates: list[RunTarget] | None = None,
) -> list[RunTarget]:
    target_pool = candidates if candidates is not None else managed.config.targets
    selected = set(preselected or set())
    filter_text = ""
    page = 0
    while True:
        visible = filtered_targets(target_pool, filter_text)
        page_count = max(1, (len(visible) + 14) // 15)
        page = min(page, page_count - 1)
        visible_page = visible[page * 15 : page * 15 + 15]
        render_target_checklist(
            managed=managed,
            title=title,
            candidates=visible_page,
            selected=selected,
            filter_text=filter_text,
            page=page,
            page_count=page_count,
        )
        command = Prompt.ask(
            "Rows/ranges, select/drop rows, or search/all/none/next/prev/done/cancel",
            default="done",
        ).strip()
        lowered = command.lower()
        if lowered in {"done", "d"}:
            return [target for target in target_pool if target.key in selected]
        if lowered in {"cancel", "q"}:
            return []
        if lowered in {"next", "n"}:
            page = min(page + 1, page_count - 1)
            continue
        if lowered in {"prev", "p"}:
            page = max(0, page - 1)
            continue
        if lowered in {"search", "s", "/"}:
            filter_text = Prompt.ask("Filter text", default="").strip()
            page = 0
            continue
        if lowered in {"clear-filter", "cf"}:
            filter_text = ""
            page = 0
            continue
        if lowered in {"all", "a"}:
            selected.update(target.key for target in visible_page)
            continue
        if lowered in {"none", "u"}:
            selected.difference_update(target.key for target in visible_page)
            continue
        if lowered in {"clear", "c"}:
            selected.clear()
            continue

        mode, index_text = parse_checklist_selection_command(command)
        indexes = parse_checklist_indexes(index_text, max_index=len(visible_page))
        if not indexes:
            console.print("[yellow]No valid target rows matched that input.[/yellow]")
            continue
        for index in indexes:
            target = visible_page[index - 1]
            if mode == "select":
                selected.add(target.key)
            elif mode == "drop":
                selected.discard(target.key)
            elif target.key in selected:
                selected.remove(target.key)
            else:
                selected.add(target.key)


def filtered_targets(targets: list[RunTarget], filter_text: str) -> list[RunTarget]:
    if not filter_text:
        return targets
    lowered = filter_text.lower()
    return [
        target
        for target in targets
        if lowered in target.baseline.lower() or lowered in target.label.lower()
    ]


def render_target_checklist(
    *,
    managed: ManagedRun,
    title: str,
    candidates: list[RunTarget],
    selected: set[str],
    filter_text: str,
    page: int,
    page_count: int,
) -> None:
    table = Table(
        title=(
            f"{title} "
            f"(selected={len(selected)}, filter={filter_text or 'none'}, "
            f"page={page + 1}/{page_count})"
        )
    )
    table.add_column("#", justify="right")
    table.add_column("Use", justify="center")
    table.add_column("Status")
    table.add_column("Baseline")
    table.add_column("Model")
    table.add_column("Done", justify="right")
    if not candidates:
        table.add_row("-", "-", "-", "-", "[dim]No targets match the current filter.[/dim]", "-")
    for index, target in enumerate(candidates, start=1):
        result = load_result(managed.target_output_path(target))
        table.add_row(
            str(index),
            checkbox(target.key in selected),
            status_label(target_status(managed, target)),
            target.baseline,
            target.label,
            f"{records_count(result)}/{expected_records(managed, target)}",
        )
    console.print(table)


def manage_queue(managed: ManagedRun) -> None:
    while True:
        show_queue(managed)
        console.print(
            Panel(
                "1. Add selected targets to queue\n"
                "2. Replace queue from checklist\n"
                "3. Remove targets from queue\n"
                "4. Move queued target\n"
                "5. Clear queue\n"
                "6. Export queue script\n"
                "7. Play full queue\n"
                "8. Play next queued target only\n"
                "9. Play N queued targets\n"
                "b. Back",
                title="Queue Menu",
            )
        )
        choice = Prompt.ask("Choose", default="1").strip().lower()
        if choice == "1":
            selected = select_targets_checklist(managed, title="Add Targets To Queue")
            if selected:
                added = append_targets_to_queue(managed, selected)
                console.print(f"[green]Added {added} target(s) to queue.[/green]")
        elif choice == "2":
            selected = select_targets_checklist(
                managed,
                title="Replace Queue",
                preselected=set(load_queue(managed)),
            )
            save_queue(managed, [target.key for target in selected])
            console.print(f"[green]Queue now has {len(selected)} target(s).[/green]")
        elif choice == "3":
            queued = queue_targets(managed)
            selected = select_targets_checklist(
                managed,
                title="Remove From Queue",
                candidates=queued,
            )
            if selected:
                removed = remove_targets_from_queue(managed, selected)
                console.print(f"[yellow]Removed {removed} target(s) from queue.[/yellow]")
        elif choice == "4":
            move_queued_target(managed)
        elif choice == "5":
            if Confirm.ask("Clear the managed queue?", default=False):
                clear_queue(managed)
                console.print("[yellow]Queue cleared.[/yellow]")
        elif choice == "6":
            queued = queue_targets(managed)
            if not queued:
                console.print("[yellow]Queue is empty.[/yellow]")
                continue
            queue_path = write_queue_script(managed, queued)
            console.print(f"[green]Wrote queue script[/green] {queue_path}")
        elif choice == "7":
            play_queue(managed)
        elif choice == "8":
            play_queue(managed, max_targets=1)
        elif choice == "9":
            max_targets = IntPrompt.ask("Queued targets to play", default=1)
            if max_targets > 0:
                play_queue(managed, max_targets=max_targets)
        elif choice in {"b", "back", "q"}:
            return


def show_queue(managed: ManagedRun) -> None:
    queued = queue_targets(managed)
    table = Table(title=f"Managed Queue: {queue_status_text(managed)}")
    table.add_column("Q", justify="right")
    table.add_column("Status")
    table.add_column("Baseline")
    table.add_column("Model")
    table.add_column("Done", justify="right")
    if not queued:
        table.add_row("-", "-", "-", "[dim]Queue is empty.[/dim]", "-")
    for index, target in enumerate(queued, start=1):
        result = load_result(managed.target_output_path(target))
        table.add_row(
            str(index),
            status_label(target_status(managed, target)),
            target.baseline,
            target.label,
            f"{records_count(result)}/{expected_records(managed, target)}",
        )
    console.print(table)


def play_queue(managed: ManagedRun, *, max_targets: int | None = None) -> None:
    if state_pid_is_running(load_state(managed)):
        console.print("[yellow]A managed target is already running.[/yellow]")
        return
    prune_completed_queue(managed)
    if not queue_targets(managed):
        console.print("[yellow]Queue is empty. Add targets from Queue manager first.[/yellow]")
        return
    if managed.pause_file.exists():
        if Confirm.ask("Pause flag exists. Remove it before playing queue?", default=True):
            clear_pause(managed)
        else:
            return

    launched = 0
    while max_targets is None or launched < max_targets:
        prune_completed_queue(managed)
        target = next_queued_target(managed)
        if target is None:
            console.print("[green]No queued runnable targets remain.[/green]")
            return

        launch_target(managed, target, watch=False)
        launched += 1
        watch_run_live(managed, target=target, exit_when_inactive=True)
        refresh_state_if_needed(managed)

        if active_target(managed) is not None:
            console.print("[yellow]Queue paused because a target is still running.[/yellow]")
            return

        status = target_status(managed, target)
        if status == "complete":
            remove_targets_from_queue(managed, [target])
            console.print(
                f"[green]Completed and dequeued[/green] {target.baseline} | {target.label}"
            )
            if managed.pause_file.exists():
                console.print("[yellow]Pause flag is set; queue playback stopped.[/yellow]")
                return
            continue
        if status == "error":
            console.print(
                f"[red]Queued target ended with an error:[/red] "
                f"{target.baseline} | {target.label}"
            )
            return
        console.print(
            f"[yellow]Queue stopped with target status {status}:[/yellow] "
            f"{target.baseline} | {target.label}"
        )
        return


def load_queue(managed: ManagedRun) -> list[str]:
    if not managed.queue_path.exists():
        return []
    try:
        data = json.loads(managed.queue_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    raw_keys: object = data.get("target_keys", []) if isinstance(data, dict) else data
    if not isinstance(raw_keys, list):
        return []
    keys = [key for key in raw_keys if isinstance(key, str)]
    return normalize_queue_keys(managed, keys)


def save_queue(managed: ManagedRun, target_keys: Iterable[str]) -> list[str]:
    managed.run_dir.mkdir(parents=True, exist_ok=True)
    keys = normalize_queue_keys(managed, target_keys)
    payload = {
        "schema_version": 1,
        "updated_at": datetime.now(UTC).isoformat(),
        "target_keys": keys,
    }
    managed.queue_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return keys


def clear_queue(managed: ManagedRun) -> None:
    if managed.queue_path.exists():
        managed.queue_path.unlink()


def normalize_queue_keys(managed: ManagedRun, target_keys: Iterable[str]) -> list[str]:
    known_keys = {target.key for target in managed.config.targets}
    normalized: list[str] = []
    seen: set[str] = set()
    for key in target_keys:
        if key in known_keys and key not in seen:
            normalized.append(key)
            seen.add(key)
    return normalized


def queue_targets(managed: ManagedRun) -> list[RunTarget]:
    by_key = {target.key: target for target in managed.config.targets}
    return [by_key[key] for key in load_queue(managed) if key in by_key]


def queued_position_map(managed: ManagedRun) -> dict[str, str]:
    return {target.key: str(index) for index, target in enumerate(queue_targets(managed), start=1)}


def queue_status_text(managed: ManagedRun) -> str:
    queued = queue_targets(managed)
    if not queued:
        return "empty"
    complete = sum(1 for target in queued if target_status(managed, target) == "complete")
    runnable = len(queued) - complete
    next_target = next_queued_target(managed)
    next_text = "none" if next_target is None else f"{next_target.baseline} | {next_target.label}"
    return f"{len(queued)} queued, {runnable} remaining, next: {next_text}"


def next_queued_target(managed: ManagedRun) -> RunTarget | None:
    for target in queue_targets(managed):
        if target_status(managed, target) != "complete":
            return target
    return None


def prune_completed_queue(managed: ManagedRun) -> int:
    complete = [
        target
        for target in queue_targets(managed)
        if target_status(managed, target) == "complete"
    ]
    if not complete:
        return 0
    return remove_targets_from_queue(managed, complete)


def append_targets_to_queue(managed: ManagedRun, targets: Iterable[RunTarget]) -> int:
    existing = load_queue(managed)
    before = set(existing)
    saved = save_queue(managed, [*existing, *(target.key for target in targets)])
    return sum(1 for key in saved if key not in before)


def remove_targets_from_queue(managed: ManagedRun, targets: Iterable[RunTarget]) -> int:
    remove_keys = {target.key for target in targets}
    existing = load_queue(managed)
    kept = [key for key in existing if key not in remove_keys]
    save_queue(managed, kept)
    return len(existing) - len(kept)


def move_queued_target(managed: ManagedRun) -> None:
    queued = queue_targets(managed)
    if len(queued) < 2:
        console.print("[yellow]Queue needs at least two targets to reorder.[/yellow]")
        return
    source = IntPrompt.ask("Move queue position", default=1)
    if source < 1 or source > len(queued):
        console.print("[red]Invalid queue position.[/red]")
        return
    destination = IntPrompt.ask("New queue position", default=1)
    destination = max(1, min(destination, len(queued)))
    keys = [target.key for target in queued]
    key = keys.pop(source - 1)
    keys.insert(destination - 1, key)
    save_queue(managed, keys)
    console.print(f"[green]Moved queued target {source} -> {destination}.[/green]")


def add_targets_to_run(managed: ManagedRun) -> ManagedRun:
    baselines = choose_baselines("open_source,open_source_react,guided_open_source")
    new_targets = choose_targets(baselines)
    if not new_targets:
        console.print("[yellow]No targets selected.[/yellow]")
        return managed
    existing_keys = {target.key for target in managed.config.targets}
    additions = [target for target in new_targets if target.key not in existing_keys]
    if not additions:
        console.print("[yellow]All selected targets already exist in this run.[/yellow]")
        return managed
    updated = update_run_targets(managed, [*managed.config.targets, *additions])
    write_all_target_commands(updated)
    console.print(f"[green]Added {len(additions)} target(s).[/green]")
    return updated


def remove_targets_from_run(managed: ManagedRun) -> ManagedRun:
    selected = select_targets_checklist(managed, title="Remove Targets")
    if not selected:
        return managed
    running_keys = {
        target.key for target in selected if target_status(managed, target) == "running"
    }
    if running_keys:
        console.print("[red]Cannot remove a running target. Pause/stop it first.[/red]")
        return managed
    if not Confirm.ask(f"Remove {len(selected)} target(s) from run config?", default=False):
        return managed
    remove_keys = {target.key for target in selected}
    kept = [target for target in managed.config.targets if target.key not in remove_keys]
    updated = update_run_targets(managed, kept)
    if load_queue(managed):
        save_queue(updated, load_queue(managed))
    console.print(
        "[yellow]Removed target definitions. Existing output files were left in place.[/yellow]"
    )
    return updated


def delete_selected_target_artifacts(managed: ManagedRun) -> None:
    selected = select_targets_checklist(managed, title="Delete Target Artifacts")
    if not selected:
        return
    running_keys = {
        target.key for target in selected if target_status(managed, target) == "running"
    }
    if running_keys:
        console.print("[red]Cannot delete artifacts for a running target.[/red]")
        return
    if not Confirm.ask(
        f"Delete output/log/summary files for {len(selected)} target(s)?",
        default=False,
    ):
        return
    deleted = delete_target_artifact_files(managed, selected)
    console.print(f"[yellow]Deleted {deleted} artifact file(s).[/yellow]")


def rerun_one_target(managed: ManagedRun) -> None:
    target = select_target(managed)
    if target is None:
        return
    state = load_state(managed)
    if state_pid_is_running(state):
        active = active_target(managed)
        if active is not None and active.key == target.key:
            console.print(
                "[red]That target is already running. Use pause+stop now before rerun.[/red]"
            )
        else:
            console.print("[yellow]A managed target is already running.[/yellow]")
        return
    result = load_result(managed.target_output_path(target))
    records = records_count(result)
    console.print(
        Panel(
            f"target: {target.baseline} | {target.label}\n"
            f"status: {target_status(managed, target)}\n"
            f"records: {records}/{expected_records(managed, target)}\n"
            "Rerun deletes this target's output, summary, and logs, then starts fresh.",
            title="Rerun Target",
        )
    )
    if not Confirm.ask("Rerun this target from scratch?", default=False):
        return
    deleted = delete_target_artifact_files(managed, [target])
    console.print(f"[yellow]Deleted {deleted} existing artifact file(s).[/yellow]")
    launch_target(managed, target)


def run_target_task_range(managed: ManagedRun) -> None:
    target = select_target(managed)
    if target is None:
        return
    if state_pid_is_running(load_state(managed)):
        console.print("[yellow]A managed target is already running.[/yellow]")
        return
    all_tasks = list_task_ids(difficulty=cast(Difficulty | None, managed.config.difficulty))
    console.print(f"Task range is 1-{len(all_tasks)} for this run's filters.")
    raw_range = Prompt.ask("Task range, for example 1-10 or 17", default="1").strip()
    try:
        task_ids = resolve_task_ids(
            difficulty=cast(Difficulty | None, managed.config.difficulty),
            split=None,
            task_ids=None,
            task_range=raw_range,
        )
    except (TypeError, ValueError) as exc:
        console.print(f"[red]Invalid task range:[/red] {exc}")
        return
    console.print(Panel(describe_task_selection(task_ids), title="Task Range"))
    if Confirm.ask("Delete existing records for this task range before launch?", default=False):
        removed = rewrite_result_without_task_ids(managed.target_output_path(target), set(task_ids))
        console.print(f"[yellow]Removed {removed} existing record(s) for this range.[/yellow]")
    launch_target(managed, target, task_ids=task_ids)


def rerun_errored_tasks(managed: ManagedRun) -> None:
    target = select_target(managed)
    if target is None:
        return
    if state_pid_is_running(load_state(managed)):
        console.print("[yellow]A managed target is already running.[/yellow]")
        return
    result = load_result(managed.target_output_path(target))
    if result is None:
        console.print("[yellow]No result file exists for that target yet.[/yellow]")
        return
    task_ids = repair_task_ids(managed, target, result)
    if not task_ids:
        console.print("[green]No errored or missing task records found for that target.[/green]")
        return
    console.print(Panel(describe_task_selection(task_ids), title="Errored/Missing Tasks"))
    if not Confirm.ask(f"Rerun {len(task_ids)} errored/missing task(s)?", default=True):
        return
    removed = rewrite_result_without_task_ids(managed.target_output_path(target), set(task_ids))
    console.print(f"[yellow]Removed {removed} existing record(s) before repair rerun.[/yellow]")
    launch_target(managed, target, task_ids=task_ids)


def errored_task_ids(result: dict[str, Any]) -> list[str]:
    records = result.get("records")
    if not isinstance(records, list):
        return []
    task_ids: list[str] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        task_id = record.get("task_id")
        if isinstance(task_id, str) and record.get("agent_error") and task_id not in task_ids:
            task_ids.append(task_id)
    return task_ids


def repair_task_ids(
    managed: ManagedRun,
    target: RunTarget,
    result: dict[str, Any],
) -> list[str]:
    task_ids = expected_task_ids_for_result(managed, result)
    episodes = (
        managed.config.deterministic_episodes
        if target.baseline in DETERMINISTIC_BASELINES
        else managed.config.llm_episodes
    )
    expected_keys = expected_episode_keys_for_tasks(
        seed=managed.config.seed,
        episodes=episodes,
        difficulty=managed.config.difficulty,
        task_ids=task_ids,
    )
    completed_keys = completed_episode_keys(result)
    errored = set(errored_task_ids(result))
    missing = {
        task_id
        for task_id in task_ids
        if any(
            (task_id, expected_seed) not in completed_keys
            for expected_seed in expected_keys[task_id]
        )
    }
    needs_repair = errored | missing
    return [task_id for task_id in task_ids if task_id in needs_repair]


def expected_task_ids_for_result(
    managed: ManagedRun,
    result: dict[str, Any],
) -> list[str]:
    filtered = result.get("filtered_task_ids")
    if isinstance(filtered, list) and all(isinstance(task_id, str) for task_id in filtered):
        return list(cast(list[str], filtered))
    task_ids = result.get("task_ids")
    if isinstance(task_ids, list) and all(isinstance(task_id, str) for task_id in task_ids):
        return list(cast(list[str], task_ids))
    return list_task_ids(difficulty=cast(Difficulty | None, managed.config.difficulty))


def completed_episode_keys(result: dict[str, Any]) -> set[tuple[str, int]]:
    records = result.get("records")
    if not isinstance(records, list):
        return set()
    completed: set[tuple[str, int]] = set()
    for record in records:
        if not isinstance(record, dict):
            continue
        task_id = record.get("task_id")
        seed = record.get("seed")
        if isinstance(task_id, str) and isinstance(seed, int):
            completed.add((task_id, seed))
    return completed


def expected_episode_keys_for_tasks(
    *,
    seed: int,
    episodes: int,
    difficulty: str | None,
    task_ids: list[str],
) -> dict[str, set[int]]:
    all_task_ids = list_task_ids(difficulty=cast(Difficulty | None, difficulty))
    task_seed_indexes = {task_id: index for index, task_id in enumerate(all_task_ids)}
    return {
        task_id: {
            seed + task_seed_indexes[task_id] * 10_000 + episode_index
            for episode_index in range(episodes)
        }
        for task_id in task_ids
    }


def rewrite_result_without_task_ids(path: Path, task_ids: set[str]) -> int:
    result = load_result(path)
    if result is None:
        return 0
    records = result.get("records")
    if not isinstance(records, list):
        return 0
    kept_records = [
        record
        for record in records
        if not (isinstance(record, dict) and record.get("task_id") in task_ids)
    ]
    removed = len(records) - len(kept_records)
    if removed <= 0:
        return 0
    result["records"] = kept_records
    result["completed_task_episodes"] = len(kept_records)
    result["complete"] = False
    result["paused"] = False
    result.pop("run_error", None)
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return removed


def describe_task_selection(task_ids: list[str], *, limit: int = 12) -> str:
    shown = task_ids[:limit]
    suffix = "" if len(task_ids) <= limit else f"\n... {len(task_ids) - limit} more"
    return "\n".join(f"{index}. {task_id}" for index, task_id in enumerate(shown, start=1)) + suffix


def delete_target_artifact_files(
    managed: ManagedRun,
    targets: Iterable[RunTarget],
) -> int:
    deleted = 0
    for target in targets:
        for path in target_artifact_paths(managed, target):
            assert_path_within(path, managed.run_dir)
            if path.is_file():
                path.unlink()
                deleted += 1
    return deleted


def target_artifact_paths(managed: ManagedRun, target: RunTarget) -> list[Path]:
    return [
        managed.target_output_path(target),
        managed.target_summary_path(target),
        managed.target_log_path(target),
        managed.target_console_log_path(target),
    ]


def delete_run(managed: ManagedRun) -> bool:
    refresh_state_if_needed(managed)
    state = load_state(managed)
    if state_pid_is_running(state):
        console.print("[red]Cannot delete a run with an active process. Stop it first.[/red]")
        return False
    if not is_safe_managed_run_dir(managed.run_dir):
        console.print(f"[red]Refusing to delete unexpected path:[/red] {managed.run_dir}")
        return False
    console.print(
        Panel(
            f"run id: {managed.config.run_id}\n"
            f"folder: {managed.run_dir}\n"
            "This removes outputs, logs, summaries, commands, pause file, and config.",
            title="Delete Run",
        )
    )
    if not Confirm.ask("Delete this managed run?", default=False):
        return False
    confirmation = Prompt.ask("Type the run id to confirm", default="").strip()
    if confirmation != managed.config.run_id:
        console.print("[yellow]Run deletion cancelled.[/yellow]")
        return False
    delete_managed_run_directory(managed)
    console.print(f"[yellow]Deleted managed run[/yellow] {managed.config.run_id}")
    return True


def delete_managed_run_directory(
    managed: ManagedRun,
    *,
    root: Path | None = None,
) -> None:
    if not is_safe_managed_run_dir(managed.run_dir, root=root):
        raise ValueError(f"Refusing to delete unexpected path: {managed.run_dir}")
    if managed.run_dir.exists():
        shutil.rmtree(managed.run_dir)


def is_safe_managed_run_dir(run_dir: Path, *, root: Path | None = None) -> bool:
    managed_runs_root = (root or managed_root()).resolve(strict=False)
    resolved_run_dir = run_dir.resolve(strict=False)
    return resolved_run_dir.parent == managed_runs_root and resolved_run_dir.name not in {
        "",
        ".",
        "..",
    }


def assert_path_within(path: Path, root: Path) -> None:
    resolved_path = path.resolve(strict=False)
    resolved_root = root.resolve(strict=False)
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"Refusing to delete path outside run directory: {path}") from exc


def update_run_targets(managed: ManagedRun, targets: list[RunTarget]) -> ManagedRun:
    updated = ManagedRun(
        config=replace(managed.config, targets=targets),
        run_dir=managed.run_dir,
    )
    save_run(updated)
    return updated


def launch_target(
    managed: ManagedRun,
    target: RunTarget,
    *,
    watch: bool = True,
    task_ids: list[str] | None = None,
) -> None:
    state = load_state(managed)
    if state_pid_is_running(state):
        console.print("[yellow]A managed target is already running.[/yellow]")
        return
    if managed.pause_file.exists():
        if Confirm.ask("Pause flag exists. Remove it before launch?", default=True):
            clear_pause(managed)
        else:
            return

    for directory in (
        managed.output_dir,
        managed.logs_dir,
        managed.summaries_dir,
        managed.commands_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    command = build_target_command(managed, target, task_ids=task_ids)
    if task_ids is None:
        write_target_command(managed, target)
    else:
        write_target_command(managed, target, task_ids=task_ids)
    console_log = managed.target_console_log_path(target)
    with console_log.open("ab") as output:
        process = subprocess.Popen(  # noqa: S603
            command,
            cwd=ROOT,
            stdout=output,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )
    save_state(
        managed,
        {
            "pid": process.pid,
            "target_key": target.key,
            "baseline": target.baseline,
            "model": target.model,
            "started_at": datetime.now(UTC).isoformat(),
            "command": command,
            "console_log": str(console_log),
        },
    )
    console.print(f"[green]Started[/green] {target.baseline} | {target.label} pid={process.pid}")
    if task_ids is not None:
        console.print(f"Task filter: {len(task_ids)} task(s)")
    console.print(f"Console log: {console_log}")
    if watch:
        watch_run_live(managed, target=target, exit_when_inactive=True)


def build_target_command(
    managed: ManagedRun,
    target: RunTarget,
    *,
    task_ids: list[str] | None = None,
) -> list[str]:
    config = managed.config
    command = [
        sys.executable,
        str(ROOT / "eval" / "run_all_eval.py"),
        "--resume",
        "--pause-file",
        str(managed.pause_file),
        "--only-baselines",
        target.baseline,
        "--seed",
        str(config.seed),
        "--target-steps",
        str(config.target_steps),
        "--output-dir",
        str(managed.output_dir),
        "--summary-output",
        str(managed.target_summary_path(target)),
        "--log-file",
        str(managed.target_log_path(target)),
    ]
    if config.difficulty is not None:
        command.extend(["--difficulty", config.difficulty])
    if task_ids:
        command.append("--task-ids")
        command.extend(task_ids)
    if target.baseline in DETERMINISTIC_BASELINES:
        command.extend(["--deterministic-episodes", str(config.deterministic_episodes)])
        command.append("--skip-llm")
        return command

    if target.model is None:
        raise ValueError(f"LLM target {target.baseline!r} requires a model.")
    command.extend(
        [
            "--skip-deterministic",
            "--llm-episodes",
            str(config.llm_episodes),
            "--timeout-seconds",
            str(config.timeout_seconds),
            "--llm-max-tokens",
            str(config.llm_max_tokens),
            "--llm-max-retries",
            str(config.llm_max_retries),
            "--llm-min-request-interval-seconds",
            str(config.llm_min_request_interval_seconds),
            "--llm-rate-limit-requests",
            str(config.llm_rate_limit_requests),
            "--llm-rate-limit-window-seconds",
            str(config.llm_rate_limit_window_seconds),
            "--llm-rejection-pause-threshold",
            str(config.llm_rejection_pause_threshold),
            "--llm-rejection-pause-seconds",
            str(config.llm_rejection_pause_seconds),
            "--llm-reasoning-exclude"
            if config.llm_reasoning_exclude
            else "--no-llm-reasoning-exclude",
            "--llm-qwen-no-think" if config.llm_qwen_no_think else "--no-llm-qwen-no-think",
            MODEL_ARG_BY_BASELINE[target.baseline],
            target.model,
        ]
    )
    return command


def write_queue_script(managed: ManagedRun, targets: list[RunTarget]) -> Path:
    managed.commands_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    path = managed.commands_dir / f"queue_{timestamp}.ps1"
    blocks = [
        "# SRE-Zero managed queue",
        f"# run_id: {managed.config.run_id}",
        f"# generated_at: {datetime.now(UTC).isoformat()}",
        (
            "Remove-Item "
            + quote_powershell_arg(str(managed.pause_file))
            + " -ErrorAction SilentlyContinue"
        ),
        "",
    ]
    for target in targets:
        blocks.append(f"# Target: {target.baseline} | {target.label}")
        blocks.append(powershell_command(build_target_command(managed, target)).rstrip())
        blocks.append("")
    path.write_text("\n".join(blocks), encoding="utf-8")
    return path


def pause_run(managed: ManagedRun) -> None:
    managed.pause_file.parent.mkdir(parents=True, exist_ok=True)
    managed.pause_file.write_text(
        f"pause requested at {datetime.now(UTC).isoformat()}\n",
        encoding="utf-8",
    )
    console.print(f"[yellow]Pause requested:[/yellow] {managed.pause_file}")
    if active_target(managed) is not None:
        console.print(
            "[yellow]This is cooperative: the child exits after the current "
            "task/episode finishes and before the next one starts. "
            "Use pause+stop for an immediate halt.[/yellow]"
        )


def clear_pause(managed: ManagedRun) -> None:
    if managed.pause_file.exists():
        managed.pause_file.unlink()
    console.print("[green]Pause flag clear.[/green]")


def stop_active_process(
    managed: ManagedRun,
    *,
    confirm: bool = True,
    force: bool = False,
) -> bool:
    state = load_state(managed)
    pid = state.get("pid")
    if not isinstance(pid, int) or not is_pid_running(pid):
        console.print("[yellow]No active managed process found.[/yellow]")
        return False
    pause_run(managed)
    if confirm and not Confirm.ask(f"Stop active process pid={pid}?", default=False):
        return False
    if os.name == "nt":
        command = ["taskkill", "/PID", str(pid), "/T"]
        if force:
            command.append("/F")
        subprocess.run(  # noqa: S603
            command,
            check=False,
        )
    else:
        os.kill(pid, signal.SIGTERM)
    state["stopped_at"] = datetime.now(UTC).isoformat()
    save_state(managed, state)
    console.print("[yellow]Stop requested. Partial target JSON remains resumable.[/yellow]")
    return True


def next_runnable_target(managed: ManagedRun) -> RunTarget | None:
    for target in managed.config.targets:
        if target_status(managed, target) in {"partial", "paused"}:
            return target
    for target in managed.config.targets:
        if target_status(managed, target) in {"pending", "error"}:
            return target
    return None


def select_target(managed: ManagedRun) -> RunTarget | None:
    index = IntPrompt.ask("Target number", default=1)
    if index < 1 or index > len(managed.config.targets):
        console.print("[red]Invalid target number.[/red]")
        return None
    return managed.config.targets[index - 1]


def show_target_details(managed: ManagedRun, target: RunTarget) -> None:
    result = load_result(managed.target_output_path(target))
    row = mark_row_or_none(managed, result)
    metrics = {} if row is None else cast(dict[str, float], row["metrics"])
    details = Table(title=f"Target Details: {target.baseline} | {target.label}")
    details.add_column("Field")
    details.add_column("Value")
    details.add_row("status", target_status(managed, target))
    details.add_row("records", f"{records_count(result)}/{expected_records(managed, target)}")
    details.add_row("output", str(managed.target_output_path(target)))
    details.add_row("run log", str(managed.target_log_path(target)))
    details.add_row("console log", str(managed.target_console_log_path(target)))
    details.add_row("command", str(managed.target_command_path(target)))
    if row is not None:
        details.add_row("score", f"{row['score']:.3f}")
        details.add_row("success", f"{metrics['success_rate']:.3f}")
        details.add_row("reward", f"{metrics['mean_reward']:.3f}")
        details.add_row("evidence", f"{metrics['evidence_coverage']:.3f}")
        details.add_row("invalid", f"{metrics['invalid_action_rate']:.3f}")
        details.add_row("agent errors", str(row["agent_error_count"]))
    if result is not None and result.get("run_error"):
        details.add_row("run error", str(result["run_error"]))
    console.print(details)
    if result is not None:
        agent_errors = recent_agent_errors(result, limit=5)
        if agent_errors:
            console.print(Panel("\n".join(agent_errors), title="Recent Agent Errors"))


def recent_agent_errors(result: dict[str, Any], *, limit: int) -> list[str]:
    records = result.get("records")
    if not isinstance(records, list):
        return []
    errors: list[str] = []
    for record in reversed(records):
        if not isinstance(record, dict):
            continue
        task_id = record.get("task_id")
        error = record.get("agent_error")
        if isinstance(task_id, str) and isinstance(error, str):
            errors.append(f"{task_id}: {error}")
        if len(errors) >= limit:
            break
    return list(reversed(errors))


def target_status(managed: ManagedRun, target: RunTarget) -> RunStatus:
    state = load_state(managed)
    if state.get("target_key") == target.key and state_pid_is_running(state):
        return "running"
    result = load_result(managed.target_output_path(target))
    if result is None:
        return "pending"
    if result.get("run_error"):
        return "error"
    if result.get("paused"):
        return "paused"
    if result_is_complete(managed, target, result):
        return "complete"
    if records_count(result) > 0:
        return "partial"
    return "pending"


def result_is_complete(managed: ManagedRun, target: RunTarget, result: dict[str, Any]) -> bool:
    if result.get("complete") is True:
        return True
    expected = expected_records(managed, target)
    return records_count(result) >= expected


def expected_records(managed: ManagedRun, target: RunTarget) -> int:
    episodes = (
        managed.config.deterministic_episodes
        if target.baseline in DETERMINISTIC_BASELINES
        else managed.config.llm_episodes
    )
    task_ids = list_task_ids(difficulty=cast(Difficulty | None, managed.config.difficulty))
    return len(task_ids) * episodes


def rebuild_summary(managed: ManagedRun) -> None:
    runs: list[dict[str, Any]] = []
    mark_rows: list[dict[str, Any]] = []
    difficulty_mark_rows: list[dict[str, Any]] = []
    run_files: list[dict[str, str]] = []
    for target in managed.config.targets:
        path = managed.target_output_path(target)
        result = load_result(path)
        if result is None:
            continue
        runs.append(result)
        mark_rows.append(make_mark_row(result, target_steps=managed.config.target_steps))
        difficulty_mark_rows.extend(
            make_difficulty_mark_rows(result, target_steps=managed.config.target_steps)
        )
        run_files.append({"baseline": target.baseline, "model": target.label, "path": str(path)})
    mark_rows.sort(key=lambda row: row["score"], reverse=True)
    difficulty_mark_rows.sort(
        key=lambda row: (str(row["difficulty"]), -float(row["score"]))
    )
    summary = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "manager": "eval/run_tui.py",
        "run_id": managed.config.run_id,
        "config": managed.config.to_json(),
        "marks": {
            "rows": mark_rows,
            "by_model": group_marks_by_model(mark_rows),
            "by_baseline": group_marks_by_baseline(mark_rows),
            "pairwise_deltas": pairwise_deltas_by_baseline(mark_rows),
        },
        "difficulty_marks": {
            "rows": difficulty_mark_rows,
            "by_difficulty": group_marks_by_difficulty(difficulty_mark_rows),
        },
        "run_files": run_files,
        "runs": runs,
    }
    managed.summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    console.print(f"[green]Wrote summary[/green] {managed.summary_path}")


def write_all_target_commands(managed: ManagedRun) -> None:
    for target in managed.config.targets:
        write_target_command(managed, target)


def write_target_command(
    managed: ManagedRun,
    target: RunTarget,
    *,
    task_ids: list[str] | None = None,
) -> None:
    managed.commands_dir.mkdir(parents=True, exist_ok=True)
    command = build_target_command(managed, target, task_ids=task_ids)
    command_path = (
        managed.target_command_path(target)
        if task_ids is None
        else managed.commands_dir / f"{target.key}.task_filter.ps1"
    )
    command_path.write_text(
        powershell_command(command),
        encoding="utf-8",
    )


def powershell_command(command: list[str]) -> str:
    lines = []
    for index, part in enumerate(command):
        quoted = quote_powershell_arg(part)
        if index == 0:
            lines.append(quoted)
        else:
            lines.append(f"  {quoted}")
    return " `\n".join(lines) + "\n"


def quote_powershell_arg(value: str) -> str:
    if not value or any(char.isspace() for char in value) or "'" in value:
        return "'" + value.replace("'", "''") + "'"
    return value


def show_log_tail(managed: ManagedRun, target: RunTarget) -> None:
    for path in (managed.target_console_log_path(target), managed.target_log_path(target)):
        console.rule(str(path))
        if not path.exists():
            console.print("[dim]No log yet.[/dim]")
            continue
        lines = read_text(path).splitlines()[-80:]
        console.print("\n".join(lines) if lines else "[dim]Empty log.[/dim]")


def watch_run_live(
    managed: ManagedRun,
    *,
    target: RunTarget | None,
    exit_when_inactive: bool,
    refresh_seconds: float = 1.0,
) -> None:
    if not interactive_terminal():
        return
    selected_target = target
    saw_running = target is not None
    while True:
        refresh_state_if_needed(managed)
        current_active = active_target(managed)
        if current_active is not None:
            selected_target = current_active
            saw_running = True
        console.clear()
        console.rule(f"[bold]Live Run: {managed.config.run_id}")
        show_dashboard(managed)
        if selected_target is not None:
            render_stale_warning(managed, selected_target)
            render_live_log_tail(managed, selected_target, line_count=35)
        else:
            console.print("[dim]No active target. Press q to return.[/dim]")
        console.print(
            Panel(
                "q return | p pause after current task/episode | s pause+stop now | c clear pause",
                title="Live Controls",
            )
        )
        if exit_when_inactive and saw_running and active_target(managed) is None:
            console.print("[green]Target process has exited.[/green]")
            time.sleep(0.8)
            return
        key = read_key_or_none(refresh_seconds)
        if key is None:
            continue
        if key in {"q", "escape"}:
            return
        if key == "p":
            pause_run(managed)
        elif key == "s":
            stop_active_process(managed, confirm=True, force=True)
        elif key == "c":
            clear_pause(managed)


def render_stale_warning(managed: ManagedRun, target: RunTarget) -> None:
    age_seconds = last_log_update_age_seconds(managed, target)
    if age_seconds is None or age_seconds < STALE_PROCESS_SECONDS:
        return
    console.print(
        Panel(
            f"No run or console log update for {format_age(age_seconds)}.\n"
            "Use p to request a cooperative pause after the current task, "
            "or s to pause and stop the process now.",
            title="[red]Stale Process Warning[/red]",
        )
    )


def render_live_log_tail(
    managed: ManagedRun,
    target: RunTarget,
    *,
    line_count: int,
) -> None:
    for title, path in (
        ("Console Log", managed.target_console_log_path(target)),
        ("Run Log", managed.target_log_path(target)),
    ):
        lines = tail_lines(path, line_count)
        console.rule(f"{title}: {path.name}")
        if not lines:
            console.print("[dim]No log lines yet.[/dim]")
        else:
            console.print("\n".join(lines))


def tail_lines(path: Path, line_count: int) -> list[str]:
    if not path.exists():
        return []
    return read_text(path).splitlines()[-line_count:]


def save_run(managed: ManagedRun) -> None:
    for directory in (
        managed.run_dir,
        managed.output_dir,
        managed.logs_dir,
        managed.summaries_dir,
        managed.commands_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    managed.config_path.write_text(
        json.dumps(managed.config.to_json(), indent=2),
        encoding="utf-8",
    )


def load_run(run_id: str) -> ManagedRun:
    run_dir = managed_root() / run_id
    config_path = run_dir / "run.json"
    data = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Invalid run config: {config_path}")
    return ManagedRun(config=ManagedRunConfig.from_json(data), run_dir=run_dir)


def list_runs() -> list[ManagedRun]:
    root = managed_root()
    if not root.exists():
        return []
    runs: list[ManagedRun] = []
    for config_path in sorted(root.glob("*/run.json"), reverse=True):
        try:
            runs.append(load_run(config_path.parent.name))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    return runs


def managed_root() -> Path:
    return ROOT / "notes" / "runs" / "managed"


def load_state(managed: ManagedRun) -> dict[str, Any]:
    if not managed.state_path.exists():
        return {}
    try:
        data = json.loads(managed.state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if isinstance(data, dict):
        return data
    return {}


def save_state(managed: ManagedRun, state: dict[str, object]) -> None:
    managed.state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def refresh_state_if_needed(managed: ManagedRun) -> None:
    state = load_state(managed)
    if state and not state_pid_is_running(state):
        state["last_seen_stopped_at"] = datetime.now(UTC).isoformat()
        save_state(managed, state)


def active_target(managed: ManagedRun) -> RunTarget | None:
    state = load_state(managed)
    if not state_pid_is_running(state):
        return None
    target_key = state.get("target_key")
    if not isinstance(target_key, str):
        return None
    for target in managed.config.targets:
        if target.key == target_key:
            return target
    return None


def active_status_text(
    state: dict[str, Any],
    *,
    pause_requested: bool = False,
) -> str:
    pid = state.get("pid")
    target_key = state.get("target_key")
    if isinstance(pid, int) and state_pid_is_running(state):
        suffix = " (pause requested)" if pause_requested else ""
        return f"running pid={pid} target={target_key}{suffix}"
    if isinstance(pid, int):
        return f"not running last_pid={pid} target={target_key}"
    return "none"


def heartbeat_status_text(managed: ManagedRun) -> str:
    target = active_target(managed)
    if target is None:
        return "inactive"
    heartbeat = latest_task_heartbeat(managed, target)
    age_seconds = last_log_update_age_seconds(managed, target)
    age_text = "unknown" if age_seconds is None else format_age(age_seconds)
    stale = age_seconds is not None and age_seconds >= STALE_PROCESS_SECONDS
    stale_text = " [red]STALE[/red]" if stale else ""
    if heartbeat is None:
        return f"no task heartbeat yet, last log update {age_text}{stale_text}"
    return (
        f"{heartbeat['phase']} {heartbeat['task_id']} "
        f"task {heartbeat['task_index']}/{heartbeat['total_tasks']} "
        f"ep {heartbeat['episode_index']}/{heartbeat['total_episodes']}, "
        f"last log update {age_text}{stale_text}"
    )


def latest_task_heartbeat(managed: ManagedRun, target: RunTarget) -> dict[str, str] | None:
    path = managed.target_log_path(target)
    if not path.exists():
        return None
    pattern = re.compile(
        r"TASK (?P<phase>\w+) .*?task=(?P<task_id>\S+) "
        r"task_index=(?P<task_index>\d+)/(?:\s*)?(?P<total_tasks>\d+) "
        r"episode=(?P<episode_index>\d+)/(?:\s*)?(?P<total_episodes>\d+)"
    )
    for line in reversed(tail_lines(path, 300)):
        match = pattern.search(line)
        if match:
            return match.groupdict()
    return None


def last_log_update_age_seconds(managed: ManagedRun, target: RunTarget) -> float | None:
    mtimes = [
        path.stat().st_mtime
        for path in (managed.target_console_log_path(target), managed.target_log_path(target))
        if path.exists()
    ]
    if not mtimes:
        return None
    return max(0.0, time.time() - max(mtimes))


def format_age(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s ago"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.1f}m ago"
    return f"{minutes / 60:.1f}h ago"


def state_pid_is_running(state: dict[str, Any]) -> bool:
    pid = state.get("pid")
    if not isinstance(pid, int):
        return False
    return is_pid_running(pid)


def is_pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        result = subprocess.run(  # noqa: S603
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
            check=False,
        )
        return str(pid) in result.stdout
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def load_result(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if isinstance(data, dict):
        return data
    return None


def records_count(result: dict[str, Any] | None) -> int:
    if result is None:
        return 0
    records = result.get("records")
    if isinstance(records, list):
        return len(records)
    return 0


def mark_row_or_none(
    managed: ManagedRun,
    result: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if result is None:
        return None
    return make_mark_row(result, target_steps=managed.config.target_steps)


def load_available_model_slugs() -> list[str]:
    path = ROOT / "notes" / "available_models.md"
    if not path.exists():
        return []
    slugs: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        candidate = line.strip()
        if MODEL_SLUG_RE.match(candidate):
            slugs.append(candidate)
    return unique_items(slugs)


def safe_target_key(baseline: str, model: str | None) -> str:
    label = model if model is not None else f"deterministic/{baseline}"
    return safe_slug(f"{baseline}_{label}")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def unique_items(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        stripped = item.strip()
        if stripped and stripped not in seen:
            seen.add(stripped)
            result.append(stripped)
    return result


def required_str(data: dict[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value


def optional_str(data: dict[str, object], key: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string or null")
    return value


def required_int(data: dict[str, object], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    return value


def required_float(data: dict[str, object], key: str) -> float:
    value = data.get(key)
    if isinstance(value, int | float):
        return float(value)
    raise ValueError(f"{key} must be a number")


def int_or_default(data: dict[str, object], key: str, default: int) -> int:
    value = data.get(key)
    if value is None:
        return default
    if isinstance(value, int):
        return value
    raise ValueError(f"{key} must be an integer")


def bool_or_default(data: dict[str, object], key: str, default: bool) -> bool:
    value = data.get(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raise ValueError(f"{key} must be a boolean")


if __name__ == "__main__":
    main()
