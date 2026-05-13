"""Small stdlib HTTP backend for local SRE-Zero frontend use."""

from __future__ import annotations

import argparse
import json
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from srezero.env import SREEnv
from srezero.schemas import Action
from srezero.task_registry import task_catalog, task_splits

SESSIONS: dict[str, SREEnv] = {}


class RequestError(ValueError):
    def __init__(self, message: str, status: HTTPStatus = HTTPStatus.BAD_REQUEST) -> None:
        super().__init__(message)
        self.status = status


class SREZeroRequestHandler(BaseHTTPRequestHandler):
    server_version = "SREZeroHTTP/0.1"

    def do_OPTIONS(self) -> None:
        self._send_empty(HTTPStatus.NO_CONTENT)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json({"status": "ok"})
            return
        if self.path == "/tasks":
            self._send_json({"tasks": task_catalog(), "splits": task_splits()})
            return
        self._send_json({"error": "not_found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        try:
            if self.path == "/episode/reset":
                self._handle_reset()
                return
            if self.path == "/episode/step":
                self._handle_step()
                return
            self._send_json({"error": "not_found"}, status=HTTPStatus.NOT_FOUND)
        except RequestError as exc:
            self._send_json({"error": str(exc)}, status=exc.status)

    def log_message(self, format: str, *args: object) -> None:
        return None

    def _handle_reset(self) -> None:
        body = self._read_json_body()
        task_id = _optional_str(body.get("task_id") or body.get("taskId"))
        seed = _optional_int(body.get("seed"))

        env = SREEnv()
        observation = env.reset(task_id=task_id, seed=seed)
        session_id = str(uuid.uuid4())
        SESSIONS[session_id] = env
        self._send_json(
            {
                "session_id": session_id,
                "observation": observation.model_dump(mode="json"),
                "info": {
                    "task_id": observation.incident_id,
                    "available_actions": env.available_actions(),
                },
            }
        )

    def _handle_step(self) -> None:
        body = self._read_json_body()
        session_id = _optional_str(body.get("session_id") or body.get("sessionId"))
        if session_id is None or session_id not in SESSIONS:
            raise RequestError("unknown_session", status=HTTPStatus.NOT_FOUND)

        action_input = body.get("raw_action") or body.get("rawAction") or body.get("action")
        if action_input is None:
            raise RequestError("missing_action")

        action = _normalize_action(action_input)
        result = SESSIONS[session_id].step(action)
        self._send_json(result.model_dump(mode="json"))

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        raw_body = self.rfile.read(length).decode("utf-8")
        try:
            parsed = json.loads(raw_body)
        except json.JSONDecodeError:
            raise RequestError("invalid_json") from None
        if not isinstance(parsed, dict):
            raise RequestError("json_body_must_be_object")
        return parsed

    def _send_empty(self, status: HTTPStatus) -> None:
        self.send_response(status)
        self._send_common_headers()
        self.end_headers()

    def _send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self._send_common_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_common_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")


def run_server(host: str, port: int) -> None:
    server = ThreadingHTTPServer((host, port), SREZeroRequestHandler)
    print(f"SRE-Zero backend listening on http://{host}:{port}")
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the SRE-Zero local HTTP backend.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    run_server(host=args.host, port=args.port)


def _normalize_action(action_input: object) -> Action | str:
    if isinstance(action_input, str):
        return action_input
    if not isinstance(action_input, dict):
        return str(action_input)

    normalized = dict(action_input)
    _rename_key(normalized, "actionType", "action_type")
    _rename_key(normalized, "rootCause", "root_cause")
    try:
        return Action.model_validate(normalized)
    except ValueError as exc:
        raise RequestError(str(exc)) from exc


def _rename_key(payload: dict[str, object], old_key: str, new_key: str) -> None:
    if old_key in payload and new_key not in payload:
        payload[new_key] = payload.pop(old_key)


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        return None
    try:
        return int(value)
    except ValueError:
        return None


if __name__ == "__main__":
    main()
