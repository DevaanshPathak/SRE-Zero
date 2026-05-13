"""Action formatting and safe string parsing."""

from __future__ import annotations

import csv
import re
from typing import Final, cast, get_args

from pydantic import ValidationError

from srezero.schemas import Action, ActionType, ConfigValue

SERVICE_ACTIONS: Final[set[str]] = {
    "inspect_logs",
    "inspect_metrics",
    "check_status",
    "inspect_config",
    "restart_service",
    "update_config",
}

AVAILABLE_ACTION_TEMPLATES: Final[list[str]] = [
    "inspect_logs(service)",
    "inspect_metrics(service)",
    "check_status(service)",
    "inspect_config(service, key?)",
    "restart_service(service)",
    "update_config(service, key, value)",
    "resolve_incident(root_cause, fix)",
    "escalate(reason)",
]

_ACTION_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*(?P<name>[a-zA-Z_][a-zA-Z0-9_]*)\s*\((?P<args>.*)\)\s*$"
)
VALID_ACTION_TYPES: Final[set[str]] = set(get_args(ActionType))


class ActionParseError(ValueError):
    """Raised when an action cannot be parsed or validated."""


def parse_action(action: Action | str) -> Action:
    """Parse a structured Action or function-call style string."""

    if isinstance(action, Action):
        return _validate_action(action)
    if not isinstance(action, str):
        raise ActionParseError(f"Unsupported action type: {type(action).__name__}")

    match = _ACTION_RE.match(action)
    if match is None:
        raise ActionParseError(
            "Action must use function-call syntax, for example inspect_logs(web_server)."
        )

    action_type = match.group("name")
    args = _split_args(match.group("args"))
    return _action_from_parts(action_type, args)


def format_action(action: Action | str) -> str:
    """Return a stable string representation for metrics and display."""

    parsed = parse_action(action) if isinstance(action, str) else _validate_action(action)
    match parsed.action_type:
        case "inspect_logs" | "inspect_metrics" | "check_status" | "restart_service":
            return f"{parsed.action_type}({parsed.service})"
        case "inspect_config":
            if parsed.key is None:
                return f"inspect_config({parsed.service})"
            return f"inspect_config({parsed.service}, {parsed.key})"
        case "update_config":
            return f"update_config({parsed.service}, {parsed.key}, {parsed.value})"
        case "resolve_incident":
            return f"resolve_incident({parsed.root_cause}, {parsed.fix})"
        case "escalate":
            return f"escalate({parsed.reason})"


def is_remediation_action(action: Action) -> bool:
    return action.action_type in {"restart_service", "update_config"}


def _split_args(arg_text: str) -> list[str]:
    if not arg_text.strip():
        return []
    try:
        row = next(csv.reader([arg_text], skipinitialspace=True))
    except csv.Error as exc:
        raise ActionParseError(f"Could not parse action arguments: {exc}") from exc
    return [_strip_quotes(item.strip()) for item in row]


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _coerce_value(value: str) -> ConfigValue:
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _action_from_parts(action_type: str, args: list[str]) -> Action:
    if action_type not in VALID_ACTION_TYPES:
        raise ActionParseError(f"Unknown action: {action_type}")
    validated_type = cast(ActionType, action_type)

    match validated_type:
        case "inspect_logs" | "inspect_metrics" | "check_status" | "restart_service":
            if len(args) != 1:
                raise ActionParseError(f"{validated_type} requires exactly one service argument.")
            action = Action(action_type=validated_type, service=args[0])
        case "inspect_config":
            if len(args) not in {1, 2}:
                raise ActionParseError(
                    "inspect_config requires service and optional key arguments."
                )
            action = Action(
                action_type=validated_type,
                service=args[0],
                key=args[1] if len(args) == 2 else None,
            )
        case "update_config":
            if len(args) != 3:
                raise ActionParseError("update_config requires service, key, and value arguments.")
            action = Action(
                action_type=validated_type,
                service=args[0],
                key=args[1],
                value=_coerce_value(args[2]),
            )
        case "resolve_incident":
            if len(args) != 2:
                raise ActionParseError("resolve_incident requires root_cause and fix arguments.")
            action = Action(action_type=validated_type, root_cause=args[0], fix=args[1])
        case "escalate":
            if len(args) != 1:
                raise ActionParseError("escalate requires one reason argument.")
            action = Action(action_type=validated_type, reason=args[0])

    return _validate_action(action)


def _validate_action(action: Action) -> Action:
    try:
        validated = Action.model_validate(action.model_dump())
    except ValidationError as exc:
        raise ActionParseError(str(exc)) from exc

    if validated.action_type in SERVICE_ACTIONS and validated.service is None:
        raise ActionParseError(f"{validated.action_type} requires a service.")
    if validated.action_type == "update_config" and (
        validated.key is None or validated.value is None
    ):
        raise ActionParseError("update_config requires key and value.")
    if validated.action_type == "resolve_incident" and (
        not validated.root_cause or not validated.fix
    ):
        raise ActionParseError("resolve_incident requires root_cause and fix.")
    if validated.action_type == "escalate" and not validated.reason:
        raise ActionParseError("escalate requires a reason.")

    return validated
