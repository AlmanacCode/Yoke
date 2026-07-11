# Compact provider-surface specs

Date: 2026-07-04

Yoke now accepts compact provider-surface specs in the same places where users would otherwise pass `provider=` plus `surface=`.

```python
Harness("codex:app", agent=agent, cwd=repo)
Session("claude:sdk", id=session_id)
profile_for("codex:app-server")
```

This makes the core idea easier to read: a runnable harness is a provider surface, not just a provider.

The compact form is input sugar. Yoke still stores and reports the exact normalized values:

- `codex:app` becomes `provider="codex"` and `surface="codex_app_server"`.
- `claude:sdk` becomes `provider="claude"` and `surface="claude_python_sdk"`.
- Hyphen aliases such as `app-server` and `agent-sdk` are accepted and normalized.

If the compact string conflicts with an explicit surface, construction fails:

```python
Harness("codex:app", surface="cli", agent=agent, cwd=repo)
```

raises a validation error. Yoke should not silently pick one surface when two inputs disagree.

This landed in:

- `src/yoke/models.py`
- `src/yoke/surfaces.py`
- `tests/test_capabilities.py`
- `README.md`
- `docs/notes/0175-provider-surfaces-are-first-class.md`

The remaining design question is default selection. `provider="codex"` still has a provider-level default, while advanced operations use `require(...)` and option-derived features to select the strongest runnable surface. CodeAlmanac should not rely on that default; its first Yoke-backed adapter should explicitly use `codex:app`.

## Verification

After the normalization fix for custom surfaces:

```bash
PYTHONPATH=src uv run pytest
uv run ruff check .
```

passed with 247 tests and a clean Ruff run.

Relayforge checkpoint failed because `DISCORD_BOT_TOKEN` is not present in the environment.
