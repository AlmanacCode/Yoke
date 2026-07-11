# 0045 - Codex Python SDK is a supported automation surface

The Codex Python SDK is documented as `openai-codex`. It controls the local
Codex app-server over JSON-RPC, requires Python 3.10+, and published builds
include a pinned Codex CLI runtime dependency. The SDK has sync and async
clients, starts and resumes threads, runs turns, streams notifications, lists
models, and supports sandbox presets.

The public SDK API includes `thread_start(... cwd, developer_instructions,
model, sandbox, approval_mode, config ...)` and `AsyncThread.run(... cwd,
effort, model, output_schema, sandbox ...)`. That is enough for Yoke to expose
`Surface.CODEX_PYTHON_SDK` as a real adapter instead of a documented placeholder.

Yoke now ships `CodexPythonSdk`:

- `check()` verifies the optional `openai_codex` package import.
- `run()` and `start()` use `AsyncCodex`.
- `developer_instructions` carries Yoke agent instructions, prompt-compiled
  subagents, and prompt-compiled inline skills.
- Yoke goals are still prompt-compiled for this surface. The public SDK docs do
  not list `thread/goal/*` wrappers.
- Native mutable/readable goals remain a raw `codex_app_server` feature.

The local environment on 2026-07-04 did not have `openai_codex` installed, so
tests use a fake SDK module and the real optional dependency is declared under
`yoke[codex]`.

Sources checked on 2026-07-04:

- current Codex manual from `fetch-codex-manual.mjs`
- https://developers.openai.com/codex/sdk
- https://github.com/openai/codex/tree/main/sdk/python
- https://raw.githubusercontent.com/openai/codex/main/sdk/python/docs/api-reference.md
