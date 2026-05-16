from srezero import benchmark_catalog, benchmark_spec, benchmark_task_ids, make_env
from srezero.scoring import score_metrics


def test_benchmark_api_exposes_splits_and_env() -> None:
    spec = benchmark_spec()
    test_ids = benchmark_task_ids(split="test")
    catalog = benchmark_catalog(split="test")

    assert spec.task_count == 40
    assert spec.train_count == 24
    assert spec.dev_count == 8
    assert spec.test_count == 8
    assert spec.unseen_incident_count == 8
    assert len(test_ids) == 8
    assert len(catalog) == 8

    env = make_env(task_id=test_ids[0])
    observation, info = env.reset(seed=0)

    assert observation.incident_id == test_ids[0]
    assert info["task_id"] == test_ids[0]


def test_standard_score_is_bounded_and_componentized() -> None:
    score = score_metrics(
        {
            "success_rate": 1.0,
            "mean_reward": 0.9,
            "mean_steps": 4.0,
            "invalid_action_rate": 0.0,
            "evidence_coverage": 1.0,
            "wrong_remediation_rate": 0.0,
            "distractor_failure_rate": 0.0,
            "premature_resolution_rate": 0.0,
        }
    )

    assert 0.0 <= score.score <= score.max_score
    assert set(score.components) == {"success", "reward", "evidence", "efficiency", "validity"}
    assert score.metrics["success_rate"] == 1.0
