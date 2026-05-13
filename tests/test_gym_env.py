from srezero.gym_env import SREOpenEnv


def test_gym_style_reset_and_step() -> None:
    env = SREOpenEnv(task_id="cache_crash")

    observation, info = env.reset(seed=0)
    assert observation.incident_id == "cache_crash"
    assert info["task_id"] == "cache_crash"
    assert env.action_space

    observation, reward, terminated, truncated, step_info = env.step("check_status(cache)")

    assert observation.step == 1
    assert reward > 0
    assert terminated is False
    assert truncated is False
    assert step_info["invalid_action"] is False
    assert "incident=cache_crash" in env.render()


def test_gym_style_truncates_on_step_budget() -> None:
    env = SREOpenEnv(task_id="cache_crash")
    observation, _ = env.reset(seed=0)

    terminated = False
    truncated = False
    for _ in range(observation.steps_remaining):
        _, _, terminated, truncated, _ = env.step("inspect_logs(web_server)")
        if terminated or truncated:
            break

    assert terminated is False
    assert truncated is True

