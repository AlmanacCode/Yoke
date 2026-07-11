# Provider and surface enums

Date: 2026-07-04

Yoke now exposes `Provider` and `Surface` as `StrEnum` models instead of literal-only type aliases.

Users can still write the simple string shape:

```python
Harness(provider="codex", surface="codex_app_server", ...)
```

Pydantic normalizes those values to:

```python
Provider.CODEX
Surface.CODEX_APP_SERVER
```

Users who prefer enum-native code can write:

```python
Harness(
    provider=Provider.CODEX,
    surface=Surface.CODEX_APP_SERVER,
    ...
)
```

The adapter registry normalizes provider and surface keys to strings. Built-in adapters can keep declaring `provider = "codex"` and `surface = "codex_cli"` without fighting the public enum model.

This follows the SDK taste goal: simple public calls, typed internal language, and no clever abstraction tax.
