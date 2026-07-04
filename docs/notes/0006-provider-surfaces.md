# 0006: Providers are not surfaces

Slice date: 2026-07-03

## Correction

Yoke cannot model support as `provider -> features`.

The real shape is:

```text
provider -> surface -> features
```

For example, Codex has several surfaces:

- CLI: `codex exec --json`
- TypeScript SDK: wraps the CLI and exposes `Codex`, `Thread`, `run`, and
  `runStreamed`
- app-server: exposes richer thread lifecycle, app notifications, subagent
  lineage, config, and mutable goals

Those surfaces do not expose the same features. A feature can be real in Codex
app-server and absent from `codex exec`.

Claude has the same issue:

- Python Agent SDK: `query()`, `ClaudeSDKClient`, `ClaudeAgentOptions`,
  programmatic `AgentDefinition`, hooks, MCP, skills, sessions, task budgets
- Claude CLI/settings filesystem: `.claude/agents`, project/user/local settings,
  plugins, hooks, skills

The Python SDK can use some filesystem settings, but the SDK surface and CLI
settings surface are still different surfaces.

## Code change

Adapters now declare both:

- `provider`
- `surface`

`Harness` can also carry a `surface`. If omitted, Yoke uses the registered
default adapter for that provider.

This lets future Yoke expose:

```python
Harness(provider="codex", surface="codex_app_server", ...)
Harness(provider="codex", surface="codex_cli", ...)
Harness(provider="claude", surface="claude_python_sdk", ...)
```

without lying that every Codex or Claude path supports every feature.

## Capability rule

There are two support matrices:

- vendor surface support: what the underlying product can do
- Yoke adapter support: what this adapter currently implements

The public `adapter.capabilities` should describe Yoke adapter support. Research
notes can describe vendor support that Yoke has not implemented yet.

## Immediate consequence

The `Codex` adapter in `yoke.providers` is currently the Codex CLI adapter
(`surface="codex_cli"`). It no longer claims native mutable goals, app-server
subagents, hooks, skills, or live sessions.

Codex app-server should become a separate adapter rather than expanding the CLI
adapter until it becomes a confused mega-adapter.
