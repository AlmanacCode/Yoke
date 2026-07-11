# 0262 - Codex app-server experimental thread and turn options

Date: 2026-07-04

## Change

Yoke now exposes high-value Codex app-server `thread/start` and `turn/start`
fields through `CodexOptions`:

- `permissions`
- `runtime_workspace_roots`
- `environments`
- `selected_capability_roots`
- `allow_provider_model_fallback`
- `service_tier`
- `client_user_message_id`

`CodexOptions.approvals_reviewer` is now also emitted to app-server params. The
field already existed on the model, but this slice wires it into `thread/start`
and `turn/start`.

## Why

Codex app-server is the primary Yoke v1 Codex surface. Its JSON-RPC protocol has
richer thread/turn controls than the current public Python SDK wrapper exposes.
Yoke should be provider-neutral at the model boundary, but it should not hide
real provider strengths behind a weak common denominator.

## Wire behavior

`permissions` selects an app-server permission profile, such as `:workspace`.
When `permissions` is present, Yoke sends `permissions` and deliberately omits
legacy `sandbox` on `thread/start` and `sandboxPolicy` on `turn/start`. Codex
app-server documents that those fields cannot be combined.

`runtime_workspace_roots`, `environments`, and `selected_capability_roots` are
serialized to the documented camelCase fields:

- `runtimeWorkspaceRoots`
- `environments`
- `selectedCapabilityRoots`

`allow_provider_model_fallback`, `service_tier`, and `client_user_message_id`
serialize to:

- `allowProviderModelFallback`
- `serviceTier`
- `clientUserMessageId`

Using any typed experimental app-server field makes `codex_experimental_api(...)`
return `True`, so the adapter initializes the app-server process with
`initialize.capabilities.experimentalApi` automatically.

## Files changed

- `src/yoke/options.py`
- `src/yoke/providers/codex_app_server.py`
- `src/yoke/providers/codex_app/policy.py`
- `tests/test_codex_app_server_params.py`
- `docs/reference.md`

## Verification

Focused tests:

```bash
uv run pytest tests/test_codex_app_server_params.py tests/test_capabilities.py tests/test_folders.py
uv run ruff check src/yoke/options.py src/yoke/providers/codex_app_server.py src/yoke/providers/codex_app/policy.py tests/test_codex_app_server_params.py
```

Result: 147 tests passed; Ruff passed.

Live Codex app-server smoke:

```bash
uv run --with openai-codex python - <<'PY'
from pathlib import Path
from yoke import Agent, CodexOptions, Harness, ProviderOptions, RunOptions

repo = Path.cwd()
harness = Harness(
    "codex:app",
    agent=Agent(instructions="You are a concise Yoke live smoke agent."),
    cwd=repo,
)
result = harness.run_sync(
    "Reply with exactly: yoke-codex-permissions-profile-smoke",
    RunOptions(
        inherit_goal=False,
        max_turns=1,
        provider=ProviderOptions(
            codex=CodexOptions(
                permissions=":workspace",
                runtime_workspace_roots=(str(repo),),
                service_tier="priority",
            )
        ),
    ),
)
print(result.status)
print(result.output)
raise SystemExit(0 if result.ok and "yoke-codex-permissions-profile-smoke" in (result.output or "") else 1)
PY
```

Result: succeeded; output contained `yoke-codex-permissions-profile-smoke`.

## Provider references

- `/Users/rohan/Desktop/Projects/openai-codex/codex-rs/app-server/README.md`
  documents `thread/start` and `turn/start` experimental fields including
  `permissions`, `runtimeWorkspaceRoots`, `environments`,
  `selectedCapabilityRoots`, and `allowProviderModelFallback`.
- `/Users/rohan/Desktop/Projects/openai-codex/sdk/python/src/openai_codex/generated/v2_all.py`
  currently exposes a narrower generated Python shape than the app-server README
  for these experimental fields, so Yoke lowers directly to JSON-RPC params.
