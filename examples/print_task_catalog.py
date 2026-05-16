"""Print the SRE-Zero Mini task catalog."""

from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from srezero.task_registry import benchmark_splits, task_catalog, task_splits  # noqa: E402


def main() -> None:
    table = Table(title="SRE-Zero Mini Task Catalog")
    table.add_column("Task")
    table.add_column("Difficulty")
    table.add_column("Split")
    table.add_column("Unseen")
    table.add_column("Alert")
    for task in task_catalog():
        table.add_row(
            task["task_id"],
            task["difficulty"],
            task["benchmark_split"],
            task["is_unseen_incident"],
            task["alert"],
        )
    Console().print(table)
    Console().print(f"Difficulty splits: {task_splits()}")
    Console().print(f"Benchmark splits: {benchmark_splits()}")


if __name__ == "__main__":
    main()
