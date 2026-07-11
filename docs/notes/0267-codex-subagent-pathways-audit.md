# 0267 - Codex subagent pathways audit

Date: 2026-07-04

## Question

Can Yoke support Codex subagents natively, and through which Codex surface?

## Short answer

Codex subagents are real, but they are not one single SDK primitive. Codex exposes them through several pathways:

1. Prompt-triggered subagent workflows in Codex app and CLI.
2. Custom agent configuration files under `.codex/agents/` or `~/.codex/agents/`.
3. App-server spawned-thread metadata and `collabToolCall` item events.
4. App-server `collaborationMode` settings that influence Codex's collaboration behavior.
5. Experimental batch fan-out through `spawn_agents_on_csv`.
6. SDK thread/turn APIs that can run prompts asking Codex to spawn agents, but do not expose a stable first-class `spawn_agent(...)` public method.

Yoke should treat Codex subagents as native runtime delegation plus native custom-agent files, not as the same shape as Claude `AgentDefinition`.

## Official docs evidence

The official Codex Subagents page says current Codex releases enable subagent workflows by default, Codex app and CLI surface subagent activity, and IDE visibility is coming later. It also says Codex only spawns subagents when explicitly asked, and that Codex handles spawning, follow-up routing, waiting, and closing agent threads.

The official Subagent concepts page defines three terms: subagent workflow, subagent, and agent thread. It says users should manually trigger subagents with instructions like "spawn two agents" or "delegate this work in parallel" and should specify division of work, waiting behavior, and return format.

The same official docs define built-in agents `default`, `worker`, and `explorer`. Custom agents are standalone TOML files under `~/.codex/agents/` or `.codex/agents/`. Required fields are `name`, `description`, and `developer_instructions`. Optional inherited fields include `nickname_candidates`, `model`, `model_reasoning_effort`, `sandbox_mode`, `mcp_servers`, and `skills.config`. Custom agents override the same settings as normal Codex session config.

The official SDK page says the Python SDK controls local Codex app-server over JSON-RPC and exposes thread start/run/resume-style usage. The SDK docs do not describe a public `spawn_agent` method.

## Local checkout evidence

`/Users/rohan/Desktop/Projects/openai-codex/codex-rs/app-server/README.md` exposes subagent-relevant app-server facts:

- `thread/list` supports experimental `parentThreadId` and `ancestorThreadId` filters for spawned children/descendants, and subagent threads include `parentThreadId` when known.
- `thread/read` returns `parentThreadId`, `agentNickname`, and `agentRole` for subagent threads when available.
- `item` type `collabToolCall` carries `{id, tool, status, senderThreadId, receiverThreadId?, newThreadId?, prompt?, agentStatus?}` for `spawn_agent`, `send_input`, `resume_agent`, `wait`, and `close_agent`.
- `turn/start` accepts `collaborationMode`; `settings.developer_instructions: null` means use Codex built-in instructions for that mode.
- Deprecated `multiAgentMode` is ignored; Ultra reasoning effort is the source of proactive multi-agent behavior.
- App-server has `externalAgentConfig/detect` and `externalAgentConfig/import` for migrating subagents from external-agent artifacts into `.codex/agents`.

`/Users/rohan/Desktop/Projects/openai-codex/sdk/python/docs/api-reference.md` exposes public Python SDK methods for threads, turns, streaming, steering, interrupt, models, login, and `SkillInput`. It does not expose a public typed subagent spawn method.

`/Users/rohan/Desktop/Projects/openai-codex/sdk/typescript/README.md` exposes TypeScript thread/run/stream/resume/config APIs. It does not expose a public typed subagent spawn method.

Generated protocol code includes `spawnAgent` and collab-agent item shapes under `sdk/python/src/openai_codex/generated/v2_all.py`, but that is generated protocol/event type surface, not the same thing as a curated public SDK method.

## Pathways by surface

| Surface | What exists | Yoke implication |
| --- | --- | --- |
| Codex app | Native subagent UI/activity. Custom agents load from `.codex/agents`. | Yoke folders can compile custom-agent files for app usage. |
| Codex CLI | Native subagent workflows, `/agent` inspection, custom agents, prompt-triggered delegation. | Yoke can generate `.codex/agents/*.toml` and invoke prompts that explicitly ask for named agents. |
| Codex IDE | Docs say visibility is coming soon. | Do not rely on IDE as v1 subagent proof. |
| Codex app-server | JSON-RPC exposes spawned-thread metadata, collab events, collaboration mode, child-thread filters. | Yoke should normalize events and read spawned child threads; it can set collaboration mode. |
| Codex Python SDK | Controls local app-server; public API is thread/turn-focused. | Yoke should use it for normal runs, but not claim it has first-class subagent control. |
| Codex TypeScript SDK | Thread/run/stream wrapper over CLI JSONL. | Same: can prompt for subagents, but no stable public spawn method found. |
| `codex exec` | Can run prompts that ask Codex to spawn subagents; CSV fan-out is experimental. | Useful for live smoke, not the cleanest SDK abstraction. |
| Agents SDK guide | Separate multi-agent app framework using handoffs/traces. | Adjacent inspiration, not Codex native subagent control. |

## What Yoke should build

Yoke should split Codex subagent support into two explicit concepts:

### 1. Declared custom agents

`Agent(subagents={...})` should compile to `.codex/agents/<name>.toml` when targeting Codex. This is closer to native Codex than only injecting developer instructions.

Candidate lowering:

```text
Yoke Agent.subagents["reviewer"]
  -> .codex/agents/reviewer.toml
  -> name, description, developer_instructions
  -> model, model_reasoning_effort, sandbox_mode
  -> mcp_servers and skills.config when configured
```

This should be represented as `declared="custom_agent_files"`, not as Claude-style inline agent definitions.

### 2. Runtime delegation events

Yoke should continue treating `collabToolCall` and spawned-thread metadata as provider-native runtime delegation.

Candidate event model:

```text
collabToolCall(spawn_agent)
  -> Event(kind=TOOL_USE, tool.kind=AGENT, agent.action=started)
  -> agent.thread_id, parent_thread_id, nickname, role, prompt
```

Yoke should also add session/history helpers for app-server child threads:

```python
children = await session.children()
descendants = await session.descendants()
```

These can lower to app-server `thread/list` with `parentThreadId` and `ancestorThreadId`.

## What Yoke should not claim yet

Yoke should not claim Codex has the same native declared-subagent shape as Claude `AgentDefinition`.

Yoke should not claim the public Python or TypeScript SDK exposes a stable `spawn_agent(...)` method. The stable public SDK surface is thread/turn oriented. Subagents can be triggered by prompt and observed through app-server events, but direct spawning is owned by the Codex runtime/tool loop.

Yoke should not build a separate fake orchestrator called `spawn_agent` unless it is clearly labeled as Yoke-owned orchestration. The native Codex model is: configure agents, ask Codex to delegate, observe spawned threads/events.

## Recommended Yoke API shape

Keep this as the core user-facing shape:

```python
agent = Agent(
    instructions="You are the lead maintainer.",
    subagents={
        "reviewer": Agent(
            description="Review correctness and missing tests.",
            instructions="Prioritize concrete risks with file references.",
            model="gpt-5.4",
            permissions=Permissions(access="read"),
        )
    },
)

harness = Harness("codex:app", agent=agent, cwd=repo)
await harness.run(
    "Use the reviewer subagent to review this branch, wait for it, then summarize."
)
```

For Codex, Yoke should compile `reviewer` into `.codex/agents/reviewer.toml` and include minimal main-thread guidance that the named custom agent exists. Codex still decides and performs the native spawn when prompted.

## Open questions for implementation

1. Should Yoke write custom agents into a temporary generated overlay, project `.codex/agents`, or a Yoke artifact bundle path passed via config?
2. Does app-server support selecting extra custom-agent roots the same way it supports selected capability roots for skills/plugins, or do custom agents require filesystem placement under `.codex/agents` / `~/.codex/agents`?
3. Can app-server `externalAgentConfig/import` be reused for generated Yoke agents, or is it only for migration from external products?
4. Should Yoke expose child-thread listing as part of generic `Session`, or as Codex-only `CodexSession.children()`? Generic names are nicer, but not all providers have spawned-thread lineage.
5. Should `Workflow.ctx.agent("reviewer", ...)` on Codex compile to prompt-based native delegation, or continue using Yoke's own portable run orchestration?

## Decision recommendation

For v1, implement Codex subagents as:

- Custom-agent file generation for `Agent.subagents`.
- Explicit status saying `declared=custom_agent_files` for Codex, not `native_inline`.
- Native collab event normalization stays as-is.
- Add child-thread list/read helpers on Codex app-server.
- Do not invent public direct `spawn_agent` unless Codex exposes one as stable public SDK/app-server API.

This is closer to Codex's design than either compiling everything into developer instructions or pretending Codex has Claude-style inline `AgentDefinition`.
