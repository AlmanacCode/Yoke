---
title: "Provider Surfaces"
summary: "Provider surfaces are concrete Claude or Codex entrypoints whose capabilities form Yoke's feature boundary."
topics: [concepts, architecture]
sources:
  - id: readme
    type: file
    path: README.md
  - id: models
    type: file
    path: src/yoke/models.py
  - id: surfaces
    type: file
    path: src/yoke/surfaces.py
  - id: capabilities
    type: file
    path: src/yoke/capabilities.py
  - id: decision
    type: file
    path: docs/notes/0175-provider-surfaces-are-first-class.md
  - id: capability-tests
    type: file
    path: tests/test_capabilities.py
  - id: opencode-server
    type: file
    path: src/yoke/providers/opencode_server.py
  - id: opencode-plan
    type: file
    path: docs/plans/2026-07-11-opencode-provider.md
  - id: opencode-permissions
    type: file
    path: src/yoke/providers/opencode/permissions.py
  - id: opencode-hooks
    type: file
    path: src/yoke/providers/opencode/hooks.py
  - id: opencode-agents
    type: file
    path: src/yoke/providers/opencode/agents.py
  - id: options
    type: file
    path: src/yoke/options.py
---

Provider surfaces are the concrete Claude or Codex entrypoints that Yoke plans against. A provider is the family, such as `codex` or `claude`; a surface is the actual exposure path, such as `codex_app_server`, `codex_python_sdk`, `codex_cli`, or `claude_python_sdk` [@models]. Surfaces matter because Yoke treats features as surface-specific, not provider-wide [@decision].

## The feature boundary

The decision note says Yoke must not treat `provider="codex"` or `provider="claude"` as enough information to know what features exist, because the same provider exposes different capabilities through different surfaces [@decision]. The code reflects this in the `Surface` enum and in the capability matrix functions that resolve, report, rank, and select surface profiles [@models] [@surfaces].

A surface profile carries provider, surface, channel, runtime, capabilities, default status, and whether this Yoke package can run it [@capabilities]. That profile is the unit used by status reports, explanations, feature checks, and automatic selection.

## How Yoke selects a surface

Yoke accepts exact surfaces, friendly aliases, and compact provider specs. For example, `codex:app` resolves to `codex_app_server`, while `claude:sdk` resolves to `claude_python_sdk` [@models]. These aliases are input sugar. Yoke still reports exact surface names in plans, runs, sessions, readiness, and events [@decision].

When no explicit surface is set, `profile_for` uses provider defaults, and `select_profile` can choose the best known surface for required features and an optional channel [@surfaces]. If a surface is explicit, harness planning validates that surface instead of silently switching it [@models].

## Capabilities and support levels

Capabilities are expressed as features with support levels. The `Feature` enum includes one-shot runs, sessions, streaming, structured output, model listing, login, permissions, request events, subagents, skills, plugins, hooks, MCP, goals, interrupts, forks, workflows, native workflows, and experimental APIs [@capabilities].

Each feature has a support value: `native`, `compiled`, `emulated`, `unsupported`, or `unknown` [@capabilities]. Reports can also include notes, lowering descriptions, recipes, and evidence for a feature on a surface [@surfaces].

Feature support also changes how Yoke explains product-facing promises. The README says skills may be native skill roots on the Codex app-server but compiled to files on other surfaces, Codex app-server subagents are compiled into guidance to use native `spawn_agent`, goals are native state only on the Codex app-server, and workflows are portable Yoke constructs across the listed surfaces [@readme]. These are not marketing distinctions; they are the support levels and lowering descriptions that `harness.explain()` exposes through the capability matrix [@surfaces].

Run event callbacks show the planning rule in a small form. `RunOptions(on_event=...)` requires `run_event_callbacks`; capability tests show automatic Codex planning chooses `codex_app_server`, automatic Claude planning chooses `claude_python_sdk`, and explicit Codex CLI or Codex Python SDK selections fail before a provider run starts [@capability-tests]. See [Normalized Events](normalized-events) for the event objects delivered through that callback.

## Why this is not just configuration

Provider surfaces are not a cosmetic naming scheme. They control whether a [Yoke Harness](yoke-harness) may run, stream, resume, fork, use workflows, expose request callbacks, or report a feature as unavailable. The capability matrix answers what the surface can do before the provider turn starts [@surfaces].

This is why the decision note calls provider surfaces first-class. A generic provider default is acceptable for simple use, but advanced behavior must resolve to a concrete surface before Yoke claims that a feature exists [@decision].

## OpenCode: a third provider with no Python SDK

`opencode_server` is Yoke's third provider surface, alongside Claude and Codex [@models]. Unlike either of those, OpenCode ships no Python SDK — the adapter spawns `opencode serve --port 0` as a child process and drives it entirely over its documented HTTP API [@opencode-server]. That makes it closer in shape to `codex_app_server` (a locally spawned, long-lived process) than to a Python-SDK surface, and it reuses the same design precedent: the process/HTTP/polling mechanics stay synchronous and thread-backed, and the async `ProviderAdapter` methods bridge to them with `asyncio.to_thread` rather than a from-scratch asyncio rewrite [@opencode-server].

OpenCode's own SSE event stream was found unreliable for live progress narration in a prior live spike, so this adapter instead polls OpenCode's own SQLite database for new session parts while a turn is in flight, and uses the same polling loop to detect a tool call stuck past a threshold — a confirmed upstream OpenCode reliability gap, not a Yoke bug [@opencode-plan].

Sessions are first-class on this surface, not a one-shot-only wrapper — OpenCode's HTTP API supports real `GET /session`, `PATCH /session/:id`, `POST /session/:id/fork`, and `POST /session/:id/summarize` endpoints, so `start`/`send`/`close` map onto genuine multi-turn sessions and `run()` is a thin convenience wrapper over them [@opencode-server]. A forked session shares its parent's underlying server process rather than spawning a new one, so process termination is reference-counted the same way `CodexAppServer` reference-counts its shared app-server process, rather than tied to whichever session happens to close first [@opencode-server].

### Skills, subagents, and MCP: config-file compilation

OpenCode discovers skills, custom agents, and MCP servers from files and config, not a runtime registration API, so this adapter compiles Yoke's declarative model into that shape once per session rather than issuing calls during a turn. Inline skills and direct Yoke subagents render as `skills/<name>/SKILL.md` and `agents/<name>.md` (YAML frontmatter, `mode: subagent`) under a Yoke-owned deployment directory pointed at by `OPENCODE_CONFIG_DIR`, so nothing lands in the user's real project [@opencode-agents] [@opencode-server]. Direct subagents only — OpenCode documents no nested subagent-of-subagent invocation model to compile a recursive one against [@opencode-agents]. `agent.options["mcp_servers"]` renders as `{"mcp": {...}}` JSON passed through `OPENCODE_CONFIG_CONTENT`, OpenCode's highest-precedence config source, since there is no runtime add-server endpoint to call instead [@opencode-server].

### Live permission approval: polling, not SSE, and not the endpoint you'd expect

The original plan assumed pending permissions were "only learnable via SSE" and shipped an always-allow-all session, declaring `PERMISSIONS`/`REQUEST_EVENTS` `compiled`/`unsupported` [@opencode-plan]. That assumption was wrong: `GET /permission` is a real, non-deprecated, polling-discoverable endpoint listing every pending permission across sessions, confirmed live against a real `opencode serve` process — the same poll-not-SSE shape as the DB-poll progress watchdog, just polling OpenCode's HTTP API instead of its SQLite database [@opencode-permissions]. `Permissions.approval=ASK` now passes an ask-all session permission block instead of allow-all, and a dedicated `OpencodePermissionWatchdog` runs on its own thread alongside the progress watchdog, resolving each pending permission through `ProviderOptions.opencode.request_handler`/`.policy` — the same `RequestPolicy`/`Response` contract Claude and Codex app-server already use for their own request callbacks — and replying via `POST /permission/:id/reply` [@opencode-permissions] [@options]. The endpoint this adapter used to target for replies, `/session/:id/permissions/:permissionID`, turned out to be deprecated in OpenCode's own OpenAPI document; the reply now goes through the current one [@opencode-permissions].

### Plugins and hooks: a generated bridge, not just config

Plugins are OpenCode's one genuinely executable extension point (JS/TS auto-loaded from the same `OPENCODE_CONFIG_DIR` used for skills/agents), which splits into two very different features here. `agent.options["opencode_plugins"]` (name → raw JS source) is pure pass-through — Yoke writes whatever the caller supplies into `plugin/<name>.js` and does not generate or validate it, the same shape as MCP config [@opencode-server]. Hooks are the opposite: Yoke *generates* a `tool.execute.before` plugin that relays every tool call to a small local HTTP server this adapter starts (`OpencodeHookBridge`), which resolves the call through the same `request_handler`/`.policy` contract permissions use and replies with a decision [@opencode-hooks]. Confirmed live: mutating the reply's `args` actually changes the command OpenCode executes, and denying actually blocks the tool call with a graceful message back to the model — not just an observed-after-the-fact event [@opencode-hooks]. The bridge is opt-in (no configured handler means no plugin file and no server) and process-scoped rather than session-scoped: it's addressed by an env var fixed at `opencode serve` spawn time, and a fork shares its parent's process and env, so one bridge serves every session on that process, routing by the `sessionID` present in each tool call's own payload [@opencode-hooks].
