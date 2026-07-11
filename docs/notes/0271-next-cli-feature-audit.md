# 0271 - Next CLI feature audit after collection run

Date: 2026-07-04

## Baseline

The new folder CLI exposes one collection path:

```bash
yoke run agents codealmanac "Review this repo"
yoke runs
yoke show run_abc123
yoke events run_abc123
```

Evidence:

- `src/yoke/cli.py:32` defines only `run` for named collection agents.
- `src/yoke/cli.py:41`, `src/yoke/cli.py:45`, and `src/yoke/cli.py:50` define only run-store inspection commands after that.
- `src/yoke/cli.py:67` loads `Collection.from_folder(args.collection)`.
- `src/yoke/cli.py:74` runs only `Harness(...).run(args.prompt)`.
- `src/yoke/cli.py:78` records the result through `RunStore`.
- `docs/notes/0270-cli-collection-run-store.md:12` says the CLI loads `agents/yoke.yaml`, selects the named agent folder, runs the harness, and records the result.

The collection contract remains one config shape:

- `docs/notes/0268-agent-collection-folder-contract.md:23` says the manifest is `agents/yoke.yaml`.
- `docs/notes/0268-agent-collection-folder-contract.md:23` also says there is no repo-root manifest, no global registry, and no alternate collection format.
- `src/yoke/models.py:656` defines `Collection`.
- `src/yoke/models.py:664` defines `Collection.from_folder(...)`.
- `src/yoke/models.py:671` defines `Collection.agent(name)`.

## SDK-accessible capabilities not reachable from the folder CLI

### Provider bundle/install artifacts

Yoke can compile an agent into provider-native files through the SDK, but the CLI cannot do it from `agents/yoke.yaml`.

Evidence:

- `src/yoke/models.py:595` defines `Agent.bundle(...)`.
- `docs/reference.md:463` shows `agent.bundle(provider="codex", surface="codex_cli")`.
- `docs/reference.md:471` shows `bundle.write(Path.cwd())`.
- `docs/reference.md:477` documents Codex outputs: `.codex/agents/*.toml`, `.codex/config.toml`, and `.agents/skills/<name>/SKILL.md`.
- `docs/reference.md:479` documents Claude outputs: `.claude/agents/*.md`, `.claude/skills/<name>/SKILL.md`, and `.claude/workflows/*.js`.
- `tests/test_artifacts.py:288` covers explicit bundle writes.
- `src/yoke/cli.py:32` through `src/yoke/cli.py:50` have no bundle, compile, or install command.

### Folder-authored workflows

Yoke can load and run workflows through the SDK. The folder format can store them, but the collection CLI cannot select or execute a named workflow.

Evidence:

- `docs/reference.md:448` lists folder workflow loading from `workflows/*.yaml`, `workflows/*.yml`, and `workflows/<name>/*.md`.
- `docs/reference.md:812` shows SDK execution with `Harness(...).workflow(...)`.
- `docs/reference.md:904` says the same workflow can live in a folder.
- `src/yoke/models.py:1437` defines `Harness.workflow(...)`.
- `src/yoke/workflows.py:1` owns Yoke-native workflow orchestration.
- `tests/test_folders.py:294`, `tests/test_folders.py:375`, and `tests/test_folders.py:400` cover markdown, script, and Python program workflows in folders.
- `tests/test_workflows.py:182` and later tests cover SDK workflow execution.
- `src/yoke/cli.py:32` through `src/yoke/cli.py:50` have no workflow command or `--workflow` option.

### Sessions, history, and session controls

Yoke exposes provider sessions through the SDK, but the CLI can only run one-shot turns and inspect Yoke run records.

Evidence:

- `src/yoke/models.py:1144` defines `Harness.start(...)`.
- `src/yoke/models.py:1199` defines `Harness.session(...)`.
- `src/yoke/models.py:1269` defines `Harness.sessions(...)`.
- `src/yoke/models.py:1310` defines `Harness.read_session(...)`.
- `src/yoke/models.py:1882` defines `Session.fork(...)`.
- `docs/reference.md:592` shows multi-turn session usage.
- `docs/reference.md:654` documents stored session history.
- `docs/reference.md:682` documents session rename and tag calls.
- `src/yoke/cli.py:32` through `src/yoke/cli.py:50` have no session, resume, history, fork, rename, tag, or compact command.

### Planning, status, model, and login controls

Yoke exposes non-running diagnostics and provider controls through the SDK, but the CLI has no equivalent commands.

Evidence:

- `src/yoke/models.py:1006` defines `Harness.plan(...)`.
- `src/yoke/models.py:1221` defines `Harness.status(...)`.
- `src/yoke/models.py:1233` defines `Harness.statuses(...)`.
- `src/yoke/models.py:1409` defines `Harness.login(...)`.
- `src/yoke/models.py:1479` defines `Harness.models(...)`.
- `docs/reference.md:190` documents `plan(...)`.
- `docs/reference.md:265` documents `status()`.
- `docs/reference.md:289` documents `login(...)`.
- `docs/reference.md:1122` documents `models()`.
- `src/yoke/cli.py:32` through `src/yoke/cli.py:50` have no plan, status, models, or login command.

### Streaming

Yoke exposes streaming in the SDK, but `yoke run` waits for a final result and prints the run id plus final output.

Evidence:

- `src/yoke/models.py:1077` defines `Harness.stream(...)`.
- `src/yoke/models.py:1722` defines `Session.stream(...)`.
- `docs/reference.md:1410` documents session streaming.
- `src/yoke/cli.py:80` prints the stored run id.
- `src/yoke/cli.py:81` through `src/yoke/cli.py:82` print only final output when present.

## Recommendation

Build `yoke install agents <agent> --provider <provider> [--surface <surface>] [--target <path>] [--overwrite]` next.

Why this is the highest-value next gap:

1. It completes the folder-first promise for non-Python users. A user who has `agents/yoke.yaml` and an agent folder should not need a Python snippet just to produce `.codex/` or `.claude/` provider files.
2. It uses the existing collection config. The command can load `Collection.from_folder(args.collection)`, select `collection.agent(args.agent)`, call `agent.bundle(...)`, and then call `bundle.write(...)`. No root `yoke.yaml`, global registry, or per-agent manifest is needed.
3. It was already identified as the next pressure after collection/run-store work. `docs/notes/0268-agent-collection-folder-contract.md:85` names the collection CLI, `docs/notes/0268-agent-collection-folder-contract.md:86` names the run store, and `docs/notes/0268-agent-collection-folder-contract.md:87` names explicit provider install.
4. It is safer and smaller than session CLI. Session resume, fork, rename, tag, compact, and history commands need more UX decisions. Install is a thin adapter over an existing SDK capability and existing provider artifact tests.
5. It is more immediately user-visible than workflow CLI. Workflows are powerful, but provider install lets a folder-authored agent show up in the tools users already open every day.

Do not add a second config approach. The command should keep the same shape as `yoke run`:

```bash
yoke install agents codealmanac --provider codex --surface codex_cli
yoke install agents reviewer --provider claude
```

The implementation should stay thin:

```text
parse args -> Collection.from_folder(collection) -> collection.agent(agent) -> agent.bundle(provider, surface) -> bundle.write(target)
```
