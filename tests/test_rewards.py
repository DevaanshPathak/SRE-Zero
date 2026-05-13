from srezero.env import SREEnv
from srezero.schemas import Action


def test_reward_bounds_for_episode_and_steps() -> None:
    env = SREEnv()
    env.reset(task_id="cache_crash", seed=0)

    step_rewards = [
        env.step(Action(action_type="check_status", service="cache")).reward,
        env.step(Action(action_type="restart_service", service="cache")).reward,
        env.step(
            Action(
                action_type="resolve_incident",
                root_cause="cache service crashed",
                fix="restart cache service",
            )
        ).reward,
    ]

    assert all(-1.0 <= reward <= 1.0 for reward in step_rewards)
    assert 0.0 <= env.metrics.final_reward <= 1.0


def test_wrong_remediation_penalty_is_recorded() -> None:
    env = SREEnv()
    env.reset(task_id="misleading_web_500_db_rootcause", seed=0)

    result = env.step(Action(action_type="restart_service", service="web_server"))

    assert env.metrics.wrong_remediations == 1
    assert result.info["reward_components"]["penalties"]["wrong_remediation"] < 0

