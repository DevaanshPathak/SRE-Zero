from baselines.random_agent import RandomAgent
from baselines.scripted_expert import ScriptedExpertAgent
from srezero.env import SREEnv
from srezero.task_registry import list_task_ids


def test_environment_reset() -> None:
    env = SREEnv()
    observation = env.reset(task_id="cache_crash", seed=0)

    assert observation.incident_id == "cache_crash"
    assert observation.step == 0
    assert "Cache hit rate" in observation.alert
    assert env.available_actions()


def test_invalid_action_handling() -> None:
    env = SREEnv()
    env.reset(task_id="cache_crash", seed=0)

    result = env.step("inspect_logs(queue)")

    assert result.info["invalid_action"] is True
    assert result.observation.last_result.error is not None
    assert env.metrics.invalid_actions == 1
    assert -1.0 <= result.reward <= 1.0


def test_scripted_expert_solves_all_tasks() -> None:
    for task_id in list_task_ids():
        env = SREEnv()
        observation = env.reset(task_id=task_id, seed=0)
        agent = ScriptedExpertAgent()
        agent.reset()

        while not env.is_done():
            observation = env.step(agent.act(observation)).observation

        assert env.metrics.success, task_id
        assert 0.75 <= env.metrics.final_reward <= 1.0


def test_random_agent_does_not_crash() -> None:
    env = SREEnv()
    observation = env.reset(task_id="web_timeout_misconfig", seed=0)
    agent = RandomAgent(seed=0)
    agent.reset()

    while not env.is_done():
        observation = env.step(agent.act(observation)).observation

    assert env.metrics.total_steps > 0
    assert 0.0 <= env.metrics.final_reward <= 1.0

