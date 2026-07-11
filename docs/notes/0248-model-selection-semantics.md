# 0248 - Model selection semantics

Date: 2026-07-04

Yoke now has a small public explanation object for model placement.

## Decision

Model preference belongs to the agent or the specific run/session, not to `Harness`.

- `Agent.model` is the default preference for that agent.
- `RunOptions.model` overrides the agent model for one run.
- `SessionOptions.model` overrides the agent model for a session.
- `Harness("provider:surface", ...)` selects the provider surface that interprets the model string.

This keeps the user-facing shape simple while preserving provider truth: not every surface can list or verify account-supported models.

## What changed

- Added `ModelSource` enum with `run`, `session`, `agent`, and `provider_default`.
- Added `ModelSelection` Pydantic model.
- Added `Harness.model_selection(options=None)`.
- Exported `ModelSelection` and `ModelSource` from `yoke`.
- Updated README with the model placement rule and examples.

## Provider truth

Codex app-server and Codex Python SDK expose live model-list APIs through Yoke, so `ModelSelection.verifiable` is true there and users can call `models()`.

Claude Python SDK accepts model aliases or full IDs through SDK options, but Yoke does not have a comparable live model-list API for that surface today, so `ModelSelection.verifiable` is false there. The provider validates the model at run time.

Codex CLI can receive a model through CLI/config lowering, but model listing belongs to a different Codex surface.

## Verified

Focused tests passed:

```bash
PYTHONPATH=src uv run pytest tests/test_capabilities.py
```

Result: 88 passed.

Focused ruff passed:

```bash
PYTHONPATH=src uv run ruff check src/yoke/models.py src/yoke/__init__.py tests/test_capabilities.py
```

Result: all checks passed.

Public API smoke passed:

```bash
PYTHONPATH=src python - <<'PY'
from pathlib import Path
from yoke import Agent, Harness, RunOptions, SessionOptions
h = Harness('codex:app', agent=Agent(instructions='x', model='agent-model'), cwd=Path.cwd())
print(h.model_selection().model_dump())
print(h.model_selection(RunOptions(model='run-model')).model_dump())
print(h.model_selection(SessionOptions(model='session-model')).model_dump())
PY
```
