# 0247 - Package and README polish

Date: 2026-07-04

This slice made Yoke's public package surface and README match the current implementation state.

## What changed

- `README.md` now describes Yoke as a private source package installed editable from this repo or imported by sibling apps such as CodeAlmanac through `../Yoke`.
- The install section notes that Yoke ships `py.typed`.
- The readiness section now starts with `scripts/smoke_harnesses.py --plan` and `--plan --json` instead of a stale list of live flags.
- The README documents that smoke plan rows include provider, surface, channel, feature, safety, and exact command.
- The README lists the new live Codex Python SDK stream smoke and Claude permission callback smoke.
- The README records two provider truths found during live testing: Codex SDK stream proves transport/completion but not final assistant text; Claude `can_use_tool` needs an async prompt stream and native permission result objects.
- The status section now says CodeAlmanac imports Yoke through an editable sibling package instead of listing CodeAlmanac integration as not final.
- `pyproject.toml` now has package keywords and a repository URL for `almanaccode/Yoke`.

## Verified

Public API import smoke passed:

```bash
PYTHONPATH=src python - <<'PY'
import yoke
from yoke import Agent, Goal, Harness, Workflow, matrix_for
missing = [name for name in yoke.__all__ if not hasattr(yoke, name)]
assert not missing, missing
agent = Agent(instructions='You are careful.', goal=Goal('Finish safely.'))
harness = Harness('codex:app', agent=agent, cwd='.')
assert str(harness.provider) == 'codex'
assert str(harness.surface) == 'codex_app_server'
assert matrix_for('codex')
Workflow.from_script('audit', "return 'ok'")
print('public API import smoke passed')
PY
```

Smoke matrix JSON passed:

```bash
PYTHONPATH=src python scripts/smoke_harnesses.py --plan --json --surface codex:sdk --surface claude:sdk
```

Package build passed:

```bash
uv build
```

Result: built `dist/yoke-0.0.0.tar.gz` and `dist/yoke-0.0.0-py3-none-any.whl`.

## Remaining README/API risk

The README is now accurate but still too long for a new user. A future polish pass should split the full surface reference into docs pages and make the README a shorter landing page plus links.
