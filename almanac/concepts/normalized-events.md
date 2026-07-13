---
title: "Normalized Events"
summary: "Normalized events are Yoke's provider-neutral stream records for text, tools, requests, usage, goals, hooks, sessions, and unknown provider activity."
topics: [concepts, runtime]
sources:
  - id: models
    type: file
    path: src/yoke/models.py
  - id: readme
    type: file
    path: README.md
  - id: options
    type: file
    path: src/yoke/options.py
  - id: codex-events
    type: file
    path: src/yoke/providers/codex_app/events.py
  - id: claude-adapter
    type: file
    path: src/yoke/providers/claude.py
  - id: event-tests
    type: file
    path: tests/test_events.py
  - id: codex-event-tests
    type: file
    path: tests/test_codex_app_events.py
  - id: capability-tests
    type: file
    path: tests/test_capabilities.py
---

Normalized events are Yoke's provider-neutral records for activity that happens during a run or streamed session turn. The `Event` model can represent text, tool use, tool results, request events, usage, provider session ids, warnings, errors, hooks, goals, rate limits, and unknown stream activity while preserving raw provider data [@models]. This gives a [Yoke Harness](yoke-harness) one event language even when Claude and Codex emit different native message shapes.

## Event kinds

`EventKind` defines the known event vocabulary: text deltas, full text, tool use, tool results, tool summaries, tool requests, approval requests, user-input requests, resolved requests, context usage, provider session discovery, warnings, errors, done events, hooks, rate limits, goal updates, goal clears, generic stream events, and unknown events [@models].

Known event kind strings are normalized into enum values, while unknown provider event strings remain as strings [@event-tests]. This lets Yoke add stable behavior for known events without discarding provider-specific activity it does not yet understand.

## What an event can carry

An event can carry display text, tool identifiers, tool input, typed tool metadata, tool results, agent-call metadata, request and response records, goal state, usage, provider session ids, provider event ids, parent tool ids, source thread ids, source turn ids, and the raw provider object [@models].

Tool metadata is also normalized. `ToolKind` covers read, write, edit, search, shell, MCP, web, agent, image, and unknown tools; `ToolStatus` covers started, completed, failed, and declined [@models]. Agent activity can be represented with `AgentCall`, which records actions such as spawning or updating provider-native agent work [@models].

## Codex app-server mapping

The Codex app-server mapper turns JSON-RPC notifications into normalized events. Agent message deltas become `text_delta`, completed agent messages become `text`, plan or command output becomes `tool_summary`, token usage becomes `context_usage`, goal changes become `goal_updated` or `goal_cleared`, warnings and errors become warning/error events, and unknown notification methods become `stream_event` with the method name preserved [@codex-events].

Codex server requests are represented as request events with a default response, typed request metadata, tool metadata, and the response that Yoke sends back to the app-server [@codex-events]. Tests also cover Codex collaboration tool calls mapping to agent tool events and preserving sender, receiver, prompt, model, effort, and raw tool result fields [@codex-event-tests].

## Claude mapping

The Claude adapter maps SDK messages into the same event model. Assistant text blocks become `text`, tool-use blocks become `tool_use`, tool-result blocks become `tool_result`, thinking blocks become `tool_summary`, system messages can carry `provider_session`, stream events become `stream_event`, hook messages become `hook`, and rate-limit messages become `rate_limit` [@claude-adapter].

Claude request callbacks are also normalized. A tool permission callback becomes an approval request, `AskUserQuestion` becomes a user-input request, and a Yoke `Response` is converted back into the Claude SDK permission result [@claude-adapter].

## Why raw data remains

Normalized events are not a lossy replacement for provider protocols. Unknown Codex app-server methods are preserved as `stream_event` records with raw notification data [@codex-events]. Unknown event kinds in the public event model also remain strings instead of failing validation [@event-tests]. This keeps event streams forward-compatible while still giving common behavior a stable shape.

## Use in runs and storage

Runs carry normalized events directly, and streamed sessions yield normalized events one at a time [@models]. This is the bridge between live provider activity and later inspection of a run result.

Embedding applications can also receive run events through `RunOptions(on_event=...)`. The README defines `on_event` as a synchronous callback that receives each normalized event once during a one-shot run [@readme]. The option is runtime-only: `RunOptions` excludes the callback from serialization and reports it as an SDK-only runtime option because a Python callable cannot round-trip through agent folders [@options].

The callback is a surface-planned feature, not a universal provider promise. `RunOptions.features()` declares `run_event_callbacks` when `on_event` is present, and capability tests show automatic Codex planning selects the Codex app-server surface while explicit Codex CLI or Codex Python SDK surfaces reject the run before execution [@options] [@capability-tests]. Use `harness.stream(...)` when the caller needs a portable event iterator instead of a live callback [@readme].

[Runtime Flow](../architecture/runtime-flow) places callbacks, streaming, collected events, and stored `events.jsonl` files in one execution path.
