from srezero.env import SREEnv
from srezero.task_registry import get_task, list_task_ids


def test_each_task_can_reset_and_expose_safe_observation() -> None:
    for task_id in list_task_ids():
        task = get_task(task_id)
        env = SREEnv()
        observation = env.reset(task_id=task_id, seed=0)

        assert observation.incident_id == task_id
        assert observation.alert == task.alert
        assert task.root_cause not in observation.model_dump_json()
        assert observation.steps_remaining == task.max_steps


def test_metrics_are_computed() -> None:
    env = SREEnv()
    env.reset(task_id="cache_crash", seed=0)
    result = env.step("check_status(cache)")

    metrics = result.info["metrics_so_far"]
    assert metrics["total_steps"] == 1
    assert metrics["evidence_actions"] == 1
    assert result.info["evidence_coverage"] > 0

