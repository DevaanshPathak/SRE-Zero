import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "eval"
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

from run_eval import evaluate, resolve_task_ids  # noqa: E402

from srezero.task_registry import list_task_ids  # noqa: E402


def test_resolve_task_ids_supports_one_based_ranges() -> None:
    easy_tasks = list_task_ids(difficulty="easy")

    selected = resolve_task_ids(
        difficulty="easy",
        split=None,
        task_ids=None,
        task_range="2-3",
    )

    assert selected == easy_tasks[1:3]


def test_resolve_task_ids_rejects_unknown_ids() -> None:
    with pytest.raises(ValueError, match="not available"):
        resolve_task_ids(
            difficulty="easy",
            split=None,
            task_ids=["not_a_task"],
            task_range=None,
        )


def test_filtered_task_eval_preserves_global_episode_seed() -> None:
    easy_tasks = list_task_ids(difficulty="easy")
    result = evaluate(
        agent_name="scripted",
        episodes=1,
        seed=7,
        difficulty="easy",
        task_ids_override=[easy_tasks[2]],
    )

    records = result["records"]
    assert isinstance(records, list)
    record = records[0]
    assert isinstance(record, dict)
    assert record["task_id"] == easy_tasks[2]
    assert record["seed"] == 20_007
