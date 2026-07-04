# 0004: Claude one-shot adapter

Slice date: 2026-07-03

## What landed

Yoke now has optional provider adapters under `yoke.providers`.

The first real adapter is `Claude`. It implements one-shot `run()` through the
Claude Agent SDK `query()` API.

```python
from yoke import Agent, Goal, Harness
from yoke.providers import Claude

agent = Agent(
    instructions="You are a careful maintainer.",
    goal=Goal("Finish safely.", token_budget=200_000),
)

result = await Harness(
    provider="claude",
    agent=agent,
    cwd=repo,
).with_adapter(Claude()).run("Implement the bundle loader.")
```

## Translation rules

Yoke `Agent.instructions` becomes Claude `system_prompt`.

Yoke `Goal` is appended to the system prompt and maps `token_budget` to Claude
`task_budget`. This is compiled support, not native mutable goal state.

Yoke subagents become Claude `AgentDefinition` entries. The Claude model can
invoke them through its Agent tool.

Yoke `Tools` maps to Claude built-in tool names:

- read: `Read`, `Grep`, `Glob`
- write: `Write`, `Edit`
- shell: `Bash`
- web: `WebFetch`, `WebSearch`
- agent: `Agent`

Yoke `Permissions` maps to Claude permission modes:

- auto + full: `bypassPermissions`
- auto + write: `acceptEdits`
- never: `dontAsk`
- ask: `default`

## What stayed intentionally unimplemented

Claude live sessions are not faked yet. The adapter raises `UnsupportedFeature`
for `start()`, `send()`, `stream()`, `set_goal()`, and `clear_goal()`.

The next slice should decide where live client ownership belongs. The likely
shape is a `Session` object that owns the provider client through adapter state,
not a bare Pydantic handle pretending to be enough.

## Codex note

`Codex` currently declares capabilities but raises `UnsupportedFeature`. The
bridge needs either the TypeScript SDK through a subprocess/Node shim or a
direct app-server protocol client.

## First real-smoke result

Command:

```bash
uv run --with claude-agent-sdk --with pydantic --with pyyaml python examples/claude_run.py
```

Result:

The first attempt failed before Claude started because `pyproject.toml` listed
`openai-codex>=0.1` under the `codex` extra. The available package in the
resolver was `openai-codex<=0.1.0b3`, and the provider research showed the
usable Codex SDK is currently TypeScript/NPM anyway. The `codex` Python extra is
now empty until Yoke has a deliberate Node/app-server bridge.

The retry succeeded against the real Claude Agent SDK and returned:

```text
yoke works
```

It also printed:

```text
Permission deny rule "MultiEdit" matches no known tool — check for typos.
```

Yoke removed `MultiEdit` from the Claude built-in tool mapping. If a later
Claude CLI version exposes `MultiEdit`, the adapter can add it behind version
or capability detection instead of warning on current installs.

The final retry succeeded cleanly:

```text
yoke works
```
