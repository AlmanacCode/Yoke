# Default adapters and README honesty

The public API should make the clean path true:

```python
harness = Harness(provider="claude", agent=agent, cwd=repo)
result = await harness.run("Implement the feature.")
```

Before this slice, examples had to call `.with_adapter(Claude())`. That is still useful for embedded applications that own provider construction, but it is too much ceremony for the common case.

Yoke now lazily constructs built-in adapters:

- `provider="claude"` -> `Claude()`
- `provider="codex"` or `surface="codex_cli"` -> `Codex()`
- `provider="codex", surface="codex_app_server"` -> `CodexAppServer()`

The adapter is registered after construction so repeated calls reuse the same object.

This does not hide provider surfaces. Unknown surfaces still raise `AdapterNotFound`.

The README was also updated because the old folder-skills section had become false. Packaged Yoke folder skills are now native on:

- Claude Python SDK through local plugins.
- Codex app-server through `skills/extraRoots/set`.

Codex CLI still prompt-compiles skills. Inline text skills still prompt-compile everywhere because they do not have a filesystem root for native provider discovery.

