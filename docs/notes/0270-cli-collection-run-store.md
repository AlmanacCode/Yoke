# 0270 CLI over collection and run store

Yoke has one folder-first CLI path:

```bash
yoke run agents codealmanac "Review this repo"
yoke runs
yoke show run_abc123
yoke events run_abc123
```

`yoke run` loads `agents/yoke.yaml`, selects the named agent folder, uses the
collection `default_provider` unless `--provider` is passed, runs the harness,
and records the result through `RunStore`.

The CLI intentionally does not add `init`, deployment, alternate root manifests,
or per-agent command aliases yet. The simple public contract is:

```text
agents/
  yoke.yaml
  codealmanac/
    agent.yaml
    instructions.md

.yoke/
  runs/
    <id>/
      record.json
      result.json
      events.jsonl
```

Verification:

```bash
uv run pytest tests/test_cli.py tests/test_store.py tests/test_public_api.py
uv run ruff check src/yoke/cli.py src/yoke/store.py src/yoke/__init__.py tests/test_cli.py tests/test_store.py tests/test_public_api.py
```
