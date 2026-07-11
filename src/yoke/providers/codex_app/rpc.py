"""Codex app-server JSON-RPC request helpers."""

from __future__ import annotations

import time
from dataclasses import dataclass

from pydantic import JsonValue

from yoke.errors import YokeError
from yoke.providers.codex_app.fields import JsonObject, as_record, string_field
from yoke.providers.codex_app.process import JsonRpcLineProcess, is_server_request


def request_rpc(
    process: JsonRpcLineProcess,
    method: str,
    params: JsonObject | None,
    timeout_seconds: float,
) -> JsonValue:
    request_id = process.next_request_id()
    process.write({"id": request_id, "method": method, "params": params})
    deadline = time.monotonic() + timeout_seconds
    while True:
        message = process.read_until(deadline, f"{method} timed out")
        if is_server_request(message):
            respond_to_server_request(process, message)
            continue
        if "id" in message:
            if message.get("id") != request_id:
                continue
            error = as_record(message.get("error"))
            if error:
                detail = string_field(error, "message") or "request failed"
                raise YokeError(f"Codex app-server {method}: {detail}")
            return message.get("result")


def respond_to_server_request(
    process: JsonRpcLineProcess,
    message: JsonObject,
    response: ServerResponse | JsonObject | None = None,
) -> None:
    request_id = message.get("id")
    method = string_field(message, "method")
    if request_id is None or method is None:
        return
    resolved = normalize_server_response(
        response if response is not None else noninteractive_response(method)
    )
    if resolved.error is not None:
        process.write({"id": request_id, "error": resolved.error})
        return
    process.write({"id": request_id, "result": resolved.result})


@dataclass(frozen=True)
class ServerResponse:
    result: JsonObject | None = None
    error: JsonObject | None = None


def normalize_server_response(response: ServerResponse | JsonObject) -> ServerResponse:
    if isinstance(response, ServerResponse):
        return response
    return ServerResponse(result=response)


def noninteractive_response(method: str) -> ServerResponse:
    if method in {
        "item/commandExecution/requestApproval",
        "item/fileChange/requestApproval",
    }:
        return ServerResponse(result={"decision": "decline"})
    if method in {"execCommandApproval", "applyPatchApproval"}:
        return ServerResponse(result={"decision": "denied"})
    if method == "item/tool/requestUserInput":
        return ServerResponse(result={"answers": {}})
    if method == "mcpServer/elicitation/request":
        return ServerResponse(result={"action": "decline", "content": None})
    if method == "item/tool/call":
        return ServerResponse(result={"contentItems": [], "success": False})
    if method == "item/permissions/requestApproval":
        return ServerResponse(
            result={"permissions": {}, "scope": "turn", "strictAutoReview": True}
        )
    return ServerResponse(
        error={
            "code": -32601,
            "message": f"Yoke does not handle Codex app-server request {method}",
        }
    )
