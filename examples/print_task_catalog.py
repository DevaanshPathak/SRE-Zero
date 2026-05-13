"""Print the SRE-Zero Mini task catalog."""

from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from srezero.task_registry import task_catalog, task_splits  # noqa: E402


def main() -> None:
    table = Table(title="SRE-Zero Mini Task Catalog")
    table.add_column("Task")
    table.add_column("Difficulty")
    table.add_column("Alert")
    for task in task_catalog():
        table.add_row(task["task_id"], task["difficulty"], task["alert"])
    Console().print(table)
    Console().print(f"Splits: {task_splits()}")


if __name__ == "__main__":
    main()
