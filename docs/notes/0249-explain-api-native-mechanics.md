# 0249 - Explain API for native mechanics

Date: 2026-07-04

Yoke now has a first-class local explanation API for the question: "how native is this exact agent/options shape on this harness?"

## What changed

- Added `Explanation`, a Pydantic model in `src/yoke/capabilities.py`.
- Added `Harness.explain(options=None, features=(), channel=None, runnable=True)`.
- Exported `Explanation` from `yoke`.
- Updated README to show `harness.explain(...)` near model selection.

## Shape

`harness.explain(...)` returns:

- `provider`, `surface`, `channel`
- `runnable`
- `ok`
- requested `features`
- `missing` features
- `model`, a `ModelSelection`
- `reports`, the per-feature `FeatureReport` rows from `Plan.reports`

Each feature report includes support level, note, lowering, recipes, and evidence. This makes the native/compiled/emulated/unsupported answer available without running a provider turn.

## Why this belongs in Yoke

The user-facing confusion was not only where `model` belongs. It was also how to tell whether subagents, goals, workflows, permissions, and events are native on a selected harness. Yoke already had the raw pieces: `Plan`, `FeatureReport`, `Status`, and `ModelSelection`. `explain(...)` stitches the local planning pieces together for one concrete call.

This is not a live validator. It does not prove account model access, auth, or provider runtime behavior. Use `check()`, `models()`, and live smokes for that. `explain(...)` is the zero-provider-call local lowering story.

## Examples covered by tests

- Codex app-server with an inherited agent model, goal, and structured output explains native support and model list verifiability.
- Claude Python SDK with declared subagents explains native declared subagent support and non-verifiable model listing.
- Codex app-server with `WorkflowOptions(native=True)` explains that provider-native workflow is unsupported on that surface.

## Verified

Focused tests passed:

```bash
PYTHONPATH=src uv run pytest tests/test_capabilities.py tests/test_public_api.py
```

Result: 93 passed.

Focused ruff passed:

```bash
PYTHONPATH=src uv run ruff check src/yoke/capabilities.py src/yoke/models.py src/yoke/__init__.py tests/test_capabilities.py tests/test_public_api.py
```

Result: all checks passed.

Public API smoke passed:

```bash
PYTHONPATH=src python - <<'PY'
from pathlib import Path
from yoke import Agent, Feature, Goal, Harness, RunOptions
h = Harness('codex:app', agent=Agent(instructions='x', goal=Goal('Finish'), model='gpt-5.4'), cwd=Path.cwd())
e = h.explain(RunOptions(model='gpt-5.4-mini'))
assert e.provider == 'codex'
assert e.model.model == 'gpt-5.4-mini'
assert e.report(Feature.GOAL) is not None
print('explain public API smoke passed')
PY
```
