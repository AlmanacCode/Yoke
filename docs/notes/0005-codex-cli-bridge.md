# 0005: Codex CLI bridge

Slice date: 2026-07-03

## What the research changed

The local TypeScript Codex SDK is useful as a design reference, but the
installed CLI is newer than the clone. The clone uses:

```text
codex exec --experimental-json
```

The installed CLI reports:

```text
codex-cli 0.141.0
```

and exposes:

```text
codex exec --json
```

Yoke should follow the installed CLI contract for local execution and keep the
TypeScript SDK as conceptual documentation for events and options.

## Adapter shape

Yoke now has a small `CodexCli` bridge that:

- runs `codex exec --json`;
- passes the prompt through stdin;
- decodes JSONL events;
- writes temporary JSON schema files for structured output;
- maps cwd, model, sandbox, approval policy, reasoning effort, network, and
  web search into CLI flags/config;
- records `thread.started` as the Yoke `Session` handle.

The `Codex` provider adapter now implements one-shot `run()`.

## What is still not landed

Codex mutable goals are not available through `codex exec --json`. They live in
the app-server protocol as:

- `thread/goal/set`
- `thread/goal/get`
- `thread/goal/clear`

Yoke should add a separate app-server client before claiming mutable goal
support at runtime.

The direct CLI adapter can resume a thread later, but Yoke's public `start()`
and `send()` need a better live-thread object before exposing that path.

## Real smoke

Command:

```bash
uv run --with pydantic --with pyyaml python examples/codex_run.py
```

Result:

```text
yoke codex works
```

This confirms the current `codex_cli` adapter can execute a real one-shot run
through the installed local Codex CLI.
