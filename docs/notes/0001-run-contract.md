# 0001: Run contract

Yoke can pivot.

The current public names are a starting language:

- Agent
- Harness
- Goal
- Skill
- Workflow
- Session
- Turn
- Event
- Run

The design target is not to preserve these exact classes. The design target is
to keep pressure-testing them against provider reality until the SDK feels
obvious.

Boundary rule:

- Yoke owns provider-neutral agent execution.
- Providers own Claude/Codex-specific mechanics behind adapters.
- Applications own product lifecycle.

The first consumer is CodeAlmanac, but Yoke must not know about CodeAlmanac
wiki pages, jobs, indexes, or lifecycle mutation policy.
