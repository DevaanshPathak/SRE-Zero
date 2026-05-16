from srezero.env import SREEnv
from srezero.task_registry import (
    benchmark_splits,
    get_task,
    list_task_ids,
    task_config_ids,
    task_splits,
)


def test_task_count_and_difficulty_splits() -> None:
    task_ids = list_task_ids()
    splits = task_splits()

    assert len(task_ids) == 40
    assert set(splits) == {"easy", "medium", "hard"}
    assert all(splits.values())
    assert set(task_ids) == set(task_config_ids())


def test_benchmark_splits_cover_all_tasks_and_hold_out_unseen_incidents() -> None:
    task_ids = set(list_task_ids())
    splits = benchmark_splits()
    primary_ids = splits["train"] + splits["dev"] + splits["test"]

    assert len(task_ids) == 40
    assert len(splits["train"]) == 24
    assert len(splits["dev"]) == 8
    assert len(splits["test"]) == 8
    assert len(splits["unseen_incident"]) == 8
    assert set(primary_ids) == task_ids
    assert len(primary_ids) == len(set(primary_ids))
    assert set(splits["unseen_incident"]).issubset(splits["test"])
    assert list_task_ids(split="unseen_incident") == splits["unseen_incident"]


def test_each_task_can_reset_and_expose_safe_observation() -> None:
    for task_id in list_task_ids():
        task = get_task(task_id)
        env = SREEnv()
        observation = env.reset(task_id=task_id, seed=0)

        assert observation.incident_id == task_id
        assert observation.alert == task.alert
        assert task.root_cause not in observation.model_dump_json()
        assert observation.steps_remaining == task.max_steps
        assert task.metadata["source"] == "config"


def test_expanded_services_are_available() -> None:
    env = SREEnv()
    env.reset(task_id="message_queue_crash", seed=0)

    state = env.current_state()

    assert "message_queue" in state["services"]
    assert "load_balancer" in state["services"]


def test_metrics_are_computed() -> None:
    env = SREEnv()
    env.reset(task_id="cache_crash", seed=0)
    result = env.step("check_status(cache)")

    metrics = result.info["metrics_so_far"]
    assert metrics["total_steps"] == 1
    assert metrics["evidence_actions"] == 1
    assert result.info["evidence_coverage"] > 0
