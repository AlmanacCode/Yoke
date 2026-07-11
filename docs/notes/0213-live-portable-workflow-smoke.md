# Live portable workflow smoke

Date: 2026-07-04.

This slice live-tested Yoke-owned portable workflows on the two v1 default surfaces:

- `Harness("codex", ...)` -> `codex_app_server`.
- `Harness("claude", ...)` -> `claude_python_sdk`.

Workflow used:

- `first`: prompt `Reply exactly: first-ok`.
- `second`: prompt `Read this previous output: {first}. Reply exactly: second-ok`.
- `WorkflowOptions(run=RunOptions(inherit_goal=False, max_turns=1), concurrency=1)`.

Live results:

- Codex app-server succeeded.
  - Workflow status: `succeeded`.
  - Surface: `codex_app_server`.
  - Final output: `second-ok`.
  - Step outputs: `first-ok`, then `second-ok`.
- Claude Python SDK succeeded.
  - Workflow status: `succeeded`.
  - Surface: `claude_python_sdk`.
  - Final output: `second-ok`.
  - Step outputs: `first-ok`, then `second-ok`.

Product conclusion:

- Portable Yoke workflows are usable on both v1 default surfaces.
- No code patch was needed for the live workflow smoke.
- Provider-native workflows remain separate. Claude TypeScript SDK documents the native `Workflow` tool; Claude Python SDK v1 should keep using portable Yoke workflows unless a native adapter is added.

Updated product estimate: about 63%. The default run path, goal path, and portable workflow path are live-proven. Remaining high-value work is subagents, skills, event ergonomics, README polish, and CodeAlmanac integration.
