# README positioning

Rewrote `README.md` on 2026-07-04 after typed Codex options landed.

The README should sell one concrete idea: Yoke is not a new agent runtime. It is a Python system-definition layer over real Claude and Codex harness surfaces.

Public examples now lead with:

- `Agent`, `Goal`, and `Harness` for the small path.
- Folder parity with `agent.yaml`, `instructions.md`, `skills/`, `subagents/`, and `workflows/`.
- Surface-specific truth tables for skills and subagents.
- Session and goal examples that distinguish compiled goals from Codex app-server native `thread/goal/*`.
- `CodexOptions`, `Collaboration`, and `CollaborationSettings` as the pleasant typed path for app-server collaboration mode.
- Raw provider dicts as an explicit escape hatch, not the default API.

The README should not promise Eve-style `tools/`, `channels/`, or `schedules/` until Yoke owns a runtime contract for them. It should keep saying that Eve is the durable workflow reference, not something Yoke has already copied.

The durable slogan is:

```text
agent definition -> provider surface -> real harness
```

This is clearer than "provider-neutral" by itself because it keeps the provider surface in the user's mental model.
