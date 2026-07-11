# Folder save refuses runtime-only options by default

Date: 2026-07-04

`Agent.save(...)` now refuses to silently omit runtime-only SDK values.

The concrete case is a workflow step with `Step(run=RunOptions(provider=ProviderOptions(codex=CodexOptions(app_server=CodexAppServerOptions(request_handler=...))))))`. `request_handler` is a live Python callback. It cannot be serialized into a Yoke folder, and pydantic excludes it from `model_dump()`. Before this slice, saving such a step would produce a folder that looked complete but had lost the callback.

Default behavior is now fail-fast:

```python
agent.save(path)
```

If runtime-only fields are present, Yoke raises a `YokeError` before writing any files. The error includes the dotted path, such as:

```text
workflows.review.steps.review.run.provider.codex.app_server.request_handler
```

Callers can explicitly opt into a lossy folder copy:

```python
agent.save(path, allow_runtime_only=True)
```

That saves serializable fields and omits runtime-only fields. This is useful for sharing the authored folder while keeping callbacks in SDK code.

Design implication: folder-native and SDK-native are peers, but not identical. Serializable authored intent belongs in folders. Live Python values belong in SDK code. The framework should make that boundary obvious at save time instead of relying on users to remember which fields pydantic excluded.

Next pressure test: inspect other escape hatches (`raw` dicts, provider clients, future custom tools) and decide which need runtime-only markers versus ordinary serialization.
