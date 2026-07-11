# CodeAlmanac integration seam

Date: 2026-07-04

Yoke should enter CodeAlmanac below the lifecycle layer, not above it.

CodeAlmanac already has the right product boundary:

```python
PageRunWorkflow / LocalEngineWorkflow
    -> HarnessesService.run(RunHarnessRequest)
    -> HarnessAdapter.run(...)
    -> HarnessRunResult
    -> job ledger / run ledger / mutation policy
```

The first integration should preserve that shape. CodeAlmanac should keep its lifecycle request/result models while a Yoke-backed adapter calls Yoke and maps the result back into CodeAlmanac's existing ledger contract.

## What CodeAlmanac should keep owning

CodeAlmanac owns lifecycle semantics:

- `init`, `ingest`, `garden`, local engine runs, and future CodeAlmanac product verbs.
- Workspace and wiki resolution.
- Prompt rendering for CodeAlmanac operations.
- Job ledger and local run ledger events.
- Mutation preflight and changed-file safety checks.
- Final success/failure interpretation for CodeAlmanac operations.
- Changed-file accounting around a run.
- Transcript/source discovery for external Claude and Codex sessions.

Those are not Yoke concerns. Yoke should not know what an Almanac page is, what an Absorb job is, or when a wiki mutation is safe.

## What Yoke should own

Yoke owns provider execution:

- Provider/surface selection.
- Claude and Codex adapter implementation.
- Provider capabilities.
- Sessions.
- Goals.
- Skills.
- Subagents.
- Workflows.
- Normalized provider events.
- Provider-specific options that do not belong in CodeAlmanac product models.

Yoke can expose richer runtime concepts than CodeAlmanac currently consumes. CodeAlmanac can start by using the one-shot run path and later opt into sessions, goals, skills, or provider surface selection when a product verb needs them.

## First landing shape

The low-risk first slice is a CodeAlmanac adapter that implements the existing `HarnessAdapter` protocol by delegating to Yoke:

```python
class YokeHarnessAdapter:
    kind: HarnessKind
    provider: Literal["claude", "codex"]
    surface: str

    def check(self) -> HarnessReadiness:
        ...

    def run(self, request: RunHarnessRequest) -> HarnessRunResult:
        before = git_status_snapshot(...)
        run = Harness(
            provider=self.provider,
            surface=self.surface,
            agent=Agent(
                instructions=codealmanac_runtime_instructions(),
                permissions=Permissions(...),
            ),
            cwd=request.cwd,
        ).run_sync(request.prompt)
        after = git_status_snapshot(...)
        return codealmanac_result_from_yoke(
            kind=self.kind,
            run=run,
            changed_files=changed_paths(request.cwd, before, after),
        )
```

This keeps `PageRunWorkflow`, `LocalEngineWorkflow`, `HarnessesService`, job recording, and mutation policies unchanged during the first integration.

## Mapping

Yoke `Run.output` maps to CodeAlmanac `HarnessRunResult.output_text`.

Yoke `Run.events` maps to CodeAlmanac `HarnessEvent` values.

Yoke `Usage` maps to CodeAlmanac `HarnessUsage`.

Yoke `Tool` maps to CodeAlmanac `HarnessToolDisplay`.

Yoke `AgentCall` maps to CodeAlmanac `HarnessAgentTrace` when Codex app-server emits provider-native collaboration-agent activity. This remains separate from `Agent.subagents`, which are client-declared Yoke/Claude-style workers.

Yoke `Run.status` maps to CodeAlmanac `HarnessRunStatus`. `RunStatus.SUCCEEDED` maps to `HarnessRunStatus.SUCCEEDED`, while `RunStatus.FAILED` and `RunStatus.CANCELLED` map to `HarnessRunStatus.FAILED` until CodeAlmanac has a distinct cancelled lifecycle state.

Yoke `Run.failure` maps to CodeAlmanac `HarnessFailure`.

Yoke `Run.provider_session_id` maps to CodeAlmanac `provider_session_id` and, when stable enough, `HarnessTranscriptRef.session_id`.

Yoke `Run.surface` and `SurfaceReport` should be retained in CodeAlmanac diagnostics or status surfaces when useful, but they should not replace CodeAlmanac's `HarnessKind` in ledgers during the first migration. `HarnessKind.CODEX` can run through `codex_app_server` first, while future configuration can choose `codex_cli` or `codex_python_sdk` without changing lifecycle schemas.

## Surface defaults

Initial CodeAlmanac defaults should be:

- Claude: `provider="claude"`, `surface="claude_python_sdk"`
- Codex: `provider="codex"`, `surface="codex_app_server"`

Codex CLI should remain available in Yoke, but CodeAlmanac lifecycle jobs have already learned to depend on app-server events, noninteractive server-request responses, usage, provider sessions, and tool displays. App server is the stronger default for CodeAlmanac.

## Avoid this migration mistake

Do not replace CodeAlmanac's lifecycle models with Yoke models in the first slice.

That would churn too many downstream surfaces at once:

- job ledger JSONL
- viewer models
- local run results
- mutation policy
- CLI output
- tests around normalized lifecycle events

The first slice should make Yoke the execution implementation while preserving CodeAlmanac's internal operation contract.

## Resolved metadata anomaly

During integration prep, `/Users/rohan/Desktop/Projects/codealmanac/pyproject.toml` was read twice and contained Yoke project metadata:

```toml
[project]
name = "yoke"
```

The CodeAlmanac and Yoke directories are distinct, and their `pyproject.toml` files are not the same file. The metadata was restored on 2026-07-04 from CodeAlmanac's local `src/codealmanac.egg-info/PKG-INFO`, `entry_points.txt`, `requires.txt`, and `uv.lock` root package entry.

Verification after restore:

```bash
uv lock --check
uv run python -c "import importlib.metadata as m; print(m.metadata('codealmanac')['Name']); print(m.metadata('codealmanac')['Version'])"
uv run ruff check .
uv run pytest tests/test_public_contract.py tests/test_cli.py
```

passed. The metadata command reported `codealmanac` and `0.1.13`; Ruff passed; the focused pytest run passed 84 tests.

## First implementation slice landed

On 2026-07-04, CodeAlmanac added a Yoke-backed adapter at the existing harness seam:

```text
HarnessesService
    -> YokeHarnessAdapter(kind, provider_surface)
    -> yoke.Harness(provider_surface, agent=..., cwd=...)
    -> yoke.Run
    -> CodeAlmanac HarnessRunResult / HarnessEvent
```

The first slice did not delete the old Claude SDK or Codex app-server adapters. They remain importable and tested as behavior references. `default_harness_adapters()` now returns:

- `YokeHarnessAdapter(HarnessKind.CLAUDE, "claude:sdk")`
- `YokeHarnessAdapter(HarnessKind.CODEX, "codex:app")`

CodeAlmanac still owns changed-file accounting. `YokeHarnessAdapter.run()` snapshots Git status before and after `harness.run_sync(request.prompt)` and maps only CodeAlmanac-side changed paths into `HarnessRunResult.changed_files`.

The mapper keeps CodeAlmanac's lifecycle result contract:

- Yoke `Readiness` -> CodeAlmanac `HarnessReadiness`
- Yoke `Run` -> CodeAlmanac `HarnessRunResult`
- Yoke `Event` -> CodeAlmanac `HarnessEvent`
- Yoke `Tool` -> CodeAlmanac `HarnessToolDisplay`
- Yoke `Usage` -> CodeAlmanac `HarnessUsage`
- Yoke `AgentCall` -> CodeAlmanac `HarnessAgentTrace`
- Yoke provider session id -> CodeAlmanac `HarnessTranscriptRef`

Package wiring uses a local `uv` source while Yoke is private:

```toml
dependencies = [
  "yoke",
]

[tool.uv.sources]
yoke = { path = "../Yoke", editable = true }
```

This is correct for the local integration slice, but it is not the final distribution story for a public CodeAlmanac package. Before release, choose the private Git dependency, internal package index, or publishable package name.

Verification:

```bash
uv lock --check
uv run ruff check .
uv run pytest
```

passed in CodeAlmanac with 488 tests after the live-smoke follow-up.

A real Codex app-server smoke also passed through CodeAlmanac's default Yoke adapter. The smoke created `yoke-smoke.txt` in a temporary git repo, returned `status=succeeded`, reported `changed=yoke-smoke.txt`, produced 36 normalized events, and carried a Codex provider session id.

## Next implementation slice

1. Run one real Claude SDK smoke through CodeAlmanac's Yoke-backed default adapter if local Claude auth is available.
2. Decide whether the old direct Claude/Codex adapters should stay as fallbacks, be hidden behind tests only, or be removed after live Yoke smokes.
3. Replace the local `tool.uv.sources` dependency with the chosen private-repo/package-index dependency before any distributable CodeAlmanac release.

This gives CodeAlmanac the new shared harness without turning the integration into a lifecycle rewrite.
