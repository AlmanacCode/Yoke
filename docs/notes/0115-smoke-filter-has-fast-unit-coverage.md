# Smoke filter has fast unit coverage

`tests/test_smoke_harnesses.py` now covers the non-live smoke helper behavior.

The tests import `scripts/smoke_harnesses.py` as a module and exercise:

- alias filters such as `codex:app` and `claude:sdk`
- exact filters such as `codex:codex_cli`
- rejection of `codex:auto`, because readiness filters need concrete surfaces
- unknown-surface diagnostics that list available exact surfaces
- JSON readiness records that report exact surface names

This keeps the live smoke script safer to evolve. Real provider checks still live behind explicit smoke commands; fast tests cover the command-shaping logic without invoking Codex or Claude.
