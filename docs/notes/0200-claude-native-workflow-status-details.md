# Claude native workflow status details

Yoke now reports more concrete provider-native workflow metadata through
`status.workflow`.

The fields are:

- `background`: the provider runtime owns a background workflow run
- `script`: the workflow primitive is script-backed rather than a Yoke step DAG
- `resumable`: the provider can resume the workflow within its session runtime
- `max_concurrent_agents`: documented concurrent-agent cap when known
- `max_agents`: documented total-agent cap when known

For the current matrix, these fields are populated for
`claude:claude_typescript_sdk`, the tracked native Claude workflow surface.

Current official Claude docs say dynamic workflows are JavaScript scripts that
orchestrate subagents at scale. The runtime executes the script separately from
the conversation, keeps intermediate results in script variables, and reports
one consolidated result. Saved workflows live under `.claude/workflows/` and use
a `meta` export plus a script body with helpers such as `agent()` and
`pipeline()`.

The same docs say workflow runs are resumable within the same Claude Code
session and have documented limits: up to 16 concurrent agents and 1,000 agents
total per run.

Design implication: Yoke's portable `Workflow(steps=...)` remains a small DAG
over provider turns. Claude dynamic workflows are a stronger native primitive.
Yoke should keep representing that distinction in both planning
(`Feature.NATIVE_WORKFLOW`) and status (`status.workflow.script/background/...`)
instead of flattening both into "workflow supported."

Verification:

```bash
PYTHONPATH=src uv run pytest tests/test_readiness.py tests/test_workflows.py tests/test_capabilities.py
uv run ruff check src/yoke/status.py tests/test_readiness.py
```

Observed:

```text
116 passed
All checks passed!
```

Sources:

- https://code.claude.com/docs/en/workflows
- https://code.claude.com/docs/en/agent-sdk/subagents
- https://code.claude.com/docs/en/agent-sdk/typescript
