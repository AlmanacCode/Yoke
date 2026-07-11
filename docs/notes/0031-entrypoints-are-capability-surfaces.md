# Entrypoints are capability surfaces

Date: 2026-07-04

Yoke must not treat "Claude" or "Codex" as enough information to decide whether a feature is supported.

The same underlying agent family exposes different features depending on how Yoke reaches it:

- Claude CLI
- Claude Agent SDK
- Claude Code hooks and local settings
- Codex CLI
- Codex SDK, when available
- Codex app server
- Codex desktop/app surfaces

This matters because goals, streaming, session resume, model listing, collaboration tools, skills, hooks, MCP, structured output, and subagents do not all appear at the same layer.

The design rule is:

```python
Harness(provider="codex", surface="app_server", ...)
Harness(provider="codex", surface="cli", ...)
Harness(provider="claude", surface="sdk", ...)
```

Provider names select the family. Surface names select the concrete entrypoint and its real capability set.

## Codex pressure

Codex app server appears to expose the richest surface today. It has app-style thread state, streaming notifications, goal tools, skill-root registration, model listing, and collaboration events.

Codex CLI is still valuable because it is easy to run and script, but it is less expressive. It should be a good one-shot and resumable-session bridge, not the source of truth for every Codex feature.

Yoke should keep Codex app-server support as a first-class adapter rather than hiding it behind the CLI adapter.

## Claude pressure

Claude Agent SDK exposes programmatic sessions, options, hooks, MCP, subagents, and structured results in a different shape from Claude CLI configuration.

Claude workflow-like behavior should be studied as SDK behavior and prompt/runtime composition, not assumed to be a portable primitive identical to Codex goals or Codex app-server collaboration.

Yoke should avoid depending on Claude-only workflow semantics as the core abstraction. Yoke-owned workflows can compile into provider features when native support exists.

## Capability contract

Every feature needs a support row per provider surface:

- `native`: the entrypoint directly exposes it.
- `compiled`: Yoke can translate a Yoke concept into the provider's native config or prompt shape.
- `emulated`: Yoke owns the loop/state and calls the provider repeatedly.
- `unsupported`: Yoke should fail clearly or degrade only when explicitly requested.
- `unknown`: research is incomplete; do not present it as supported.

This keeps the public API honest:

```python
caps = harness.capabilities()
caps.supports("goal")
caps.supports("streaming")
caps.supports("declared_subagents")
```

## SDK implication

Yoke's public API can remain simple:

```python
agent = Agent(
    instructions="You are a careful maintainer.",
    goal=Goal("Finish the requested implementation safely."),
)

harness = Harness(
    provider="codex",
    surface="app_server",
    agent=agent,
    cwd=repo,
)

result = await harness.run("Implement the bundle loader.")
```

But internally the adapter must know the exact surface. The beautiful API should not erase the messy truth that each entrypoint has a different feature envelope.

## Ongoing research checklist

Before marking a Yoke feature supported, check the provider's current docs or code for each relevant entrypoint:

- Does the CLI expose it?
- Does the SDK expose it?
- Does the app server expose it?
- Does it work in one-shot runs?
- Does it work in live sessions?
- Does it stream?
- Does it resume?
- Does it survive folder packaging?
- Does it require provider-specific auth, config, or app-only state?

This is the project trap: the feature may exist, but not at the entrypoint Yoke is using.
