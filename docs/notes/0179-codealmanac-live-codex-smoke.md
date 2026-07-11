# CodeAlmanac live Codex smoke through Yoke

Date: 2026-07-04

CodeAlmanac's default Codex harness now successfully runs through Yoke and Codex app-server.

## What the smoke did

The smoke created a temporary git repo, loaded `create_app()`, selected `HarnessKind.CODEX`, and ran a `RunHarnessRequest` through the default adapter. The prompt asked Codex to create `yoke-smoke.txt` with exact contents.

The default adapter was:

```text
YokeHarnessAdapter surface=codex:app
```

Readiness succeeded:

```text
ready=True message=Logged in using ChatGPT
```

The run succeeded:

```text
status=succeeded
output='Created `yoke-smoke.txt`.'
changed=yoke-smoke.txt
events=36
event_kinds=provider_session,warning,tool_use,tool_result,tool_use,tool_result,tool_use,text_delta,text_delta,text_delta,text_delta,text_delta
transcript=019f2d5a-0479-7fa1-8280-a4af85b6098e
file_exists=True
file_text='yoke smoke ok\n'
```

## Bug found before success

The first smoke reached Codex readiness and the Yoke app-server turn loop, then exceeded the useful quick-smoke window. The bridge was not matching CodeAlmanac's previous direct Codex adapter closely enough.

The fix made CodeAlmanac's Yoke bridge explicit for Codex app-server:

- Use `CodexAppServer(ephemeral=True, client_name="codealmanac", client_title="CodeAlmanac")`.
- Pass `RunOptions(provider=ProviderOptions(codex=CodexOptions(experimental_api=True)))`.
- Read `CODEALMANAC_YOKE_CODEX_TURN_TIMEOUT_SECONDS` as a CodeAlmanac-owned live-run timeout override.

This keeps CodeAlmanac lifecycle jobs ephemeral while still delegating provider mechanics to Yoke.

## Verification

After the fix, in `/Users/rohan/Desktop/Projects/codealmanac`:

```bash
uv lock --check
uv run ruff check .
uv run pytest
```

passed. The full pytest run reported 488 passing tests.

The local virtualenv still prints stale `.dist-info` warnings for old CodeAlmanac installs missing `RECORD`; the package installs and tests still pass.

## Next pressure test

Run the matching real Claude SDK smoke through CodeAlmanac's default `YokeHarnessAdapter(HarnessKind.CLAUDE, "claude:sdk")` if local Claude auth is available.
