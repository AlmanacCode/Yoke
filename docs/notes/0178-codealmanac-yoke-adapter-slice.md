# CodeAlmanac Yoke adapter slice

Date: 2026-07-04

CodeAlmanac now imports Yoke at the existing harness adapter seam.

## Shape

```text
CodeAlmanac lifecycle workflow
    -> HarnessesService.run(RunHarnessRequest)
    -> YokeHarnessAdapter.run(request)
    -> yoke.Harness("codex:app" | "claude:sdk", agent=..., cwd=request.cwd)
    -> yoke.Run
    -> HarnessRunResult
```

The lifecycle layer did not learn Yoke concepts. It still sees `HarnessKind`, `RunHarnessRequest`, `HarnessRunResult`, `HarnessEvent`, changed files, and transcript refs.

## Files changed in CodeAlmanac

- `pyproject.toml`: adds `yoke` and a local editable `tool.uv.sources` entry pointing at `../Yoke`.
- `uv.lock`: adds `yoke v0.0.0`.
- `src/codealmanac/integrations/harnesses/__init__.py`: default adapters now use Yoke.
- `src/codealmanac/integrations/harnesses/yoke/adapter.py`: owns the CodeAlmanac adapter boundary.
- `src/codealmanac/integrations/harnesses/yoke/mapper.py`: maps Yoke models into CodeAlmanac models.
- `tests/test_yoke_harness_adapter.py`: covers readiness, run wrapping, changed-file accounting, event/tool/usage/agent/transcript mapping, and failure-output fallback.
- `tests/test_claude_adapter.py` and `tests/test_codex_adapter.py`: old direct adapters remain tested, while `create_app()` default wiring now expects `YokeHarnessAdapter`.

## What stayed CodeAlmanac-owned

- Changed-file accounting uses CodeAlmanac `git_status_snapshot` and `changed_paths`.
- Job ledgers, run ledgers, lifecycle status, and mutation policy are unchanged.
- `HarnessKind.CLAUDE` and `HarnessKind.CODEX` remain CodeAlmanac's ledger identity.
- Old direct Claude/Codex adapters remain available as behavior references.

## What Yoke owns

- Provider/surface execution.
- Provider readiness through `Harness.check_sync()`.
- Provider-normalized run, event, tool, usage, agent-call, and session values.
- Exact provider surfaces: CodeAlmanac defaults are `claude:sdk` and `codex:app`.

## Verification

In `/Users/rohan/Desktop/Projects/codealmanac`:

```bash
uv lock --check
uv run ruff check .
uv run pytest
```

passed. The full pytest run reported 488 passing tests after the live-smoke follow-up.

The local virtualenv still prints stale-install warnings about old CodeAlmanac `.dist-info` directories missing `RECORD`; those warnings did not prevent install, lint, or tests.

## Distribution caveat

The current dependency is local:

```toml
[tool.uv.sources]
yoke = { path = "../Yoke", editable = true }
```

This is acceptable for local integration while Yoke is private. It is not a final public distribution contract. Before CodeAlmanac is released with Yoke, choose one:

- private Git dependency
- private package index
- publishable Yoke package name
- vendored/internal package only if Yoke is not meant to be shared

## Next pressure test

Run a real CodeAlmanac lifecycle operation through the Yoke-backed `codex:app` adapter. That checks the full stack: CodeAlmanac lifecycle prompt -> Yoke -> Codex app-server -> Yoke events -> CodeAlmanac result/changed files.

## Live Codex app-server smoke

The first live smoke proved readiness but hung past the useful quick-smoke window. Interrupting it showed the bridge had reached Yoke's Codex app-server turn loop. The mismatch was that the first bridge version did not force CodeAlmanac's previous app-server assumptions:

- CodeAlmanac lifecycle jobs should use ephemeral Codex app-server threads.
- CodeAlmanac should opt into Codex app-server `experimentalApi`, matching the previous direct adapter.
- Live provider runs need a bounded timeout that CodeAlmanac can tune.

The bridge now constructs a `CodexAppServer` adapter for `codex:app` with `ephemeral=True`, `client_name="codealmanac"`, and a timeout controlled by `CODEALMANAC_YOKE_CODEX_TURN_TIMEOUT_SECONDS` when set. It also passes Yoke `RunOptions(provider=ProviderOptions(codex=CodexOptions(experimental_api=True)))` for Codex app-server runs.

The clean live smoke used a temporary git repo and CodeAlmanac's default adapter:

```text
adapter=YokeHarnessAdapter surface=codex:app
ready=True message=Logged in using ChatGPT
status=succeeded
output='Created `yoke-smoke.txt`.'
changed=yoke-smoke.txt
events=36
event_kinds=provider_session,warning,tool_use,tool_result,tool_use,tool_result,tool_use,text_delta,text_delta,text_delta,text_delta,text_delta
transcript=019f2d5a-0479-7fa1-8280-a4af85b6098e
file_exists=True
file_text='yoke smoke ok\n'
```

That smoke exercised the full path:

```text
CodeAlmanac HarnessesService
    -> default YokeHarnessAdapter(HarnessKind.CODEX, "codex:app")
    -> Yoke Harness
    -> Codex app-server
    -> Yoke Run/Event models
    -> CodeAlmanac HarnessRunResult / changed_files / transcript
```

The next pressure test should run a real Claude SDK smoke through `claude:sdk` if local Claude auth is available.

## Live Claude SDK smoke

The matching Claude smoke is recorded in `docs/notes/0181-codealmanac-live-claude-smoke.md`.

The smoke found that CodeAlmanac cannot use one portable approval word for every provider surface. `approval="never"` preserved Codex app-server's old noninteractive policy, but Claude SDK interpreted the corresponding `dontAsk` mode as blocked Write/Bash tools. CodeAlmanac's Yoke bridge now uses `approval="never"` for `codex:app` and `approval="auto"` for `claude:sdk`.

After that change, a live Claude SDK run through CodeAlmanac's default adapter wrote and read back a temp file successfully. CodeAlmanac verification passed with 489 tests.
