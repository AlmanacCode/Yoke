# Auto surface means capability-selected

Yoke now treats `surface="auto"` the same as leaving `surface` unset.

The behavior is intentional. A missing surface does not mean "Codex CLI forever" or "Claude Python SDK forever"; it means Yoke should keep the provider default for plain one-shot work and select a richer runnable surface when requested features require one.

Example:

```python
harness = Harness(provider="codex", surface="auto", agent=agent, cwd=repo)
harness = harness.require("readable_goal")
assert harness.surface == "codex_app_server"
```

This keeps the public API readable while preserving the deeper design rule: provider names are not capability boundaries. Codex CLI, Codex Python SDK, Codex app-server, Claude CLI, Claude Python SDK, and Claude TypeScript SDK all need separate capability profiles.
