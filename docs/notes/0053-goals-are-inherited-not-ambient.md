# Goals are inherited, not ambient

Yoke now treats `Agent.goal` as a default that can be explicitly disabled per run or session.

The original provider code used `options.goal or agent.goal`. That made an agent-level goal ambient: once an agent had a goal, every run and session inherited it with no way to opt out. That is risky because goals change the shape of execution from a bounded turn toward a longer-running objective.

The public policy is now explicit:

```python
agent = Agent(
    instructions="You are careful.",
    goal=Goal("Finish the implementation safely."),
)

# inherits agent.goal
await harness.run("Implement the loader.")

# ordinary bounded run, no inherited goal
await harness.run("Explain this file.", RunOptions(inherit_goal=False))

# explicit turn goal wins even when inheritance is off
await harness.run(
    "Do this one thing.",
    RunOptions(goal=Goal("Only this turn."), inherit_goal=False),
)
```

`RunOptions.resolve_goal(agent.goal)` and `SessionOptions.resolve_goal(agent.goal)` own the policy. Provider adapters should not hand-roll goal resolution.

Semantics:

- `goal=Goal(...)` means use this explicit goal.
- `goal=None, inherit_goal=True` means inherit `Agent.goal`.
- `goal=None, inherit_goal=False` means no goal for this run/session.

This keeps Yoke's lifecycle boundary clearer. A goal can still be an agent property, but it is no longer irreversible ambient execution state.

Provider behavior remains surface-specific:

- Codex app-server uses native thread goals and disables ephemeral threads when a goal is present.
- Codex CLI and Codex Python SDK compile goals into prompt text.
- Claude Python SDK compiles goals into system prompt/task budget context.
