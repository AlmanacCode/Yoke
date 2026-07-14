# Worklog

## Audit goal: ephemeral provider compilation

Critically audit whether Yoke should compile its canonical agent packages into
per-run provider representations for Codex and Claude.

Core questions:

- Which features have direct runtime APIs, which require files, and which are
  only prompt emulations?
- Can generated files live in an isolated temporary root without weakening
  discovery, resumption, concurrency, or debugging?
- Who owns transcripts, session history, tool events, generated artifacts,
  credentials, and cleanup?
- What must survive after the temporary bundle is removed?

Non-goals: do not modify production code or assume temporary compilation is
correct merely because it is convenient.

Success means every important feature has a provider-specific lowering,
lifetime, storage owner, and evidence grade, followed by a clear architecture
recommendation.

## 2026-07-11

- Read Yoke's folder loader, bundle compiler, status language, Codex app-server
  adapter, Claude adapter, skill-root wiring, and subagent lowering.
- Read CodeAlmanac's packaged agent collection and harness boundary.
- Live-smoked path-backed skills on Codex app-server and Claude Python SDK.
- Live-smoked declared subagents on Claude and generic collaboration spawning
  on Codex. Only Claude received its declaration through the provider SDK.
- Built a folder-only concurrent smoke. Both providers invoked the skill and
  child. Neither event stream attested the child's effective model. Codex had
  not materialized `.codex/agents`, so the smoke did not prove named custom
  agent discovery.
- Read current Claude SDK docs for programmatic subagents, filesystem skills,
  and local plugins. Read the open-source Codex app-server protocol.
- Found that Yoke's `provider_native` subagent headline can obscure the separate
  fact that `declared_subagents` is only `compiled` on app-server.
- Produced the HTML report with exact placement rules and remediation.
- Verified that `Skill.from_text(...)` is prompt text on both active adapters;
  only path-backed skills enter Codex extra roots or Claude plugin paths.
- Tested Codex absolute `agents.<name>.config_file` registration with a secret
  stored only in the child role. Startup accepted it, but the default V2 tool
  hid role selection. Unhiding metadata produced a reserved-tool-schema 400;
  the V1 collaboration path spawned a child but did not return the secret.
  Therefore registration exists, while usable native named-role selection via
  the current app-server path remains unproven.
- Audited ephemeral provider compilation across instructions, skills,
  subagents, models, tools, permissions, hooks, MCP, plugins, structured output,
  streaming, sessions, goals, environment, and generated work files.
- Live-tested native transcript persistence with `uv run --extra all`. Codex's
  thread appeared in session listing and returned one normalized turn. Claude's
  one-shot `Run.provider_session_id` was recovered from events and read back
  three transcript messages. A one-shot run intentionally has no live
  `run.session`; that is an API distinction, not lost history.
- Concluded that runtime files should be immutable and session-scoped, while a
  secret-free compilation receipt must remain durable so resume can recreate
  the same provider projection and detect definition drift.
- Traced Codex named-role spawning through current `openai/codex` source and
  installed `codex-cli 0.144.1`. Current source has the intended native path:
  `spawn_agent(agent_type=...)` calls `apply_role_to_config`, which loads the
  registered absolute role file. Full-history forks deliberately reject role,
  model, and effort overrides; named roles require a fresh or partial fork.
- Verified through `config/read` that app-server received the injected
  `agents.reviewer` declaration from session flags. Nevertheless, strict live
  children recorded `agent_role: null`, including an explicitly requested
  built-in `explorer` role. Asking the running model to enumerate its actual
  spawn schema returned only `task_name`, `message`, and `fork_turns`.
- Setting `hide_spawn_agent_metadata=false` exposes the source-level role field
  but the live model endpoint rejects the resulting reserved tool schema with
  HTTP 400. Root cause: the installed/runtime backend contract hides or rejects
  `agent_type`; Yoke prompt wording and role-file materialization are not the
  failing boundary.
- Independent source review confirmed that project `.codex/agents`, user
  `${CODEX_HOME}/agents`, and absolute `[agents.<name>].config_file` declarations
  all converge on the same role registry. Folder placement therefore cannot
  change whether `agent_type` is exposed. Native named roles also require
  `fork_turns="none"` or a positive partial fork because full-history forks
  intentionally inherit the parent role.
- Repeated the schema probe with isolated `@openai/codex@0.145.0-alpha.4`.
  Default-hidden metadata returned `SCHEMA_MISSING`; enabling metadata produced
  the same reserved `collaboration.spawn_agent` HTTP 400 as stable 0.144.1.
  The mismatch is not resolved by the currently published alpha client.
