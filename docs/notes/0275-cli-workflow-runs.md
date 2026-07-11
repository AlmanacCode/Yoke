# 0275 CLI workflow runs

Yoke folder users can now run named workflows from the same collection path:

```bash
yoke workflow agents codealmanac review "Bundle loader"
```

The command uses the same path as the rest of the folder CLI:

```text
agents/yoke.yaml -> Collection -> Agent -> Harness.workflow(...) -> RunStore.record(...)
```

Flags:

- `--provider`: override `default_provider`.
- `--cwd`: working directory for provider turns.
- `--store`: Yoke run store root.
- `--native`: request provider-native workflow execution.
- `--resume`: pass a workflow replay/resume id.
- `--concurrency`: set portable workflow concurrency.
- `--channel`: set the provider channel.
- `--args`: pass structured JSON input for program/native workflows.
- `--fail-fast` / `--no-fail-fast`: set portable workflow failure behavior.

The run store already supports `WorkflowRun`; the CLI records workflow results
beside one-shot runs under `.yoke/runs/<id>/`.

Verification:

```bash
uv run pytest tests/test_cli.py tests/test_store.py tests/test_workflows.py
uv run ruff check src/yoke/cli.py tests/test_cli.py
```
