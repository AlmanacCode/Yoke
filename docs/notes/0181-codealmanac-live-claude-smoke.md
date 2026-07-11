# CodeAlmanac live Claude smoke through Yoke

Date: 2026-07-04

CodeAlmanac's default Claude harness now runs through Yoke and the Claude Agent SDK.

## What the smoke tested

The smoke loaded `create_app()` from `/Users/rohan/Desktop/Projects/codealmanac`, selected `HarnessKind.CLAUDE`, and ran a `RunHarnessRequest` through the default adapter.

The default adapter was:

```text
YokeHarnessAdapter surface=claude:sdk
```

Readiness succeeded before the run:

```text
available=True
message=Claude authenticated via claude.ai
```

## Bug found before success

The first write smoke returned `status=succeeded`, but Claude said both Write and shell commands were blocked by the current `dontAsk` permission mode. Yoke's original Claude mapping treated `approval="never"` as Claude SDK `permission_mode="dontAsk"`.

That is not the right CodeAlmanac lifecycle behavior. CodeAlmanac means "do not interrupt the user for approval while running this lifecycle job," not "deny write tools." The bridge now uses surface-specific permissions:

- `codex:app` keeps `Permissions(access="write", approval="never")` so Yoke compiles the same app-server approval posture that CodeAlmanac's old direct adapter used.
- `claude:sdk` uses `Permissions(access="write", approval="auto")` so Claude SDK can use Write/Edit/Bash under `acceptEdits` rather than blocking them under `dontAsk`.

This belongs in the CodeAlmanac-Yoke bridge because it preserves the old CodeAlmanac Codex contract while acknowledging that Claude's permission words do not mean the same thing as Codex app-server's approval policy.

## Successful live smoke

The successful run used an absolute temp-file path and required Claude to read the file back after writing it. That avoids a false-positive final response and verifies the provider actually wrote into the temp workspace.

```text
cwd=/var/folders/.../codealmanac-yoke-claude-d5oxazpm
adapter=YokeHarnessAdapter surface=claude:sdk
status=succeeded
output='Readback matched — the file contains exactly `yoke claude smoke ok\n`.'
transcript=ede14445-9ac1-4e54-9b73-5758d7fb7f5d
events=16
event[4] kind=tool_use msg='Write: /var/folders/.../yoke-claude-smoke.txt' tool_kind=write status=started
event[8] kind=tool_use msg='Read: /var/folders/.../yoke-claude-smoke.txt' tool_kind=read status=started
file_exists=True
file_text='yoke claude smoke ok\n'
```

A prior relative-path prompt produced a positive final response but no file in the requested temp directory. The absolute-path plus readback version is the stronger smoke contract for Claude SDK. Future lifecycle prompts should continue to rely on CodeAlmanac's changed-file validation rather than trusting the provider's final prose alone.

## CodeAlmanac files changed

- `src/codealmanac/integrations/harnesses/yoke/adapter.py`: adds `permissions_for_surface()` and uses it when constructing the Yoke agent.
- `tests/test_yoke_harness_adapter.py`: covers the surface-specific permission policy.

## Verification

In `/Users/rohan/Desktop/Projects/codealmanac`:

```bash
uv lock --check
uv run ruff check .
uv run pytest
```

passed. The full pytest run reported 489 passing tests.

In `/Users/rohan/Desktop/Projects/Yoke`:

```bash
uv run ruff check .
```

passed.

The local CodeAlmanac virtualenv still prints stale `.dist-info` warnings for old CodeAlmanac installs missing `RECORD`; package installation, lint, and tests still pass.
