from srezero.actions import ActionParseError, format_action, parse_action
from srezero.schemas import Action


def test_parse_valid_update_config_action() -> None:
    action = parse_action("update_config(database, DB_POOL_SIZE, 100)")

    assert action == Action(
        action_type="update_config",
        service="database",
        key="DB_POOL_SIZE",
        value=100,
    )
    assert format_action(action) == "update_config(database, DB_POOL_SIZE, 100)"


def test_parse_invalid_action_name() -> None:
    try:
        parse_action("shell(rm -rf /)")
    except ActionParseError as exc:
        assert "Unknown action" in str(exc)
    else:
        raise AssertionError("Expected ActionParseError")

