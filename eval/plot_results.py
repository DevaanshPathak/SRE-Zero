"""Create simple SVG plots from SRE-Zero evaluation summaries.

The plotting script intentionally avoids a plotting dependency. It reads the
combined JSON produced by `eval/run_all_eval.py` or `eval/run_baseline_marks.py`
and writes small SVG charts plus a markdown table.
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot SRE-Zero evaluation results.")
    parser.add_argument("--input", type=Path, default=Path("notes/runs/all_eval_summary.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("notes/plots/latest"))
    args = parser.parse_args()
    input_path = repo_path(args.input)
    output_dir = repo_path(args.output_dir)

    data = json.loads(input_path.read_text(encoding="utf-8"))
    rows = extract_rows(data)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "overall_marks.svg").write_text(
        bar_chart(
            rows,
            value_key="score",
            title="SRE-Zero Overall Marks",
            max_value=100.0,
            value_label="marks",
        ),
        encoding="utf-8",
    )
    (output_dir / "success_vs_evidence.svg").write_text(
        grouped_rate_chart(
            rows,
            title="Success Rate vs Evidence Coverage",
            series=[
                ("success_rate", "Success"),
                ("evidence_coverage", "Evidence"),
            ],
        ),
        encoding="utf-8",
    )
    (output_dir / "metrics_table.md").write_text(metrics_table(rows), encoding="utf-8")
    print(f"Wrote plots to {output_dir}")


def repo_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return ROOT / path


def extract_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    marks = data.get("marks")
    if isinstance(marks, dict) and isinstance(marks.get("rows"), list):
        return sorted(marks["rows"], key=lambda row: row.get("score", 0.0), reverse=True)

    overall = data.get("overall", {})
    if not isinstance(overall, dict):
        overall = {}
    return [
        {
            "baseline": data.get("agent", "unknown"),
            "model": data.get("model_override") or "default",
            "score": float(overall.get("mean_reward", 0.0)) * 100.0,
            "metrics": overall,
            "agent_error_count": 0,
            "run_error": data.get("run_error"),
        }
    ]


def row_label(row: dict[str, Any]) -> str:
    model = str(row.get("model", "unknown")).replace("deterministic/", "")
    return f"{row.get('baseline', 'unknown')} / {model}"


def metric(row: dict[str, Any], key: str) -> float:
    metrics = row.get("metrics", {})
    if not isinstance(metrics, dict):
        return 0.0
    value = metrics.get(key, 0.0)
    return float(value) if isinstance(value, int | float) else 0.0


def bar_chart(
    rows: list[dict[str, Any]],
    *,
    value_key: str,
    title: str,
    max_value: float,
    value_label: str,
) -> str:
    width = 960
    row_height = 42
    left = 260
    top = 64
    chart_width = 620
    height = top + row_height * len(rows) + 42
    lines = svg_header(width, height, title)
    for index, row in enumerate(rows):
        y = top + index * row_height
        value = float(row.get(value_key, 0.0))
        bar_width = max(0.0, min(chart_width, chart_width * value / max_value))
        label = html.escape(row_label(row))
        lines.append(f'<text x="20" y="{y + 18}" class="label">{label}</text>')
        lines.append(
            f'<rect x="{left}" y="{y}" width="{bar_width:.1f}" height="24" rx="3" '
            'class="bar" />'
        )
        lines.append(
            f'<text x="{left + bar_width + 8:.1f}" y="{y + 17}" class="value">'
            f"{value:.1f} {html.escape(value_label)}</text>"
        )
    lines.append("</svg>")
    return "\n".join(lines)


def grouped_rate_chart(
    rows: list[dict[str, Any]],
    *,
    title: str,
    series: list[tuple[str, str]],
) -> str:
    width = 960
    row_height = 48
    left = 260
    top = 76
    chart_width = 620
    bar_height = 16
    height = top + row_height * len(rows) + 56
    colors = ["#2f6f4e", "#c77d2a", "#555555"]
    lines = svg_header(width, height, title)
    for series_index, (_, label) in enumerate(series):
        x = left + series_index * 130
        lines.append(f'<rect x="{x}" y="42" width="18" height="12" class="s{series_index}" />')
        lines.append(f'<text x="{x + 24}" y="53" class="legend">{html.escape(label)}</text>')
    for index, row in enumerate(rows):
        y = top + index * row_height
        label = html.escape(row_label(row))
        lines.append(f'<text x="20" y="{y + 22}" class="label">{label}</text>')
        for series_index, (key, _) in enumerate(series):
            value = max(0.0, min(1.0, metric(row, key)))
            bar_width = chart_width * value
            bar_y = y + series_index * (bar_height + 4)
            lines.append(
                f'<rect x="{left}" y="{bar_y}" width="{bar_width:.1f}" '
                f'height="{bar_height}" rx="3" class="s{series_index}" />'
            )
            lines.append(
                f'<text x="{left + bar_width + 8:.1f}" y="{bar_y + 12}" class="value">'
                f"{value:.2f}</text>"
            )
    lines.append("<style>")
    for index, color in enumerate(colors):
        lines.append(f".s{index} {{ fill: {color}; }}")
    lines.append("</style>")
    lines.append("</svg>")
    return "\n".join(lines)


def metrics_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        (
            "| Baseline | Model | Marks | Success | Reward | Steps | Invalid | Evidence | "
            "Wrong Fix | Distractor |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row.get('baseline', 'unknown')} | {row.get('model', 'unknown')} | "
            f"{float(row.get('score', 0.0)):.1f} | "
            f"{metric(row, 'success_rate'):.2f} | "
            f"{metric(row, 'mean_reward'):.3f} | "
            f"{metric(row, 'mean_steps'):.2f} | "
            f"{metric(row, 'invalid_action_rate'):.2f} | "
            f"{metric(row, 'evidence_coverage'):.2f} | "
            f"{metric(row, 'wrong_remediation_rate'):.2f} | "
            f"{metric(row, 'distractor_failure_rate'):.2f} |"
        )
    return "\n".join(lines) + "\n"


def svg_header(width: int, height: int, title: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        "<style>",
        "text { font-family: Arial, sans-serif; fill: #1f2933; }",
        ".title { font-size: 22px; font-weight: 700; }",
        ".label { font-size: 13px; }",
        ".value { font-size: 12px; fill: #3e4c59; }",
        ".legend { font-size: 12px; fill: #3e4c59; }",
        ".bar { fill: #345995; }",
        "</style>",
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff" />',
        f'<text x="20" y="30" class="title">{html.escape(title)}</text>',
    ]


if __name__ == "__main__":
    main()
