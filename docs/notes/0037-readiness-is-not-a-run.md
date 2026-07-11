# Readiness is not a run

Date: 2026-07-04

Yoke now has a small readiness surface:

```python
readiness = await harness.check()
readiness = harness.check_sync()
```

The result is:

```python
class Readiness(YokeModel):
    provider: Provider
    surface: Surface | str | None = None
    available: bool
    message: str
    fix: str | None = None
    raw: str | None = None
```

Readiness answers "is this provider surface available enough to try a run?"

It is not:

- a dry-run
- a test prompt
- a model-list call
- a credential setup flow
- a guarantee that the next agent turn will succeed

Current provider checks:

- Codex CLI: `codex login status`
- Codex app-server: `codex login status`
- Claude Python SDK: import `claude_agent_sdk`, then accept `ANTHROPIC_API_KEY` or `claude auth status`

This boundary mirrors the CodeAlmanac integration pressure. CodeAlmanac has local status/setup/doctor concerns and separate lifecycle execution concerns. Yoke should give embedders readiness facts without making them start a provider session or parse provider-specific command output.
