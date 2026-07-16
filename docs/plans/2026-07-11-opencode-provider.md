# OpenCode Provider Implementation Plan

**Status (2026-07-12):** Task 4's PERMISSIONS/REQUEST_EVENTS row and the "no
polling-discoverable pending permission signal" claim below turned out to be
wrong — `GET /permission` is real and non-deprecated. Live permission
approval, filesystem-agent subagents, and both PLUGINS and HOOKS (all listed
`UNSUPPORTED`/`UNKNOWN` below) shipped after this plan was written. This
document is kept as the historical record of the initial implementation;
see [Provider Surfaces](../../almanac/concepts/provider-surfaces.md) and
`src/yoke/surfaces.py` for current, accurate capability status.

**Goal:** Add OpenCode as Yoke's third provider, so any Yoke consumer (CodeAlmanac included) can run agents on OpenCode through the same `Harness` API as Claude and Codex.

**Architecture:** `Provider.OPENCODE` / `Surface.OPENCODE_SERVER`. OpenCode has no Python SDK — it's a locally spawned HTTP server (`opencode serve --port 0`) with a documented OpenAPI surface. Following the precedent already set by `CodexAppServer` (`providers/codex_app/process.py`), the process/HTTP/DB-polling mechanics stay synchronous and thread-backed — the same shape as the proven CodeAlmanac implementation being ported — and the async `ProviderAdapter` methods bridge to them via `asyncio.to_thread`, rather than a ground-up asyncio rewrite that would need fresh live-testing to trust. OpenCode's own SSE stream was found unreliable for live progress in a prior spike (CodeAlmanac, 2026-07-09), so this adapter polls OpenCode's own SQLite database for live events and stuck-tool-call detection instead. Sessions are first-class (`start`/`send`/`close`), not a one-shot-only wrapper: OpenCode's HTTP API supports session reuse natively, and Yoke shouldn't be narrower than the surface it wraps.

**Tech Stack:** Python 3.11+, httpx (sync, bridged via `asyncio.to_thread`), stdlib `sqlite3`, pytest/pytest-asyncio.

**Evidence base:** https://opencode.ai/docs/server/ (session/auth/mcp/permission endpoints), https://opencode.ai/docs/skills/ (native `.opencode/skills/*/SKILL.md`, also reads `.claude/skills/`), https://opencode.ai/docs/mcp-servers/ (config-file only, no runtime API), https://opencode.ai/docs/providers/, https://opencode.ai/docs/cli/. Domain logic (server spawn, part-mapping, stuck-tool-call heuristics) ported from CodeAlmanac's `integrations/harnesses/opencode/*` (pre-migration), which spiked and validated these HTTP behaviors live.

---

### Task 1: Provider/Surface plumbing

- Add `Provider.OPENCODE = "opencode"` and `Surface.OPENCODE_SERVER = "opencode_server"` to `models.py`.
- Register in `adapters.py`: `_builtin_surfaces["opencode"] = {"opencode_server"}`, `default_adapter()` branch.
- `surfaces.py`: `default_surface()`, `SURFACE_CHANNELS` (`Channel.APP_SERVER` — same shape as `codex_app_server`, a locally spawned long-lived process, not a CLI one-shot or SDK import), `SURFACE_RUNTIMES` (`"opencode_server"`), `SURFACE_EVIDENCE` citing the docs above.
- Add failing tests asserting `adapter_for("opencode")` resolves and `has_adapter("opencode", "opencode_server")` is true before any adapter exists (`test_provider_surface.py` pattern).

### Task 2: Async process + HTTP mechanics

- `providers/opencode/process.py`: `asyncio.create_subprocess_exec("opencode", "serve", "--port", "0", ...)`, async stdout scan for `listening on http://127.0.0.1:(\d+)` with `asyncio.wait_for` deadline (direct async port of the existing `_wait_for_listening`). Windows note carried over: resolve via `shutil.which` first.
- `providers/opencode/http.py`: `httpx.AsyncClient` wrapping `GET /config/providers`, `POST /session`, `GET /session`, `GET /session/:id`, `PATCH /session/:id`, `DELETE /session/:id`, `POST /session/:id/fork`, `POST /session/:id/abort`, `POST /session/:id/summarize`, `POST /session/:id/message`, `POST /session/:id/permissions/:permissionID`, `PUT /auth/:id`, `GET /agent`.
- `providers/opencode/db.py` (new — Yoke can't import CodeAlmanac's `query_readonly_or_empty`): stdlib `sqlite3.connect(f"file:{path}?mode=ro", uri=True)` wrapped in `asyncio.to_thread`, tolerating missing file/table/corrupt db by returning `()`.
- Tests: fake `opencode serve` (a tiny stub script) or a `respx`/`httpx.MockTransport`-backed fake server, matching `test_codex_app_server_params.py`'s fixture style.

### Task 3: Event normalization + progress polling

- `providers/opencode/parts.py`: port `map_opencode_part` (text/reasoning/tool/patch/step-finish) to yield Yoke `Event` objects — `EventKind.TEXT`, `TOOL_USE`/`TOOL_RESULT` (with `Tool`/`tool_is_error`), `TOOL_SUMMARY` (reasoning + patch), `CONTEXT_USAGE` (step-finish → `Usage`). Task-tool spawns become `Event(kind=TOOL_USE, agent=AgentCall(agent_type="task", new_thread_id=child_session_id, prompt=...))` — Yoke has no dedicated agent-spawn event kind, it rides the existing `agent` field.
- `providers/opencode/progress.py`: `asyncio.Task` polling loop (replaces the thread + `queue.Queue` + `threading.Event` original) reading `part`/`message` rows scoped to known session ids, discovering child sessions via the `task` tool the same way, and raising a stuck-tool-call error past `stuck_after_seconds` (default 240s — this is a confirmed upstream OpenCode reliability gap, not a Yoke bug; cite the same tracking issue in the docstring).
- The send-vs-watchdog race stays the original's thread-join-with-timeout loop (send on one thread, watchdog on another, main thread polls `watchdog.stuck_reason` while joining with a short timeout) — this is synchronous code bridged via `asyncio.to_thread` at the adapter boundary, not native asyncio tasks.
- Tests: feed a fake sqlite db with part/message rows across poll cycles, assert event ordering, child-session discovery, and stuck detection at the threshold.

### Task 4: `OpencodeServer` adapter (`providers/opencode_server.py`)

- Implement `ProviderAdapter`: `check` (brief server + `GET /config/providers`, empty list → not ready), `models` (native, from providers list), `start`/`send`/`close` as the primary path, `run` as `start → send → close`.
- `list_sessions`/`read_session`/`rename`/`fork`/`interrupt`/`compact` map directly to the endpoints in Task 2 — these are real, not emulated, per the OpenAPI surface.
- `login(method="api_key", api_key=...)` → `PUT /auth/:id`. OAuth authorize/callback exists in the API but is out of scope for this task (no interactive browser flow in this adapter yet) — declare it explicitly rather than silently doing nothing.
- Permissions: session creation always passes the allow-all block. `POST /session/:id/permissions/:permissionID` exists to *answer* a request, but there is no polling-discoverable way to learn a permission is *pending* (only SSE, which this adapter deliberately avoids) — do not build an approval-callback loop this pass; see the corrected capability table.
- Skills: render Yoke skills as `SKILL.md` files under a Yoke-owned deployment directory, and set `OPENCODE_CONFIG_DIR` (per https://opencode.ai/docs/config/) to point OpenCode at it — this reuses `native_skills.py` rendering but needs its own deployment wiring (`runtime_deployment.py` currently branches `if provider is Provider.CODEX else _write_claude(...)` — a binary dispatch that will silently write Claude-shaped files for OpenCode unless corrected to an exhaustive branch alongside a new `_write_opencode`. `runtime_owner_pid()`'s stale-deployment reclaim also hardcodes `{Provider.CLAUDE.value, Provider.CODEX.value}` and needs `Provider.OPENCODE.value` added, or opencode runtime dirs never get reclaimed).
- Declared subagents: `Support.COMPILED` — lower Yoke subagents into whatever file shape `GET /agent` reads from (check `opencode` source/docs for the exact file format before implementing; if undocumented, mark `Support.UNKNOWN` with a note rather than guessing the shape).
- Failure classification ported from `failures.py` (not_installed, server_start_failed, stuck_tool_call, timeout, generic).

### Task 5: Capability matrix + docs

- `surfaces.py` `MATRIX[(Provider.OPENCODE, Surface.OPENCODE_SERVER)]` per the table below, plus `FEATURE_EVIDENCE`/`FEATURE_LOWERING`/`FEATURE_RECIPES` entries citing the URLs above. Done.
- Almanac docs: no existing per-provider pages exist for Claude/Codex either (provider specifics already live inside `almanac/concepts/provider-surfaces.md`), so a new standalone `opencode.md` page would break that established pattern rather than follow it. Added an "OpenCode: a third provider with no Python SDK" section to `provider-surfaces.md` instead, documenting the DB-polling decision, why SSE was rejected, why permissions are compiled not native, and the shared-process/fork reference-counting design. Done.
- `pyproject.toml`: confirmed no new optional dependency needed — `httpx` is already a base dependency, not extras-gated, and no OpenCode Python SDK exists to depend on.
- `docs/reference.md`: added the `opencode_server` row to the surfaces/capabilities table. Done.
- `README.md`: the tagline ("A Python SDK for building agents on Claude Code and Codex") and intro paragraph became inaccurate once this lands — updated tagline, intro, badge row, quickstart install-extras note (OpenCode needs none), the `"codex"`/`"claude"` swap paragraph, and the surfaces table to include OpenCode. Left the "How it compares" table's Claude Agent SDK/Codex SDK row unchanged — it specifically compares official vendor SDKs, and OpenCode has no equivalent official SDK to list there; editing it would make it less accurate, not more. Done.

| Feature | Support | Note |
|---|---|---|
| SESSION / SESSION_LIST / SESSION_READ / SESSION_RENAME / SESSION_COMPACT / FORK / INTERRUPT | NATIVE | direct endpoint per Task 4 |
| MODELS | NATIVE | `GET /config/providers` |
| LOGIN | NATIVE (api_key only) | `PUT /auth/:id`; OAuth path unimplemented, noted |
| PERMISSIONS | COMPILED | blanket allow/deny set at session creation only — see below |
| REQUEST_EVENTS / REQUEST_CALLBACKS | UNSUPPORTED | corrected during implementation: `POST /session/:id/permissions/:permissionID` can *answer* a pending request, but there is no polling-discoverable "pending permission" signal — OpenCode's docs indicate this is only learnable via SSE, and this adapter deliberately does not depend on SSE (see Task 3). Revisit if SSE reliability for this one low-volume signal is separately confirmed. |
| SKILLS | NATIVE | `OPENCODE_CONFIG_DIR` env var points OpenCode at a Yoke-generated skill directory (`skills/<name>/SKILL.md`) without touching the user's project — confirmed via https://opencode.ai/docs/config/. Reuses `native_skills.py` rendering. |
| INLINE_SUBAGENTS | NATIVE | `task` tool spawns, confirmed by CodeAlmanac's spike |
| DECLARED_SUBAGENTS | COMPILED or UNKNOWN | pending file-format confirmation, Task 4 |
| STREAMING / RUN_EVENT_CALLBACKS | EMULATED | DB-poll based; native SSE spiked unreliable |
| MCP | COMPILED | config-file only (`OPENCODE_CONFIG_CONTENT` env var), no runtime add-server API |
| SESSION_TAG, GOAL, GOAL_LOOP, MUTABLE_GOAL, READABLE_GOAL, NATIVE_WORKFLOW, STRUCTURED_OUTPUT, COLLAB_AGENT_TOOLS, COLLABORATION_MODE, HOOKS, PLUGINS | UNSUPPORTED | no endpoint/evidence found |

**Permissions default:** session creation always passes the allow-all permission block (`OPENCODE_ALLOW_ALL_PERMISSION`), matching CodeAlmanac's proven behavior. `RunOptions.permissions`/`SessionOptions.permissions` with a non-default `Approval` can be lowered to a narrower session-creation-time permission block, but there is no live interactive approval loop this pass.

### Task 6: Verify

- Full `pytest` + `ruff check .`.
- Live lab: readiness check, one-shot run producing text + tool use, a multi-turn session (start/send/send/close), a forced permission-approval round-trip, and a deliberately long-running tool call to confirm stuck-detection fires (or a mocked-timing test if 240s is impractical live).
- Update `docs/reference.md` provider table.
