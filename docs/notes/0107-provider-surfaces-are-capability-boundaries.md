# Provider surfaces are capability boundaries

Yoke should treat a provider surface as the capability boundary, not the provider name.

`provider="codex"` is not specific enough for a correct adapter. Codex exposes different behavior through the CLI, the Python SDK, and the app-server surface. The app-server shape is likely the richest surface for embedded use because it exposes live thread operations and streaming-oriented control, while the CLI remains closer to one-shot process execution. The Python SDK has its own native thread/session surface.

`provider="claude"` has the same pressure. The Claude Python SDK and CLI are related, but options such as resume, fork, settings, permissions, and streaming events do not always have the same shape or support level across surfaces.

The practical API consequence is that `Harness(provider=...)` can remain friendly, but Yoke's internal model needs a second axis:

```python
Harness(provider="codex", surface="app")
Harness(provider="codex", surface="sdk")
Harness(provider="codex", surface="cli")
Harness(provider="claude", surface="sdk")
Harness(provider="claude", surface="cli")
```

Yoke's concrete names currently stay explicit: `codex_app_server`, `codex_python_sdk`, `codex_cli`, `claude_python_sdk`, `claude_cli`, and conceptual documented surfaces such as `claude_typescript_sdk`.

The default can choose the best available surface, but explicit surfaces matter for predictable feature support. Capability checks should report the exact surface, for example `codex_app_server` supports a feature natively while `codex_cli` does not.

This keeps the SDK honest as it grows. Goals, workflows, streaming, interrupt, fork, custom subagents, settings, permissions, and session continuation should be mapped per surface instead of being flattened into one provider-level promise.
