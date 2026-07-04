# 0003: Provider pressure from Claude, Codex, and Eve

Slice date: 2026-07-03

## What changed

Yoke now treats support as a first-class concept. A provider adapter declares
`Capabilities`, and each feature is `native`, `compiled`, `emulated`, or
`unsupported`.

This keeps the public API simple without lying about provider behavior.

## Evidence

Claude Agent SDK exposes:

- `ClaudeAgentOptions` for tools, permissions, cwd, settings, hooks, MCP,
  agents, skills, sessions, thinking, effort, output format, file
  checkpointing, session stores, and task budgets.
- `AgentDefinition` for programmatic subagents.
- filesystem-loaded agents through `.claude/agents` when settings sources
  include the project.
- no Codex-style mutable thread-goal service in the SDK surface read here.

Codex TypeScript SDK exposes:

- `Codex.startThread()` and `Codex.resumeThread()`.
- repeated `thread.run(...)` turns.
- `runStreamed(...)` events.
- structured output per turn.
- thread options for cwd, model, sandbox, network, web search, approval policy,
  reasoning effort, and additional directories.

Codex app-server exposes:

- `thread/goal/set`, `thread/goal/get`, and `thread/goal/clear`.
- goal status values: active, paused, blocked, usage-limited, budget-limited,
  complete.
- persisted thread goals with objective, token budget, tokens used, time used,
  created time, and updated time.
- subagent spawning in the app-server extension path.

Eve exposes the strongest authoring model:

- filesystem identity by path.
- `agent/` as the authored surface.
- declared subagents under `agent/subagents/<id>/`.
- built-in copy subagent tool.
- skills as lighter capability packs.
- durable sessions with event streams.
- dynamic tools, skills, and instructions resolved on session/turn/step events.

## Decision

Yoke should expose one clean authoring language and one honest adapter seam:

- `Harness` is the user-facing runtime object with `run()` and `start()`.
- provider adapters own execution.
- adapters declare capabilities before Yoke claims a feature works.
- `Goal` exists in core, but adapters decide whether it is native, compiled
  into options, or emulated in prompt text.

## Next pressure test

Build a Claude adapter skeleton first because Claude has the richest Python SDK
surface. The slice should translate `Agent`, `Skill`, `Permissions`, `Goal`,
and subagents into `ClaudeAgentOptions` without starting with workflows.
