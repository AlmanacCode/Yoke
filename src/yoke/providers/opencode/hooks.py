"""Generated OpenCode plugin + local bridge for `tool.execute.before` hooks.

Confirmed live in a 2026-07-12 spike: a generated `tool.execute.before`
plugin hook is awaited (blocking) by OpenCode before a tool runs, can mutate
`output.args` in place (the actually-executed tool call reflects the
mutation — replacing the whole `output.args` object does *not* work, only
per-key assignment does), and can block the call outright by throwing. The
hook runs inside the `opencode serve` child process, not this one, so it
needs a local HTTP round trip to reach a Python-side decision — this module
is that bridge.

Opt-in only: OpencodeServer only deploys this plugin and starts the bridge
when a caller configures `ProviderOptions.opencode.request_handler`/
`.policy` at session start (see `_maybe_deploy_hook_bridge` in
opencode_server.py). A tool call this adapter doesn't have an opinion on
defaults to allow-unchanged, not deny — unlike a permission request, hook
interception is something a caller opts into per tool, not a mandatory
approval gate.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from yoke.models import Event, EventKind, Request, RequestKind, Response, Tool
from yoke.providers.opencode.fields import JsonObject, as_record, string_field
from yoke.providers.opencode.parts import infer_opencode_tool_kind
from yoke.providers.opencode.permissions import policy_response

OPENCODE_HOOK_PLUGIN_SOURCE = """\
export const YokeToolHook = async () => {
  const bridgeUrl = process.env.YOKE_HOOK_BRIDGE_URL;
  if (!bridgeUrl) {
    return {};
  }
  return {
    "tool.execute.before": async (input, output) => {
      const res = await fetch(bridgeUrl + "/tool-hook", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sessionID: input.sessionID,
          callID: input.callID,
          tool: input.tool,
          args: output.args,
        }),
      });
      const decision = await res.json();
      if (decision.args) {
        for (const key of Object.keys(decision.args)) {
          output.args[key] = decision.args[key];
        }
      }
      if (decision.deny) {
        throw new Error(decision.message || "Denied by Yoke.");
      }
    },
  };
};
"""

ResolveCallback = Callable[[str, JsonObject], Response]


class OpencodeHookBridge:
    """Local HTTP server the generated plugin calls into for each tool call.

    Process-scoped, not session-scoped: the plugin is addressed via an env
    var fixed at `opencode serve` spawn time, and a fork shares its parent's
    process/env, so there is exactly one bridge per process regardless of
    how many sessions (forks) run on it. `resolve` is given the tool call's
    own `sessionID` to route to the right session's current policy/event
    stream.
    """

    def __init__(self, resolve: ResolveCallback) -> None:
        bridge = self
        self._resolve = resolve

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802 - stdlib handler name
                length = int(self.headers.get("Content-Length", 0))
                try:
                    payload = as_record(json.loads(self.rfile.read(length) or b"{}"))
                except ValueError:
                    payload = {}
                session_id = string_field(payload, "sessionID") or ""
                response = bridge._resolve(session_id, payload)
                body = json.dumps(
                    {
                        "args": response.updated_input,
                        "deny": response.decision != "allow",
                        "message": response.message,
                    }
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format_string: str, *args: object) -> None:
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True
        )

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()


def hook_event(payload: JsonObject) -> Event:
    """Build the provider-neutral event for one intercepted tool call."""

    tool_name = string_field(payload, "tool") or "tool"
    args = payload.get("args")
    command = string_field(args, "command") if isinstance(args, dict) else None
    tool = Tool(
        kind=infer_opencode_tool_kind(tool_name),
        title=tool_name,
        command=command,
    )
    message = f"OpenCode is about to run {tool_name}"
    call_id = string_field(payload, "callID")
    # Allow-unchanged by default: this bridge only exists because the
    # caller opted in (see module docstring), so a tool this specific
    # handler has no opinion on should pass through, not fail closed.
    default = Response.allow()
    return Event(
        kind=EventKind.TOOL_REQUEST,
        message=message,
        tool_id=call_id,
        tool_name=tool_name,
        tool=tool,
        request=Request(
            kind=RequestKind.TOOL,
            id=call_id,
            method=tool_name,
            message=message,
            tool=tool,
            input=args,
            default=default,
            raw=payload,
        ),
        response=default,
        source_thread_id=string_field(payload, "sessionID"),
        raw=payload,
    )


def resolve(
    payload: JsonObject, request_handler: object | None
) -> tuple[Event, Response]:
    """Resolve one intercepted tool call, returning the event and decision."""

    event = hook_event(payload)
    response = policy_response(event, request_handler)
    return event, response
