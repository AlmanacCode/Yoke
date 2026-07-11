# 0254 - Extra install command cleanup

Date: 2026-07-04

## Change

Provider readiness and missing-package errors now point users at the
distribution name:

```bash
pip install almanac-yoke[claude]
pip install almanac-yoke[codex]
```

The import package remains:

```python
from yoke import Agent, Harness
```

## Why

After the distribution rename, old messages still suggested
`pip install yoke[...]`. That would install or refer to the wrong package name
because PyPI already has a separate `yoke` project.

## Verification

Stale-string search:

```bash
rg -n "pip install yoke|yoke\\[" src tests README.md docs/quickstart.md docs/reference.md pyproject.toml
```

Result: only the new `almanac-yoke[...]` strings remain in source and tests.

Focused tests:

```bash
PYTHONPATH=src uv run pytest \
  tests/test_codex_python_sdk.py \
  tests/test_claude_readiness.py \
  tests/test_claude_options.py \
  tests/test_claude_events.py \
  tests/test_capabilities.py \
  tests/test_public_api.py
```

Result:

```text
152 passed
```

Ruff:

```bash
PYTHONPATH=src uv run ruff check \
  src/yoke/providers/codex_sdk.py \
  src/yoke/providers/claude.py \
  tests/test_codex_python_sdk.py
```

Result:

```text
All checks passed!
```
