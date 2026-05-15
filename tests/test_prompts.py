from baselines.prompts import template_for_profile
from srezero.env import SREEnv


def test_prompt_templates_include_expanded_services_and_action_format() -> None:
    prompting = template_for_profile("prompting")
    react = template_for_profile("react")

    assert "message_queue" in prompting.system
    assert "load_balancer" in prompting.system
    assert "inspect_metrics(cache)" in prompting.system
    assert "Thought:" in react.system
    assert "Action:" in react.system


def test_prompt_user_message_contains_observation() -> None:
    observation = SREEnv().reset(task_id="message_queue_crash", seed=0)

    message = template_for_profile("prompting").user_message(observation)

    assert "message_queue_crash" in message
    assert "Background jobs are delayed" in message
