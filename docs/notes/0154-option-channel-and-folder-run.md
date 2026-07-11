# Option channel and workflow folder run metadata

Date: 2026-07-04

## Change

`RunOptions`, `SessionOptions`, and `WorkflowOptions` now accept `channel`.

```python
RunOptions(channel=Channel.APP_SERVER)
SessionOptions(channel="sdk")
WorkflowOptions(channel=Channel.APP_SERVER)
```

Planning precedence is:

1. Method argument, such as `harness.plan(..., channel=...)`.
2. Option object channel, such as `RunOptions(channel=...)`.
3. Constructor channel, such as `Harness(channel=...)`.

## Folder effect

Workflow step `run:` metadata can now include channel:

```yaml
---
run:
  channel: app_server
---
Review the patch.
```

This keeps folder-authored workflows close to SDK-authored workflows without making the top-level agent provider-specific.

## Boundary

`Agent` folders remain provider-neutral. A top-level `agent.yaml` does not gain `provider`, `surface`, or `channel` fields in this slice. Channel belongs to execution context: a harness, a session, a run, or a workflow execution.

## Why this matters

The user can now express the natural intent at the right level:

- Whole harness: `Harness(channel="app_server")`.
- One run: `RunOptions(channel="app_server")`.
- One workflow execution: `WorkflowOptions(channel="app_server")`.
- One workflow step: markdown frontmatter `run.channel`.

Yoke still uses exact surface capabilities to prove support.
