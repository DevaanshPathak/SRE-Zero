from baselines.llm_agent import _extract_action
from srezero.env import SREEnv
from srezero.schemas import Action


def test_extract_action_repairs_bare_evidence_action_from_visible_service_hint() -> None:
    observation = SREEnv().reset(task_id="cache_crash", seed=0)

    action = _extract_action("inspect_metrics", observation)

    assert isinstance(action, Action)
    assert action.action_type == "inspect_metrics"
    assert action.service == "cache"


def test_extract_action_does_not_repair_without_visible_service_hint() -> None:
    observation = SREEnv().reset(task_id="cache_latency_degradation", seed=0)

    action = _extract_action("inspect_metrics", observation)

    assert action == "inspect_metrics"
