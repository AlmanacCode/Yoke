# 0008: Codex app-server is a control plane

Slice date: 2026-07-03

## What was read

Files inspected from the local Codex clone:

- `codex-rs/app-server/src/main.rs`
- `codex-rs/app-server/src/in_process.rs`
- `codex-rs/app-server/src/transport.rs`
- `codex-rs/app-server/src/request_processors/thread_lifecycle.rs`
- `codex-rs/app-server/src/request_processors/thread_goal_processor.rs`
- `codex-rs/app-server/src/request_processors/thread_processor.rs`
- `codex-rs/app-server/src/request_processors/turn_processor.rs`
- `codex-rs/app-server/src/message_processor.rs`

## Surface shape

Codex app-server is a control-plane surface.

It starts with a transport:

- `stdio://`
- `unix://`
- `ws://IP:PORT`
- `off`

It then runs JSON-RPC-ish client requests through `MessageProcessor`. The
in-process module confirms the intended lifecycle:

1. start runtime state,
2. perform `initialize` / `initialized`,
3. send typed client requests,
4. consume server requests and notifications,
5. shut down.

The in-process docs explicitly say higher-level callers should use
`codex-app-server-client` when available, because that wraps the low-level
runtime behind request/response helpers, surface-specific startup policy, and
bounded shutdown.

## Important app-server primitives

Requests observed in `message_processor.rs`:

- `Initialize`
- `ThreadStart`
- `ThreadResume`
- `ThreadGoalSet`
- `ThreadGoalGet`
- `ThreadGoalClear`
- `ThreadList`
- `TurnStart`

Goal processor behavior:

- native goal feature gate,
- set/get/clear per thread,
- persisted state reconciliation,
- ordered goal update notifications,
- goal snapshots on resume,
- status values mapped from state: active, paused, blocked, usage-limited,
  budget-limited, complete.

Thread lifecycle behavior:

- listeners attach to running conversations,
- running threads are unloaded after inactivity,
- listener commands order resume responses, goal updates, goal clears, and
  server-request resolution,
- server notifications carry thread and turn progress.

## Implication for Yoke

`codex_app_server` should be a separate adapter surface, not an extension of
`codex_cli`.

The adapter should probably have three layers:

1. `CodexAppServerTransport`: stdio/unix/ws JSON-RPC transport.
2. `CodexAppServerClient`: typed-ish request/response plus notification stream.
3. `CodexApp`: Yoke provider adapter translating `Harness`, `Session`, `Turn`,
   `Goal`, and `Event` into app-server operations.

This follows the Cosmic Python boundary: the adapter owns provider mechanics,
while Yoke services/models own product verbs like run, start, send, stream, and
set goal.

## Do not fake this

The CLI adapter has compiled goals because it can only put the goal in the
prompt. App-server has native mutable goals. Yoke must not expose mutable goals
through the CLI adapter just because the provider name is `codex`.

The app-server adapter needs real protocol handling before claiming support for:

- mutable goals,
- app-server thread streaming,
- app-server subagent lineage,
- server-request approvals,
- config/skills/hook surfaces.

## Open question

The local clone references `codex_app_server_protocol`, but the protocol crate
source was not in the paths first searched under `codex-rs/`. Future work should
locate the generated/provided protocol crate or consume the app-server client
crate if it is published inside the Codex repository.
