# 0272 CLI explain and status

Yoke folder users can now inspect a named agent before running it:

```bash
yoke explain agents codealmanac
yoke status agents codealmanac
```

Both commands use the same path as `yoke run`:

```text
agents/yoke.yaml -> Collection -> Agent -> Harness
```

`yoke explain` is local. It does not start a provider turn. It prints the
selected surface, model source, required features, missing features, and feature
lowering rows.

`yoke status` calls the provider readiness check and prints the full semantic
status payload:

- readiness
- surface capability report
- goals
- workflows
- subagents
- skills, plugins, hooks, and MCP
- control/auth
- permissions
- history
- exposure/configuration mode

This keeps the public folder approach simple while exposing the native-vs-
compiled-vs-emulated distinctions that already exist in the SDK.

Verification:

```bash
uv run pytest tests/test_cli.py tests/test_readiness.py tests/test_capabilities.py
uv run ruff check src/yoke/cli.py tests/test_cli.py
```
