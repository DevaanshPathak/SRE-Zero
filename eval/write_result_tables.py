"""Write paper-ready Markdown result tables from SRE-Zero JSON output."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from srezero.scoring import PAPER_METRIC_KEYS  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Write SRE-Zero result tables.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("notes/runs/baseline_blog_full/summary.json"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("notes/tables/latest"))
    args = parser.parse_args()

    input_path = repo_path(args.input)
    output_dir = repo_path(args.output_dir)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    rows = extract_rows(data)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "overall_results.md").write_text(overall_results_table(rows), encoding="utf-8")
    (output_dir / "paper_metrics.md").write_text(paper_metrics_table(rows), encoding="utf-8")
    (output_dir / "task_success.md").write_text(task_success_table(data), encoding="utf-8")
    print(f"Wrote result tables to {output_dir}")


def repo_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return ROOT / path


def extract_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    marks = data.get("marks")
    if isinstance(marks, dict) and isinstance(marks.get("rows"), list):
        return sorted(marks["rows"], key=lambda row: row.get("score", 0.0), reverse=True)

    score = data.get("score", {})
    result = data.get("result", {})
    if isinstance(score, dict) and isinstance(result, dict):
        return [
            {
                "baseline": result.get("agent", "unknown"),
                "model": result.get("model_override") or "default",
                "score": score.get("score", 0.0),
                "metrics": score.get("metrics", {}),
                "agent_error_count": 0,
            }
        ]
    return []


def overall_results_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| Rank | Baseline | Model | Marks | Success | Reward | Evidence | Invalid | Errors |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for index, row in enumerate(rows, start=1):
        metrics = row.get("metrics", {})
        lines.append(
            f"| {index} | {row.get('baseline', 'unknown')} | {row.get('model', 'unknown')} | "
            f"{float(row.get('score', 0.0)):.1f} | "
            f"{metric(metrics, 'success_rate'):.2f} | "
            f"{metric(metrics, 'mean_reward'):.3f} | "
            f"{metric(metrics, 'evidence_coverage'):.2f} | "
            f"{metric(metrics, 'invalid_action_rate'):.2f} | "
            f"{int(row.get('agent_error_count', 0) or 0)} |"
        )
    return "\n".join(lines) + "\n"


def paper_metrics_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| Baseline | Model | " + " | ".join(PAPER_METRIC_KEYS) + " |",
        "|---|---|" + "|".join("---:" for _ in PAPER_METRIC_KEYS) + "|",
    ]
    for row in rows:
        metrics = row.get("metrics", {})
        values = " | ".join(f"{metric(metrics, key):.3f}" for key in PAPER_METRIC_KEYS)
        lines.append(
            f"| {row.get('baseline', 'unknown')} | "
            f"{row.get('model', 'unknown')} | {values} |"
        )
    return "\n".join(lines) + "\n"


def task_success_table(data: dict[str, Any]) -> str:
    runs = data.get("runs", [])
    if not isinstance(runs, list) or not runs:
        return "_No per-task results available._\n"

    task_ids = list(runs[0].get("by_task", {}).keys())
    lines = [
        "| Task | " + " | ".join(run_label(run) for run in runs) + " |",
        "|---|" + "|".join("---:" for _ in runs) + "|",
    ]
    for task_id in task_ids:
        values = []
        for run in runs:
            by_task = run.get("by_task", {})
            metric_value = 0.0
            if isinstance(by_task, dict) and isinstance(by_task.get(task_id), dict):
                metric_value = metric(by_task[task_id], "success_rate")
            values.append(f"{metric_value:.2f}")
        lines.append(f"| {task_id} | " + " | ".join(values) + " |")
    return "\n".join(lines) + "\n"


def run_label(run: dict[str, Any]) -> str:
    baseline = str(run.get("baseline") or run.get("agent") or "unknown")
    model = str(run.get("model") or run.get("model_override") or "default")
    return f"{baseline}/{model}"


def metric(metrics: object, key: str) -> float:
    if not isinstance(metrics, dict):
        return 0.0
    value = metrics.get(key, 0.0)
    if isinstance(value, int | float):
        return float(value)
    return 0.0


if __name__ == "__main__":
    main()
