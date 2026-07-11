# Provider surfaces are feature boundaries

Date: 2026-07-04

Yoke cannot model `provider="codex"` or `provider="claude"` as a single uniform capability set. Codex and Claude expose different features through different surfaces, and the richest surface is not always the public SDK.

## Rule

A Yoke capability belongs to a `(provider, surface)` pair, not just to a provider.

Examples:

- Codex app server appears to expose the deepest live runtime surface: streaming, session state, collaboration/agent handoffs, app-native tool events, native goals, and richer lifecycle hooks.
- Codex CLI is useful and scriptable, but it is primarily a process surface; Yoke must parse/normalize what the CLI emits and should not assume app-server parity.
- Codex Python/TypeScript SDK surfaces may lag or differ from app-server behavior. Treat them as separate adapters, not wrappers around the same contract.
- Claude SDK exposes agents, subagents, tools, hooks, MCP, and workflow-style composition, but those concepts may not map one-to-one to Claude CLI or any future hosted/app surface.
- Claude workflows are inspiration for portable Yoke workflows, but Yoke should own the portable workflow model instead of depending on Claude-only workflow semantics.

## Design consequence

Yoke should have three layers:

1. User model: `Agent`, `Harness`, `Goal`, `Workflow`, `Skill`, `Tool`, `RunOptions`.
2. Capability model: `Capabilities` resolved from `(provider, surface)`.
3. Adapter model: provider/surface-specific implementations that lower Yoke concepts into CLI, SDK, or app-server calls.

The public SDK should stay beautiful and small, but internally it must be honest about which surface is doing the work.

```python
from yoke import Agent, Goal, Harness, Surface

agent = Agent(
    instructions="You are a careful maintainer.",
    goal=Goal("Finish the requested implementation safely."),
)

harness = Harness(
    provider="codex",
    surface=Surface.CODEX_APP_SERVER,
    agent=agent,
    cwd=repo,
)

result = await harness.run("Implement the bundle loader.")
```

If the caller omits `surface`, Yoke may choose a recommended default, but it should expose the chosen surface in readiness, run metadata, and diagnostics.

## Integration consequence for CodeAlmanac

CodeAlmanac should depend on Yoke as a harness SDK, not as a jobs/runs lifecycle engine.

CodeAlmanac owns:

- lifecycle operations
- jobs and run records
- changed-file calculation
- normalized product events
- prompts and wiki mutation rules

Yoke owns:

- provider auth/readiness
- CLI/SDK/app-server invocation
- session and stream mechanics
- goal lowering
- subagent lowering
- portable workflow execution
- provider capability discovery

The adapter boundary should look like this:

```python
request: CodeAlmanac RunHarnessRequest
    -> Yoke Agent + Harness + RunOptions
    -> Yoke Run/Event stream
    -> CodeAlmanac HarnessRunResult/HarnessEvent
```

Yoke should not import CodeAlmanac or know about Almanac roots, pages, jobs, captures, or lifecycle semantics.

## Open research checklist

Before declaring parity for a feature, check all relevant surfaces:

- Codex app server
- Codex CLI
- Codex Python SDK
- Codex TypeScript SDK, if available
- Claude Python SDK
- Claude TypeScript SDK
- Claude CLI

For each feature, record whether the surface supports it natively, supports it through prompt/bundle lowering, or does not support it cleanly.

Features to track:

- one-shot run
- resumable session
- streaming events
- structured output
- goals
- per-turn goals
- custom subagents
- skills
- MCP/tools
- hooks
- workflows
- permission/approval policy
- model listing
- auth/login flows
- usage accounting
- tool-call event visibility
