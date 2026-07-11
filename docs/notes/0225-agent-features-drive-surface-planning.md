# Agent features drive surface planning

2026-07-04

Yoke planning now includes features implied by the `Agent` itself, not only features implied by per-run options.

Before this slice, `Harness.plan(...)`, `Harness.run(...)`, `Harness.stream(...)`, `Harness.start(...)`, and session turn planning guarded features such as structured output, goals, provider options, and workflow options, but an agent with `skills` or declared `subagents` did not declare those as surface requirements. That made it possible for an explicit weak surface to reach adapter execution before Yoke reported that the surface could not satisfy the agent shape.

`Agent.features()` now returns:

- `Feature.GOAL` when `agent.goal` is set
- `Feature.SKILLS` when `agent.skills` is non-empty
- `Feature.DECLARED_SUBAGENTS` when `agent.subagents` is non-empty

Harness and session planning combine agent features with option features through the existing surface capability planner. The selected surface can still use native, compiled, or emulated support according to the capability matrix; the important change is that agent shape participates in the same early planning contract as run options.

Verification:

- `PYTHONPATH=src uv run pytest tests/test_capabilities.py tests/test_codex_subagents.py tests/test_folders.py tests/test_workflows.py tests/test_sessions.py tests/test_goals.py tests/test_structured_output.py`
- `PYTHONPATH=src uv run ruff check src/yoke/models.py tests/test_capabilities.py`
