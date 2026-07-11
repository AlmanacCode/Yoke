# Model list API

Added `Harness.models()` and `Harness.models_sync()` after the Codex app-server collaboration smoke showed that `collaborationMode.settings.model` must be both present and account-supported.

Public model:

```python
class Model:
    id: str
    hidden: bool
    reasoning_efforts: tuple[str, ...]
    raw: object | None
```

Current support:

- Codex app-server: native through `model/list`.
- Codex CLI: unsupported in Yoke for now.
- Claude Python SDK: unsupported in Yoke for now.

Design note: model listing is a surface capability, not a global provider capability. The same account and model provider can expose different catalogs or metadata through different entrypoints.

`Model.raw` is retained because app-server model catalogs include provider-specific metadata that Yoke should not discard before it has a typed use for it.

Live smoke on 2026-07-04:

```text
COUNT 4
FIRST [('gpt-5.5', ('low', 'medium', 'high', 'xhigh')), ('gpt-5.4', ('low', 'medium', 'high', 'xhigh')), ('gpt-5.4-mini', ('low', 'medium', 'high', 'xhigh')), ('gpt-5.3-codex-spark', ('low', 'medium', 'high', 'xhigh'))]
```
