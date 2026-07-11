# Codex app-server collaboration live smoke

Ran a live Yoke smoke against `codex_app_server` on 2026-07-04 using existing local Codex auth.

The first attempt used `CollaborationSettings(model="gpt-5.2")` and reached the provider, but app-server returned a provider error:

```text
The 'gpt-5.2' model is not supported when using Codex with a ChatGPT account.
```

The second attempt omitted `settings.model`, and app-server rejected the request before the turn started:

```text
Codex app-server turn/start: Invalid request: missing field `model`
```

The app-server `model/list` response for this account included:

- `gpt-5.5`
- `gpt-5.4`
- `gpt-5.4-mini`
- `gpt-5.3-codex-spark`

The successful smoke used typed Yoke options:

```python
RunOptions(
    provider=ProviderOptions(
        codex=CodexOptions(
            collaboration=Collaboration(
                mode="plan",
                settings=CollaborationSettings(
                    developer_instructions=None,
                    model="gpt-5.4-mini",
                    reasoning_effort="medium",
                ),
            )
        )
    )
)
```

Prompt:

```text
Reply with exactly: yoke-collab-ok
```

Result:

```text
OUTPUT yoke-collab-ok
EVENTS ['provider_session', 'warning', 'tool_use', 'tool_result', 'tool_use', 'tool_result', 'tool_use', 'text_delta', 'text_delta', 'text_delta', 'text_delta', 'text_delta', 'text_delta', 'text', 'context_usage', 'done']
```

Yoke implication: `CollaborationSettings.model` should stay optional in the Python model because Yoke should not hardcode account-specific defaults, but docs/examples should use a known available model or tell callers to consult `model/list`.

Follow-up slice added `Harness.models()` and `Model` so callers can discover account-supported models through Yoke:

```python
models = await harness.models()
```

Codex app-server implements this with `model/list`; Claude and Codex CLI currently report unsupported model listing.
