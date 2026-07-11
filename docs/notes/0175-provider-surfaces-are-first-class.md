# Provider surfaces are first-class

Date: 2026-07-04

Yoke must not treat `provider="codex"` or `provider="claude"` as enough information to know what features exist. The same provider exposes different capabilities through different surfaces.

## Source signals

OpenAI documents `codex app-server` as the deep integration surface for product embeddings: authentication, conversation history, approvals, and streamed agent events. The same page says CI/job automation should use the Codex SDK instead. That means app-server and SDK are not interchangeable surfaces.

Claude Agent SDK documentation splits its Python API into `query()` and `ClaudeSDKClient`. `query()` is closer to one-off runs; `ClaudeSDKClient` is the continuous conversation surface. The docs also show that TypeScript has features Python does not expose, such as `applyFlagSettings()` for changing some running-session settings.

Claude subagents and skills are native Claude Code concepts. Claude documents custom subagents as independent contexts with their own system prompt, tool access, and permissions. Claude skills are folder/file based, load lazily, and can run in subagents. These concepts are not just generic prompts.

## Design consequence

Yoke capabilities must be keyed by provider surface, not provider name.

Good:

```python
Harness(provider="codex", surface="app-server", agent=agent)
Harness(provider="claude", surface="python-sdk", agent=agent)
Harness("codex:app", agent=agent)
Harness("claude:python", agent=agent)
```

Bad:

```python
Harness(provider="codex", agent=agent)  # then pretending every Codex feature exists
```

A provider-level default is fine for ergonomics, but it must resolve to a concrete surface before capabilities are checked or a run starts.

## Capability model

Yoke should keep the current capability matrix shape and make it unavoidable in new features:

- `Feature.STREAMING_EVENTS` may be true for Codex app-server and false or partial elsewhere.
- `Feature.SESSION_READ` and `Feature.SESSION_COMPACT` may exist on app-server but not CLI.
- `Feature.SUBAGENTS` may be native on Claude surfaces and emulated or unsupported elsewhere.
- `Feature.WORKFLOWS` may be a Yoke-level abstraction even when only one provider has native pieces.
- `Feature.GOALS` must distinguish provider-native long-running goal semantics from Yoke-managed objective metadata.
- `Feature.RUNTIME_SETTINGS` must distinguish startup-only options from mid-session mutations.

The matrix should answer three questions separately:

1. Is the feature native on this surface?
2. Can Yoke emulate it safely on this surface?
3. If unsupported, what should the user do instead?

## API pressure

The natural public API probably wants both convenience and explicitness:

```python
harness = Harness("codex:app", agent=agent, cwd=repo)
print(harness.status().features)
```

For teams that want defaults:

```python
harness = Harness(provider="codex", agent=agent, cwd=repo)
assert harness.surface.name == "app"
```

The important part is that `harness.surface` becomes concrete before execution.

## Implementation pressure

Provider packages should not be named only by provider. They should make surface differences obvious in code:

```text
src/yoke/providers/codex/app.py
src/yoke/providers/codex/sdk.py
src/yoke/providers/codex/cli.py
src/yoke/providers/claude/python.py
src/yoke/providers/claude/typescript.py
src/yoke/providers/claude/cli.py
```

If we later collapse files, the public model should still expose the surface boundary.

## CodeAlmanac integration consequence

CodeAlmanac should import Yoke at its current narrow harness adapter seam, but the adapter must choose a concrete Yoke surface.

Likely defaults:

- Claude: `claude:python-sdk`, because CodeAlmanac is Python-native today.
- Codex: `codex:app-server`, because CodeAlmanac already uses app-server features and event streaming.

CodeAlmanac should not ask Yoke for generic `codex` behavior and then assume app-server-only features are present.

## Landed pressure tests

Yoke now accepts compact provider-surface specs in the public model layer:

```python
Harness("codex:app", agent=agent, cwd=repo)
Session("claude:sdk", id=session_id)
profile_for("codex:app-server")
```

The compact form is input sugar only. Yoke stores provider and surface
separately and reports exact names such as `codex_app_server` and
`claude_python_sdk`.

Conflicting inputs fail loudly:

```python
Harness("codex:app", surface="cli", agent=agent, cwd=repo)
```

raises a validation error instead of silently picking one source of truth.

## Remaining pressure tests

- Should `provider="codex"` default to app-server for product integrations and SDK for CI-like one-off runs, or should Yoke require explicit surface once advanced features are requested?
- Should capability checks happen eagerly at construction or lazily at run start?
- Should goals be `Goal` metadata for every surface, with `native=True/False` in status, rather than a separate API?
