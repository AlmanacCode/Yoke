# 0273 CLI install provider bundles

Yoke folder users can now write provider-native files without Python glue:

```bash
yoke install agents codealmanac --provider codex:cli
yoke install agents reviewer --provider claude:sdk --target .
```

The command keeps the same path as `run`, `explain`, and `status`:

```text
agents/yoke.yaml -> Collection -> Agent -> agent.bundle(...) -> Bundle.write(...)
```

It does not introduce a root manifest, install registry, or extra config file.
Provider artifacts remain explicit files:

- Codex: `.codex/agents/*.toml`, `.codex/config.toml`, `.agents/skills/*/SKILL.md`
- Claude: `.claude/agents/*.md`, `.claude/skills/*/SKILL.md`, `.claude/workflows/*.js`

Verification:

```bash
uv run pytest tests/test_cli.py tests/test_artifacts.py
uv run ruff check src/yoke/cli.py tests/test_cli.py
```
