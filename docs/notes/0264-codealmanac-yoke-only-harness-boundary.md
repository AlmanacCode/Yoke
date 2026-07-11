# 0264 - CodeAlmanac uses Yoke-only harness adapters

Date: 2026-07-04

## Change

CodeAlmanac's harness integration is now Yoke-only at the product adapter seam.
The old direct provider adapter packages were removed:

- `src/codealmanac/integrations/harnesses/claude/`
- `src/codealmanac/integrations/harnesses/codex/`
- `tests/test_claude_adapter.py`
- `tests/test_codex_adapter.py`
- `tests/test_codex_app_server_adapter.py`

The default app composition still exposes the same CodeAlmanac harness kinds:

- `HarnessKind.CODEX` -> `YokeHarnessAdapter(HarnessKind.CODEX, "codex:app")`
- `HarnessKind.CLAUDE` -> `YokeHarnessAdapter(HarnessKind.CLAUDE, "claude:sdk")`

## Why

Yoke now owns provider protocol details for Claude and Codex. Keeping old direct
Claude/Codex adapters in CodeAlmanac created two implementations of the same
runtime behavior, which made future harness work ambiguous. CodeAlmanac should
own lifecycle operations, job logging, changed-file validation, and product
contracts; Yoke should own provider-specific execution surfaces.

This preserves the desired hosted boundary from the usealmanac audit:

```text
usealmanac -> CodeAlmanac lifecycle -> Yoke -> Claude/Codex
```

`usealmanac` should not import Yoke directly unless hosted product state starts
needing provider-surface selection or Yoke capability reports.

## Tests updated

`tests/test_yoke_harness_adapter.py` now asserts that `create_app()` wires both
CodeAlmanac harness kinds to `YokeHarnessAdapter` with the expected provider
surfaces.

## Verification

Run from `/Users/rohan/Desktop/Projects/codealmanac`:

```bash
uv run pytest tests/test_yoke_harness_adapter.py tests/test_harnesses_service.py tests/test_diagnostics.py
uv run ruff check src/codealmanac/integrations/harnesses tests/test_yoke_harness_adapter.py
```
