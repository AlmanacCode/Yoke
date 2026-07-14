# Yoke reference

This is the detailed Yoke API reference. Start with `README.md` or `docs/quickstart.md` when you want the short path.

## Embedding Yoke in an app

Yoke is meant to sit behind your app's own service boundary. Your product code
should not need to import Claude or Codex SDK objects, and it usually should not
need to import Yoke provider adapters either.

```python
from pydantic import BaseModel

from yoke import Agent, Goal, Harness, RunOptions, Tools


class HarnessTask(BaseModel):
    prompt: str
    model: str | None = None
    effort: str | None = None
    goal: str | None = None
    output_schema: dict | None = None


def run_task(task: HarnessTask, repo):
    agent = Agent(
        instructions="Run this product task carefully.",
        tools=Tools(read=True, write=True, shell=True),
    )
    options = RunOptions(
        model=task.model,
        effort=task.effort,
        goal=Goal(task.goal) if task.goal else None,
        output_schema=task.output_schema,
    )
    return Harness("codex:app", agent=agent, cwd=repo).run_sync(task.prompt, options)
```

That is the intended layering:

- your app owns product verbs, jobs, retries, safety checks, and persistence
- Yoke owns provider-neutral agent/session/workflow values
- provider adapters own Claude/Codex protocol details

For example, CodeAlmanac keeps `init`, `ingest`, `garden`, job logging,
changed-file validation, and reindexing in its own lifecycle workflows. It uses
Yoke only at the harness adapter seam.

## The small path

The folder CLI is the same path as the SDK:

```bash
yoke run agents codealmanac "Review this repo"
yoke workflow agents codealmanac review "Bundle loader"
yoke explain agents codealmanac
yoke status agents codealmanac
yoke install agents codealmanac --provider codex:cli
yoke runs
yoke show run_abc123
yoke events run_abc123
```

`yoke run` loads `agents/yoke.yaml`, runs the named agent through the selected
provider, and records `record.json`, `result.json`, and `events.jsonl` under
`.yoke/runs/<id>/`.
`yoke workflow` runs a named workflow from the selected agent folder through
`Harness.workflow(...)` and stores the resulting `WorkflowRun` in the same
`.yoke/runs/<id>/` store.
It accepts SDK-shaped workflow flags: `--native`, `--resume`, `--concurrency`,
`--channel`, `--args`, and `--fail-fast` / `--no-fail-fast`.

`yoke explain` does not call the provider. It prints the local surface plan,
model source, feature list, and lowering rows. `yoke status` calls the selected
adapter readiness check, then prints readiness plus semantic reports for goals,
workflows, subagents, skills, MCP, hooks, permissions, history, control, and
exposure.
`yoke install` calls the same provider bundle writer as `agent.bundle(...)` and
writes native files under the current directory or `--target`.

```python
from pathlib import Path

from yoke import Agent, Harness, Permissions, Tools

agent = Agent(
    instructions="Explain the repository in three bullets.",
    tools=Tools(read=True),
    permissions=Permissions(),
)

result = await Harness(
    provider="codex",
    surface="codex_cli",
    agent=agent,
    cwd=Path.cwd(),
).run("What does this project do?")

if result.status == "succeeded":
    print(result.output)
else:
    print(result.failure.message if result.failure else result.output)
```

Simple scripts can opt into exceptions:

```python
result.raise_for_status()
```

When you request structured output, read parsed values from `result.data`:

```python
from pydantic import BaseModel
from yoke import RunOptions


class Summary(BaseModel):
    summary: str
    changed: bool


result = await harness.run(
    "Return a summary object.",
    RunOptions(output_schema=Summary),
)

print(result.data.summary)
```

If the provider returns malformed structured output, Yoke returns a failed run
with `result.failure.code` set to `invalid_structured_json` or
`invalid_structured_output`.

Every async convenience method has a sync twin:

```python
result = harness.run_sync("What does this project do?")
```

Provider and surface values are enum-native but string-friendly:

```python
from yoke import Provider, Surface

Harness(provider=Provider.CODEX, surface=Surface.CODEX_APP_SERVER, ...)
```

Surfaces can be exact, automatic, or friendly aliases:

```python
Harness("codex:app", ...)
Harness("claude:sdk", ...)
Harness(provider="codex", surface="codex_app_server", ...)
Harness(provider="codex", surface="auto", ...)
Harness(provider="codex", surface="app", ...)
Harness(provider="codex", surface="sdk", ...)
Harness(provider="claude", surface="sdk", ...)
```

Aliases are provider-aware input sugar. `codex:app` means
`codex_app_server`; `codex:sdk` means `codex_python_sdk`; `claude:sdk` means
`claude_python_sdk`. Yoke still reports exact surface names in plans, runs,
sessions, readiness, and events.

V1 defaults are product-oriented: `Harness("codex", ...)` selects
`codex_app_server`, and `Harness("claude", ...)` selects
`claude_python_sdk`. Use `codex:cli`, `codex:sdk`, `claude:cli`, or
`claude:typescript` only when you explicitly want that surface.

If you know the features you need but not the right surface, require them:

```python
from yoke import Channel, Feature, RunOptions, SessionOptions

harness = Harness(
    provider="codex",
    channel=Channel.APP_SERVER,
    agent=agent,
    cwd=Path.cwd(),
).require(Feature.STREAMING, Feature.READABLE_GOAL)

print(harness.profile().surface)  # codex_app_server
```

If you set a surface explicitly, `require(...)` validates it instead of
silently changing it.

Embedders can bind environment variables to one harness without changing
process-global `os.environ`:

```python
harness = Harness(
    "codex:app",
    agent=agent,
    cwd=repo,
    environment={"ALMANAC_CLI": "/opt/almanac/bin/almanac"},
)
```

Yoke merges the controlled adapter environment first, then
`Harness.environment`, then typed credentials. Harness values therefore win
over adapter defaults, while an explicit API key or OAuth credential remains
authoritative. Environment values are excluded from model serialization and
repr because they may contain secrets. The built-in Claude SDK and Codex
app-server surfaces pass the merged mapping to their child processes without
mutating global state.

`require(...)` chooses runnable Python-backed Yoke surfaces by default. Use
`runnable=False` when you are planning against a conceptual provider surface
that this package cannot run yet:

```python
profile = select_profile(
    "claude",
    requires=[Feature.WORKFLOW],
)

print(profile.surface)   # claude_typescript_sdk
print(profile.runnable)  # False, until Yoke has a TypeScript adapter
```

For actual Python execution, `Harness.require(...)` will choose the best
runnable surface instead. Today that means Claude workflows run through Yoke's
portable workflow runner on `claude_python_sdk`.

Use `plan(...)` when you want diagnostics without changing the harness:

```python
plan = harness.plan(RunOptions(output_schema=Summary), channel=Channel.APP_SERVER)
print(plan.ok, plan.surface, plan.missing)
```

Plans also carry feature reports for the selected surface. Use these when you
want to explain how this exact run shape will lower requested features before
execution:

```python
for row in plan.reports:
    print(row.feature, row.support, row.lowering)

print(plan.report(Feature.STRUCTURED_OUTPUT))
```

Broader APIs such as `harness.report()`, `report_for(...)`, and
`matrix_for(...)` remain the right tools for surface-wide capability audits.

Execution options can also carry the channel when the constraint belongs to a
specific run or session:

```python
result = await harness.run(
    "Implement the plan.",
    RunOptions(channel=Channel.APP_SERVER),
)
session = await harness.start(SessionOptions(channel=Channel.SDK))
```

When selection is surprising, inspect the ranked fits:

```python
for fit in harness.fits(Feature.WORKFLOW, channel=Channel.SDK):
    print(fit.profile.surface, fit.profile.runnable, fit.missing)
```

For status pages, CLIs, or integration checks, use JSON-friendly reports:

```python
report = harness.require(Feature.MODELS).report()
print(report.model_dump())
```

For a provider-level matrix, ask once:

```python
from yoke import matrix_for

matrix = matrix_for("codex", channel=Channel.APP_SERVER, runnable=True)
print(matrix.model_dump())
```

Standalone checks can use `report_for("codex", "app")`. Reports accept aliases
on input and return exact surface names.

Methods with obvious requirements apply this automatically: `start()` requires
sessions, `workflow()` requires workflows, and `models()` requires model
listing. Session methods do the same: `stream()` requires streaming, and goal
methods require readable or mutable goal support. Passing `output_schema` in
`RunOptions` requires structured output. Option objects expose this as public
planning API through `.features(...)`. Plain `run()` does not auto-select a
richer surface; it keeps the provider default unless you call `require(...)`.

Check local readiness without starting an agent run:

```python
readiness = await harness.check()
if not readiness.available:
    print(readiness.message)
    print(readiness.fix)
```

Use `status()` when an embedding app wants readiness and declared capability
metadata together:

```python
status = await harness.status()
print(status.available)
print(status.provider, status.surface, status.channel)
print(status.supports(Feature.READABLE_GOAL))
```

Use `statuses()` when you want the provider exposure map with live readiness:

```python
for status in await harness.statuses(channel=Channel.APP_SERVER):
    print(status.surface, status.available, status.supports(Feature.READABLE_GOAL))
```

`status()` checks the selected surface. `statuses()` checks every matching known
surface for the harness provider, optionally filtered by `Channel`.

Capability reports include surface evidence URLs. Use them when you need to
audit why Yoke believes `codex_app_server` supports a feature that `codex_cli`
does not.

Some surfaces can also start provider-native login flows:

```python
login = await Harness(
    provider="codex",
    agent=agent,
    cwd=Path.cwd(),
).login("device_code")

print(login.verification_url, login.user_code)
completed = await login.wait()
```

For Codex Python SDK, Yoke supports `chatgpt`, `device_code`, and `api_key`.
Codex CLI/app-server and Claude currently use their normal external auth setup:
`codex login`, `claude`/Claude Code auth, or provider environment variables.
`Feature.LOGIN` means Yoke can initiate the login workflow, not merely that the
surface can be authenticated externally.

Ask `status.control` when the distinction matters:

```python
print(status.control.mode)
print(status.control.login, status.control.models)
print(status.control.interrupt, status.control.fork)
print(status.control.request_events, status.control.request_callbacks)
```

`programmatic` means Yoke can initiate login for the surface. `external_auth`
means the surface may still expose runtime controls, such as model listing,
interrupt, fork, request events, request callbacks, or an experimental
app-server API, but auth happens through the provider's normal setup. Yoke
reports those controls separately because Codex
app-server, Codex SDKs, Codex CLI, and Claude SDKs do not expose the same shape.

Ask `status.exposure` when you need to know where configuration naturally
lives:

```python
print(status.exposure.mode)             # cli, sdk, or protocol
print(status.exposure.experimental)     # whether experimental fields exist
print(status.exposure.runtime_options)  # whether live SDK values are expected
```

Codex app-server reports `protocol` because it is a JSON-RPC integration
surface. SDK surfaces report `sdk` because they can carry live object graphs.
CLI surfaces report `cli` because configuration flows through process flags,
provider config files, and compiled artifacts.

## Folder agents

Yoke can save and load the same system as a readable folder:

```python
agent.save("agent")
agent = Agent.from_folder("agent")
```

```text
agent/
  agent.yaml
  instructions.md
  skills/
    source-grounding/SKILL.md
  subagents/
    reviewer/
      agent.yaml
      instructions.md
  workflows/
    ship/
      draft.md
      review.md
```

```python
from yoke import Agent

agent = Agent.from_folder("agent")
```

Multiple agents use one collection folder. The manifest always lives at
`agents/yoke.yaml`, and every path is relative to that folder:

```text
agents/
  yoke.yaml
  codealmanac/
    agent.yaml
    instructions.md
  inert/
    agent.yaml
    instructions.md
  reviewer/
    agent.yaml
    instructions.md
```

```yaml
default_provider: codex:app
agents:
  codealmanac: codealmanac
  inert: inert
  reviewer: reviewer
```

```python
from yoke import Collection, Harness

collection = Collection.from_folder("agents")
agent = collection.agent("codealmanac")
harness = Harness(collection.default_provider, agent=agent, cwd=repo)
```

There is no root manifest and no global agent registry. The collection folder is
the portable unit.

## Run storage

Yoke run storage is explicit. Callers choose when to write a local snapshot:

```python
from yoke import RunStore

result = await harness.run("Review this repository.")
record = RunStore.at(".yoke").record(
    result,
    agent="codealmanac",
    collection="agents",
)
```

The store writes one directory per run:

```text
.yoke/
  runs/
    run_abc123/
      record.json
      result.json
      events.jsonl
```

`record.json` is the inspection index. It records the Yoke run id, provider,
surface, status, cwd, collection path, agent name, provider session id, event
count, and paths to the stored result and events. `result.json` is the
provider-neutral result snapshot without volatile provider objects.
`events.jsonl` contains normalized Yoke events. If a provider stores native
transcripts, those still belong to the provider under locations such as
`~/.codex` or `~/.claude`; Yoke stores the provider session handle needed to
find that native history.

The loader understands:

- `agent.yaml`
- `instructions.md`
- sorted markdown files in `instructions/`
- `skills/*.md`
- `skills/<name>/SKILL.md`
- `subagents/<name>/`
- `workflows/*.yaml` and `workflows/*.yml`
- `workflows/<name>/*.md` with path-derived step names

Simple goals can be written as `goal: Finish the implementation safely.` in
`agent.yaml`. Goals with budgets or status use the same mapping shape as the
SDK: `goal: { objective: Finish safely., token_budget: 200000 }`.

Folder support is inspired by Eve, but Yoke does not copy Eve's full runtime
surface yet. `tools/`, `channels/`, and `schedules/` should appear only when
Yoke has a real runtime contract for them.

The folder is Yoke source. Provider-native files are a separate explicit compile
step:

```python
bundle = agent.bundle(provider="codex", surface="codex_cli")
for artifact in bundle.artifacts:
    print(artifact.path, artifact.lowering)
```

Writing is explicit:

```python
bundle.write(Path.cwd())
```

Current compile targets:

| Provider | Generated files |
| --- | --- |
| Codex | `.codex/agents/*.toml`, `.codex/config.toml`, `.agents/skills/<name>/SKILL.md` |
| Claude | `.claude/agents/*.md`, `.claude/skills/<name>/SKILL.md`, `.claude/workflows/*.js` |

Each artifact carries `kind`, typed `component`, optional `feature`,
`description`, and `lowering`, so callers can explain what provider-native file
was produced from which Yoke concept. `component` is the concrete file role
such as `agent`, `skill`, `workflow`, or `config`; `feature` points back to the
Yoke capability such as `skills`, `filesystem_agent`, or `native_workflow`.

`Agent.save(...)` copies path-backed skills into the Yoke folder so the saved
agent is self-contained. `agent.bundle(...).write(...)` only writes compiled
provider artifacts; path-backed skills remain existing provider resources unless
the selected adapter supports loading them natively.

## Skills

```python
from pathlib import Path

from yoke import Agent, Skill

agent = Agent(
    instructions="Use source evidence before editing.",
    skills=(Skill.from_path(Path("agent/skills/source-grounding")),),
)
```

Yoke preserves native skill behavior when the provider surface supports it.

| Surface | Packaged folder skills | Inline text skills |
| --- | --- | --- |
| Claude Python SDK | local Claude plugin root | derived local plugin skill |
| Codex app-server | `skills/extraRoots/set` | derived native skill root |
| Codex CLI | prompt-compiled | prompt-compiled |

Native skills can bring supporting files and provider UI affordances. Compiled
skills are portable prompt context.
Folder skills are live-smoked on the v1 defaults: Codex app-server and Claude
Python SDK.

Ask `status.skills` when you need the exact mode:

```python
status = await harness.status()
print(status.skills.mode)
print(status.skills.skills, status.skills.plugins, status.skills.hooks)
```

`provider_native` means the surface can discover or load skill bundles.
`compiled` means Yoke flattens the skill into instructions for that surface.
`plugins` reports whether the surface can load provider plugin bundles. A skill
is reusable capability content; a plugin is provider packaging that may contain
skills, agents, hooks, MCP servers, commands, or app integrations.

## Subagents

```python
from yoke import Agent, Effort, Tools

agent = Agent(
    instructions="You are the root maintainer.",
    subagents={
        "reviewer": Agent(
            description="Find correctness and architecture risks.",
            instructions="Review concretely. Prefer file and line evidence.",
            effort=Effort.HIGH,
            tools=Tools(read=True, shell=True),
        )
    },
)
```

Provider behavior is intentionally different:

| Surface | Yoke-declared subagents |
| --- | --- |
| Claude Python SDK | mapped to Claude `AgentDefinition` |
| Codex CLI | compiled into prompt instructions |
| Codex app-server | derived custom-agent TOML selected by `agent_type` |

Codex app-server also has native collaboration-agent tool activity such as
`spawnAgent`, `sendInput`, `wait`, and `closeAgent`. Yoke exposes that as
`Feature.COLLAB_AGENT_TOOLS` and normalizes `collabToolCall` and legacy
`collabAgentToolCall` items as
`ToolKind.AGENT`. These events also carry `event.agent` with typed thread,
prompt, model, and reasoning metadata when Codex provides it. That is not the
same as a client-declared subagent map.

Ask `status.subagents` when you need the exact mode:

```python
status = await harness.status()
print(status.subagents.mode)
print(status.subagents.declared, status.subagents.collab)
print(status.subagents.definition_sources)
print(status.subagents.agent_tool, status.subagents.events)
```

`declared` means Yoke subagents map to provider definitions. `compiled` means
they become instructions or artifacts. `provider_native` means the provider
surface can expose live spawned-agent activity, which is separate from the
Yoke-declared subagent map.

### Runtime deployments

For Claude SDK and Codex app-server, Yoke derives provider-native runtime files
under an isolated temporary directory outside `Harness.cwd`. Configure its
parent with `Harness(runtime_root=Path(...))`; Yoke removes each deployment on
close or error. Root and child skills retain separate ownership.

Codex roles use `spawn_agent(agent_type=..., fork_turns="none")` (or a partial
turn count), because a full fork cannot change role/model metadata. If the
selected model/backend rejects the named-agent schema, the run fails rather
than falling back to a generic child. Use `agent.bundle(...).write(...)` only
when you intentionally want durable project files; `runtime_root` is a cache,
not another authored configuration source. Existing Codex skill configuration
is preserved; for a path managed by the active Yoke deployment, Yoke's runtime
enablement flag takes precedence so parent and child skill ownership remains
enforced.

## Sessions

One-shot runs are the common case:

```python
result = await harness.run("Diagnose the failing test.")
```

Sessions are for multi-turn work:

```python
async with harness.session() as session:
    await session.run("Remember the word yoke.")
    result = await session.run("What word did I ask you to remember?")
```

Session turns accept `RunOptions`, so structured output, permissions, effort,
goal inheritance, and provider-specific options can be set per turn when the
surface supports them:

```python
result = await session.run(
    "Return a summary object.",
    RunOptions(output_schema=Summary, inherit_goal=False),
)
```

Codex app-server and Claude sessions are live provider sessions. Codex CLI
sessions are persisted thread ids resumed through `codex exec resume`.

```python
from yoke import SessionOptions

session = await harness.start(SessionOptions(resume=thread_id))
```

Live sessions can request interruption when the selected surface supports it:

```python
await session.interrupt()
```

Today that is native on Claude Python SDK live sessions and Codex app-server
turns. Codex CLI resume sessions do not have a live turn handle, so Yoke rejects
`interrupt()` there during capability planning.

Sessions can also branch when the surface supports provider-native forking:

```python
from yoke import ForkOptions

fork = await session.fork(ForkOptions(ephemeral=True))
result = await fork.run("Try the alternate fix.")
```

Fork support is surface-specific:

| Surface | Fork support |
| --- | --- |
| Claude Python SDK | native full-session fork via `resume=<provider_session_id>` and `fork_session=True`; requires a learned `provider_session_id` |
| Codex Python SDK | native `thread_fork` on the same live SDK client |
| Codex app-server | native `thread/fork`; supports app-server fork options |
| Codex CLI | unsupported |

Claude's live fork surface does not support `last_turn_id` or `exclude_turns`.
Those options belong to other fork forms such as Codex app-server or Claude's
offline transcript/store helpers.

Yoke sessions have two identities. `Session.id` is the Yoke live-session key;
`Session.provider_session_id` is the provider-persisted conversation id when a
provider exposes one. Claude fork uses `provider_session_id`, not the local
Yoke key.

## Stored session history

Some provider surfaces expose stored conversations without resuming them:

```python
page = await harness.sessions(limit=10)
history = await harness.read_session(page.sessions[0].id)
```

Claude Python SDK maps this to `list_sessions()`, `get_session_info()`, and
`get_session_messages()`. Codex app-server maps it to `thread/list` and
`thread/read`. These calls are read-only Yoke history APIs; they do not start a
turn, resume a live session, archive a thread, or mutate provider state.

Session control is separate from history reads. When a surface supports provider
compaction, use the explicit session method:

```python
await session.compact()
```

Codex app-server maps this to `thread/compact/start`. Claude file checkpointing
can rewind filesystem state, but it is not the same as conversation compaction,
so Yoke does not expose it as `Session.compact()`.

Non-destructive session metadata uses the same surface-aware rule:

```python
await harness.rename_session(session_id, "Bug bash")
await harness.tag_session(session_id, "needs-review")
```

Claude Python SDK supports both rename and tag. Codex app-server supports rename
through `thread/name/set`; it does not expose a portable tag operation.

## Goals

Goals are explicit Yoke values:

```python
from yoke import Goal

goal = Goal("Finish the requested implementation safely.", token_budget=200_000)
```

They can live on the agent:

```python
agent = Agent(instructions="You are careful.", goal=goal)
```

They can also be attached to a run or session:

```python
from yoke import RunOptions, SessionOptions

await harness.run("Implement this.", RunOptions(goal=goal))
session = await harness.start(SessionOptions(goal=goal))
```

`Agent.goal` is inherited by default, but it is not ambient forever. Disable it
for one bounded run or session when needed:

```python
await harness.run("Explain this file.", RunOptions(inherit_goal=False))
session = await harness.start(SessionOptions(inherit_goal=False))
```

Codex app-server supports native readable and mutable thread goals:

```python
session = await session.set_goal(goal)
current = await session.get_goal()
session = await session.clear_goal()
```

Goal behavior depends on the exact provider surface:

```python
status = await harness.status()
print(status.goal.mode)
```

`native_thread` means Yoke can read or mutate provider goal state through the
session. `provider_loop` means the provider documents a native keep-working
loop, but Yoke is not claiming readable or mutable goal state for that surface.
`compiled_context` means Yoke passes the goal into the run or session prompt.
`status.goal.loop` says whether the selected surface exposes provider-native
continuation. `auto_continues` is true only for surfaces that document a native
goal loop.

Yoke keeps bounded goals and keep-working goal loops separate:

```python
from yoke import Goal, GoalLoopOptions

plan = harness.plan(GoalLoopOptions(goal=Goal("Finish the migration safely.")))
print(plan.surface)
```

`GoalLoopOptions` asks the planner for `Feature.GOAL_LOOP`. A normal
`RunOptions(goal=...)` or `SessionOptions(goal=...)` only asks for
`Feature.GOAL`, so it stays a bounded run/session unless the caller explicitly
chooses a native loop surface.

To start a provider-owned loop from the SDK, call `goal_loop()`:

```python
run = await harness.goal_loop(
    GoalLoopOptions(goal=Goal("Finish the migration safely."))
)

print(run.session.id)
print(run.auto_continues)
```

`GoalRun` is a handle, not a job record. It tells you which provider surface
accepted the loop and returns the provider session so your app can inspect,
interrupt, fork, or close it when the surface supports those controls. Yoke does
not poll, retry, enqueue, or decide completion for the app.

Claude SDK receives goals as compiled prompt/task-budget context. Claude CLI
documents `/goal` as an evaluator loop. Codex CLI documents `/goal` for
interactive goal runs. Codex app-server uses `thread/goal/*` for persisted goal
state surfaced by `/goal`.

## Workflows

`Workflow` is Yoke's Claude-style workflow runtime: a small agent program with
`agent`, `parallel`, `pipeline`, `phase`, args, traces, and one consolidated
result. It works across runnable Yoke harness surfaces because Yoke owns the
orchestration and each helper lowers to provider turns.

```python
from yoke import Agent, WorkflowMemory, Harness, Workflow, WorkflowOptions

agent = Agent(
    instructions="Coordinate carefully.",
    subagents={
        "researcher": Agent(instructions="Find source evidence."),
        "reviewer": Agent(instructions="Review with concrete risks."),
    },
)

async def audit(ctx):
    async with ctx.phase("research"):
        files = await ctx.agent("researcher", f"Find files for {ctx.args['scope']}")

    reviews = await ctx.pipeline(
        ["api", "cli"],
        lambda item: ctx.agent("reviewer", f"Review {item} using {files.output}"),
        phase="review",
    )

    return ctx.summarize(reviews)

workflow = Workflow("audit-routes").run(audit)
memory = WorkflowMemory()
result = await Harness("codex", agent=agent, cwd=repo).workflow(
    workflow,
    {"scope": "routes"},
    WorkflowOptions(memory=memory, resume="audit-run-1"),
)
print(result.output)
print(result.run_id)
print(result.traces)
```

The same workflow can live on disk:

```text
agent/workflows/audit-routes/
  workflow.yaml
  workflow.py
```

```python
# agent/workflows/audit-routes/workflow.py
async def main(ctx):
    files = await ctx.agent("researcher", f"Find files for {ctx.args['scope']}")
    reviews = await ctx.pipeline(
        ["api", "cli"],
        lambda item: ctx.agent("reviewer", f"Review {item} using {files.output}"),
    )
    return ctx.summarize(reviews)
```

`Agent.from_folder(...)` loads this as `Workflow.from_program(...)`. Path identity
is primary: the directory name is the workflow name unless `workflow.yaml`
explicitly overrides it.

This is the portable functionality inspired by Claude dynamic workflows. It is
not a durable background workflow runtime yet, and it does not pretend Codex has
Claude's native `Workflow` tool. `WorkflowMemory` and `WorkflowStore` give replay for
unchanged `ctx.agent(...)` calls when `WorkflowOptions(resume=...)` uses the
same run id.

If you are embedding Yoke inside a product that already has lifecycle
workflows, keep the distinction sharp. A product workflow should decide what
business operation is happening and when safety checks run. A Yoke workflow is
the agent-turn orchestration used inside a harness task. Do not pass arbitrary
Yoke workflows through your product boundary unless that boundary explicitly
models multi-turn agent orchestration.

`Workflow(steps=...)` is the older Yoke-owned dependency DAG over provider
turns:

```python
from yoke import Step, Workflow

workflow = Workflow(
    name="review",
    steps=(
        Step(name="draft", agent="main", prompt="Draft: {input}"),
        Step(
            name="review",
            agent="reviewer",
            depends_on=("draft",),
            prompt="Review this draft:\n\n{draft}",
        ),
    ),
)

result = await harness.workflow(workflow, "write release notes")
```

This portable step workflow path is live-smoked on the v1 defaults:
`codex_app_server` and `claude_python_sdk`. Provider-native script workflows
remain an explicit adapter capability.

Workflow options can set defaults for every step, while a single step can
override them with `run=`:

```python
workflow = Workflow(
    name="ship",
    steps=(
        Step(name="plan", prompt="Plan: {input}"),
        Step(
            name="verify",
            prompt="Verify this plan:\n\n{plan}",
            run=RunOptions(
                goal=Goal("Verify safely without editing files."),
                permissions=Permissions(access="read"),
            ),
        ),
    ),
)
```

The same workflow can live in a folder. This mirrors Eve's path-derived style:
the workflow name comes from the directory, and each step name comes from the
markdown filename.

```text
agent/workflows/review/
  workflow.yaml
  draft.md
  review.md
```

Step files can carry runtime overrides in frontmatter:

```markdown
---
agent: reviewer
depends_on: draft
run:
  goal:
    objective: Verify safely without editing files.
  permissions:
    access: read
---
Review this draft:

{draft}
```

`Agent.save(...)` writes workflows in this markdown-folder shape by default.
The loader still accepts `workflows/*.yaml` and `workflows/*.yml` for compact
machine-authored definitions.

`workflow.yaml` is optional metadata:

```yaml
description: Draft then review.
```

Each step file body is the prompt. Frontmatter is optional:

```markdown
---
agent: reviewer
depends_on: draft
output_schema:
  type: object
---
Review this draft:

{draft}
```

Step output schemas are passed through to the provider run when supplied. A
workflow-level run schema acts as the fallback.

Folder saves fail if a step contains runtime-only SDK values, such as a Python
callback. If you intentionally want a lossy folder copy that omits those live
values, call `agent.save(path, allow_runtime_only=True)`.

Workflows are small dependency DAGs. `depends_on` and prompt placeholders such
as `{draft}` create dependencies. Ready steps run concurrently up to
`WorkflowOptions.concurrency`.

```python
from yoke import Goal, RunOptions, WorkflowOptions

result = await harness.workflow(
    workflow,
    "write release notes",
    WorkflowOptions(
        run=RunOptions(goal=Goal("Finish the workflow safely.")),
        concurrency=2,
        fail_fast=True,
    ),
)

print(result.mode)      # yoke_portable
print(result.provider)  # claude
print(result.surface)   # claude_code_cli, codex_app_server, ...
```

`WorkflowOptions.run` carries shared run options to every step: goals,
permissions, effort, output schema, and provider-specific options. Step schemas
still win over workflow-level schemas.

Workflow behavior also depends on the provider surface:

```python
status = await harness.status()
print(status.workflow.mode)
print(status.workflow.native)
```

`yoke_portable` means Yoke runs the workflow as steps over provider turns.
`provider_native` means the surface documents its own workflow primitive, such
as Claude TypeScript SDK's `Workflow` tool for dynamic background workflows.
Script workflows require provider-native workflow support; step workflows are
portable.

If a step returns `Run(status="failed")`, the workflow records the failed step.
With `fail_fast=True`, scheduling stops at that step. With `fail_fast=False`,
ready downstream work can continue, but `WorkflowRun.status` remains `failed`.

```python
if not result.ok and result.failed_step:
    print(result.failed_step.step, result.failure.message)
```

Each `StepResult` also carries execution trace metadata:

```python
for step in result.steps:
    print(step.step, step.agent, step.surface)
    print(step.depends_on)
    print(step.prompt)
```

This makes portable workflows inspectable without adding a separate workflow log
format. Provider-native workflow adapters can still return their own
`WorkflowRun(mode="provider_native")` shape when the provider owns orchestration.

This is not a durable workflow runtime yet. Eve remains the reference point for
that future direction.

Yoke can also load and save provider-native script workflows. This matches the
shape of Claude dynamic workflows: the script holds the orchestration, uses
helpers such as `agent()` and `pipeline()`, and keeps intermediate results in
script variables instead of the parent conversation.

```python
workflow = Workflow(
    name="audit-routes",
    description="Audit every route handler.",
    script="""
const found = await agent('List every route handler.', {
  schema: {
    type: 'object',
    required: ['files'],
    properties: { files: { type: 'array', items: { type: 'string' } } },
  },
})

const audits = await pipeline(found.files, file =>
  agent(`Audit ${file} for missing auth checks.`, { label: file }),
)

return audits.filter(Boolean)
""".strip(),
)
```

Script workflows round-trip through folders as `workflows/<name>/script.js`.
Yoke does not execute these through its local DAG runner. Running one delegates
to the selected provider adapter, so planning asks for `Feature.NATIVE_WORKFLOW`.
If the selected surface has no native workflow adapter, Yoke raises
`UnsupportedFeature` instead of pretending a portable DAG is equivalent.

Claude's native `Workflow` tool accepts `script`, `name`, `scriptPath`, `args`,
and `resumeFromRunId`. Yoke models that shape directly:

```python
inline = Workflow.from_script(
    "audit-routes",
    "return await agent('Audit route handlers')",
    args={"scope": "routes"},
)

saved = Workflow.from_name(
    "nightly-audit",
    args={"changed": True},
    resume_from_run_id="run-123",
)

file_backed = Workflow.from_file(
    "audit-routes",
    "workflows/audit-routes.js",
)

print(saved.native_input())
# {"name": "nightly-audit", "args": {"changed": True}, "resumeFromRunId": "run-123"}
```

If you specifically need a provider-native workflow primitive, ask for it
explicitly:

```python
plan = harness.plan(WorkflowOptions(native=True), runnable=False)
print(plan.surface)  # claude_typescript_sdk today
```

`status.workflow` reports the same distinction at runtime:

```python
status = await harness.status()
print(status.workflow.mode)
print(status.workflow.background, status.workflow.script)
print(status.workflow.max_concurrent_agents, status.workflow.max_agents)
```

Portable workflows remain the default. `native=True` does not make Yoke emulate
native support; it requires `Feature.NATIVE_WORKFLOW` and asks the adapter to
own execution. This is how step workflows can later be lowered into a
provider-native workflow surface without changing the SDK call.

## Codex app-server collaboration mode

Codex app-server has provider-native collaboration modes. Yoke exposes them as
Codex-specific typed options, not as portable Yoke subagents.

```python
from yoke import (
    CodexOptions,
    Collaboration,
    CollaborationSettings,
    ProviderOptions,
    RunOptions,
)

models = await harness.models()
model = next(model for model in models if model.id == "gpt-5.4-mini")

options = RunOptions(
    provider=ProviderOptions(
        codex=CodexOptions(
            collaboration=Collaboration(
                mode="plan",
                settings=CollaborationSettings(
                    developer_instructions=None,
                    model=model.id,
                    reasoning_effort="medium",
                ),
            )
        )
    )
)

result = await harness.run("Plan the refactor.", options)
```

`developer_instructions=None` is preserved because Codex app-server uses explicit
null to mean "use the built-in instructions for this collaboration mode."
`settings.model` is required when sending `collaborationMode`; use `model/list`
through `await harness.models()` or a known account-supported model rather than
hardcoding a model from another account.

Raw provider options still work for fields Yoke has not typed yet:

```python
ProviderOptions(codex={"collaboration_mode": {"mode": "plan", "settings": {}}})
```

Claude-specific SDK knobs use the same placement:

```python
from yoke import (
    ClaudeOptions,
    ClaudePermissionMode,
    ClaudeToolset,
    ProviderOptions,
    RunOptions,
)

options = RunOptions(
    provider=ProviderOptions(
        claude=ClaudeOptions(
            tools=ClaudeToolset(),  # native {"type": "preset", "preset": "claude_code"}
            setting_sources=("user", "project"),
            include_partial_messages=True,
            permission_mode=ClaudePermissionMode.DONT_ASK,
            allowed_tools=("Read", "Glob", "Grep"),
        )
    )
)

result = await harness.run("Use the project's Claude agents.", options)
```

`ClaudeOptions.tools` is Claude's top-level available toolset. It accepts exact
Claude built-in tool names such as `("Read", "Grep")`, an empty tuple/list to
disable built-ins, or `ClaudeToolset()` for the native Claude Code preset.
`ClaudeOptions.allowed_tools` is different: it only pre-approves matching tool
calls. It does not make those tools available if `tools` or `Agent.tools`
excluded them.

Runtime Claude approval callbacks and hooks live in SDK code, not in Yoke
folders:

```python
from yoke import Hook, HookEvent, Response
from yoke import RequestPolicy

async def approve_tool_call(event, default):
    if event.tool and event.tool.kind == "shell":
        return Response.deny("Shell needs a human reviewer.")
    return Response.allow()

async def block_dangerous_shell(input_data, tool_use_id, context):
    return {}

options = RunOptions(
    provider=ProviderOptions(
        claude=ClaudeOptions(
            request_handler=approve_tool_call,
            hooks=(
                Hook(
                    HookEvent.PRE_TOOL_USE,
                    matcher="Bash",
                    callbacks=(block_dangerous_shell,),
                    timeout=5,
                ),
            ),
        )
    )
)

for item in options.runtime_options():
    print(item.path, item.reason)
```

Claude SDK approval requests and `AskUserQuestion` prompts reach your
`request_handler` through Claude's native `can_use_tool` callback. `Hook(...)`
lowers to Claude's native `HookMatcher` shape for hook events such as
`PreToolUse`, `PostToolUse`, `Stop`, `SubagentStart`, and `PermissionRequest`.
You can still pass raw `can_use_tool` or raw Claude hook dictionaries if you
want direct Claude SDK objects. Codex app-server request handling is different:
it arrives through app-server request events. `status.control` reports both
shapes separately as `request_callbacks` and `request_events`.

For simple allow/deny policy, use `RequestPolicy`:

```python
policy = RequestPolicy.allow_tools("read", "search")

RunOptions(
    provider=ProviderOptions(
        claude=ClaudeOptions(policy=policy),
        codex=CodexOptions(
            app_server=CodexAppServerOptions(policy=policy),
        ),
    )
)
```

`RequestPolicy` returns Yoke `Response` values. Provider adapters lower those
responses to their native shapes. Because it is serializable, it can live in a
Yoke folder. Use `request_handler=` only for live Python callbacks. Keep
`CodexRequestPolicy` when you need a Codex app-server-specific decision such as
`acceptForSession`.

You can plan against that distinction directly:

```python
plan = harness.plan(features=(Feature.REQUEST_CALLBACKS,))
```

These fields are passed to `ClaudeAgentOptions`, excluded from
`model_dump()`, and rejected from normal folder saves unless you explicitly
allow lossy runtime-only omission.

Yoke-owned fields like `model`, tools, subagents, output format, and task budget
still come from the Yoke `Agent`, `RunOptions`, and `Goal`. `ClaudeOptions.raw`
is for extra `ClaudeAgentOptions` kwargs that Yoke has not typed yet.

Codex-specific autonomy controls stay in `CodexOptions` because Codex separates
sandbox and approvals:

```python
from yoke import CodexApproval, CodexOptions, CodexSandbox, ProviderOptions

options = RunOptions(
    provider=ProviderOptions(
        codex=CodexOptions(
            sandbox=CodexSandbox.WORKSPACE_WRITE,
            approval=CodexApproval.ON_REQUEST,
            network=False,
            writable_roots=("/path/to/repo",),
        )
    )
)
```

The neutral `Permissions` model is still useful for simple runs. Provider
options are for exact provider-native behavior.

Ask `status.permissions` when you need to know which shape a surface honors:

```python
status = await harness.status()
print(status.permissions.mode)
print(status.permissions.sandbox, status.permissions.approval)
print(status.permissions.permission_mode, status.permissions.tool_rules)
```

Codex surfaces report `codex_native`: sandbox, approval, network, and approval
reviewer controls are separate. Claude SDK surfaces report `claude_native`:
permission mode, tool rules, hooks, callbacks, and dynamic permission changes
belong to Claude's SDK model.

Planning sees provider-native permission requirements:

```python
plan = harness.plan(
    RunOptions(
        provider=ProviderOptions(
            codex=CodexOptions(sandbox=CodexSandbox.WORKSPACE_WRITE),
        )
    )
)
print(plan.features)         # (Feature.CODEX_PERMISSIONS,)
print(plan.profile.surface)  # codex_app_server
```

Explicit `RunOptions.permissions` asks for the neutral `permissions` feature.
Provider-native option fields ask for `codex_permissions` or
`claude_permissions`, so auto-surface selection does not silently choose a
surface that cannot honor those controls. Neutral `Permissions(...)` stays a
portable value object unless you explicitly require `Feature.PERMISSIONS`.

## Codex app-server experimental API

Codex app-server has a stable protocol surface and an opt-in experimental
surface. Yoke keeps that choice explicit:

```python
from yoke import CodexOptions, ProviderOptions, RunOptions

options = RunOptions(
    provider=ProviderOptions(
        codex=CodexOptions(experimental_api=True),
    )
)

plan = harness.plan(options)
print(plan.profile.surface)  # codex_app_server

result = await harness.run("Use an experimental app-server field.", options)
```

`experimental_api=True` makes Yoke initialize app-server with
`capabilities.experimentalApi`. Because app-server negotiates this once per
process, a stable session cannot be upgraded later by passing experimental
options to a single turn. Start the session with
`SessionOptions(provider=ProviderOptions(codex=CodexOptions(experimental_api=True)))`
when you need experimental app-server fields across a session.

Collaboration mode is separate from this flag. `collaborationMode` is a typed
Codex app-server turn option in Yoke; do not assume every collaboration feature
requires experimental API unless the app-server protocol marks that specific
field or method as experimental.

Yoke also types the high-value experimental `thread/start` and `turn/start`
fields from Codex app-server. These stay under `CodexOptions` because they are
provider-native runtime controls, not portable agent traits:

```python
options = RunOptions(
    provider=ProviderOptions(
        codex=CodexOptions(
            permissions=":workspace",
            runtime_workspace_roots=("/Users/me/project",),
            environments=({"environmentId": "local", "cwd": "/Users/me/project"},),
            selected_capability_roots=(
                {
                    "id": "github@openai",
                    "location": {
                        "type": "environment",
                        "environmentId": "workspace",
                        "path": "/opt/plugins/github",
                    },
                },
            ),
            allow_provider_model_fallback=True,
            service_tier="priority",
        )
    )
)
```

`permissions` selects a Codex permission profile such as `:workspace`. When it
is set, Yoke sends Codex app-server's `permissions` field and deliberately does
not send the legacy `sandbox` / `sandboxPolicy` field, because app-server rejects
that combination. Using any typed experimental app-server field automatically
initializes the Codex app-server process with `experimentalApi`.

Some app-server options are SDK-only. For example, `request_handler` is a live
Python callback for server requests, so it cannot be represented in a Yoke
folder. Use `policy=` when the logic is a serializable `RequestPolicy`.

Set `CodexAppServerOptions(ephemeral=True)` when a run should not persist its
thread in Codex history. The default remains persistent so sessions can be
resumed and forked. A native `Goal` always forces a persistent thread because
Codex does not support goals on ephemeral threads.

One-shot Claude SDK and Codex app-server runs can be bounded explicitly with
`RunOptions(timeout_seconds=60)`. The default is unchanged and uses the
provider adapter's normal lifetime. On expiry Yoke stops consuming the Claude
response or interrupts the active Codex turn and returns a failed `Run` with
`failure.code == "timeout"`; output already received from Claude is retained.

```python
from yoke import CodexAppServerOptions, CodexOptions, ProviderOptions, RunOptions

options = RunOptions(
    provider=ProviderOptions(
        codex=CodexOptions(
            app_server=CodexAppServerOptions(request_handler=my_handler),
        )
    )
)

for item in options.runtime_options():
    print(item.path, item.reason)
```

Codex app-server request events carry structured request and response values:

```python
async for event in session.stream("Make the safe change.", options):
    if event.request:
        print(event.request.kind, event.request.method)
        print(event.response.decision if event.response else None)
```

The transport stays provider-specific: Codex app-server requests arrive as
stream events, while Claude approval and question prompts enter through
`ClaudeOptions.can_use_tool`. The shared `Request` / `Response` values describe
what the embedding app is being asked and what answer was sent back.

You can ask Codex options how they enter the app-server surface:

```python
exposure = options.provider.codex.app_server_exposure()
print(exposure.stable)        # serializable initialize capabilities
print(exposure.experimental)  # experimentalApi gates
print(exposure.runtime)       # live callbacks and SDK objects
```

Serializable fields still round-trip through folders. Runtime-only fields stay
in SDK code. `Agent.save(...)` refuses to drop them silently unless you pass
`allow_runtime_only=True`. Serializable `raw` dictionaries are allowed, but
callables inside `raw` are treated as runtime-only values.

## Events

Yoke normalizes provider streams into small event objects:

```python
async for event in harness.stream("Make the change."):
    print(event.kind, event.text)
```

`harness.stream(...)` is the one-turn convenience path. It starts a short-lived
session, streams the turn, and closes the session when the stream ends.

Use an explicit session when you want conversation history across streamed
turns:

```python
session = await harness.start()
async for event in session.stream("Make the change."):
    print(event.kind, event.text)
```

Events can carry:

- resolved provider surface
- normalized text through `event.text` / `event.message`
- normalized tool lifecycle kinds
- `Tool` display metadata
- `Request` / `Response` values for provider approval or user-input requests
- `Goal` changes when a surface exposes native goal state
- `AgentCall` metadata for provider-native helper or collaboration activity
- `Usage`
- provider session ids
- source thread and turn ids
- raw provider payloads

### Token usage

`Usage` preserves provider token categories without estimating missing values.
Every field is `int | None`; `None` means the selected surface did not report
that value.

| Field | Meaning |
| --- | --- |
| `input_tokens` | Provider-reported ordinary input. For Codex this includes the cached-input subset; for Claude it excludes cache reads and cache writes. |
| `cache_creation_input_tokens` | Claude cache-write input. Other current surfaces report `None`. |
| `cached_input_tokens` | Provider-reported cache reads/reused input. It is a subset of Codex input, but a separate category for Claude. |
| `output_tokens` | Provider-reported output; Codex includes the reasoning-output subset. |
| `reasoning_output_tokens` | Separately reported Codex reasoning output. Claude Agent SDK does not expose this split. |
| `total_tokens` | Total for the event's provider scope. Yoke sums Claude ordinary input, cache writes, cache reads, and output because Claude exposes disjoint categories. |
| `total_processed_tokens` | A cumulative total only when the surface reports an aggregate: Codex app-server thread total, Claude final run result, or Claude background-task total. |
| `max_tokens` | Provider-reported context-window maximum, not a configured output limit. |

Do not add `cached_input_tokens` or `reasoning_output_tokens` to Codex totals:
both are already subsets. Claude final `ResultMessage.usage` is the aggregate
for that SDK query, so Yoke uses it as the run's final usage.

## Surfaces and capabilities

Yoke models capabilities by surface, not only by provider.

| Provider | Surface | Channel | Runtime | Good for |
| --- | --- | --- | --- | --- |
| Claude | `claude_python_sdk` | `sdk` | `claude_code` | one-shot, live sessions, skills, plugins, hooks, MCP, subagents |
| Claude | `claude_typescript_sdk` | `sdk` | `claude_code` | documented Claude SDK surface; tracked, no built-in adapter yet |
| Claude | `claude_cli` | `cli` | `claude_code` | interactive/headless Claude Code surface; tracked, no built-in adapter yet |
| Codex | `codex_cli` | `cli` | `codex_exec` | one-shot runs, JSONL events, resumable exec threads |
| Codex | `codex_python_sdk` | `sdk` | `codex_app_server` | published Python SDK, app-server-backed automation surface |
| Codex | `codex_typescript_sdk` | `sdk` | `codex_sdk` | documented TypeScript SDK over local Codex agents; tracked, no built-in adapter yet |
| Codex | `codex_app_server` | `app_server` | `codex_app_server` | live app protocol, streaming, skill roots, plugins, goals, collab agent events |

`Surface` intentionally names documented entrypoints even before Yoke ships a
built-in adapter for each one. That keeps design discussions precise: a feature
may be native in Codex app-server, available through the Codex Python SDK,
interactive-only in the CLI, or absent from a given surface.
`Channel` is the broader exposure path behind a surface, so reports can say
"this is SDK-backed" or "this is app-server-backed" without losing the exact
surface name.
`Runtime` is the provider machinery underneath the entrypoint. For example,
`codex_python_sdk` is an SDK channel, but it runs through the local Codex
app-server runtime.

Filter by channel when that is the important constraint:

```python
from yoke import Channel, Feature, profiles_for, select_profile

for profile in profiles_for("codex", channel=Channel.SDK):
    print(profile.surface)

profile = select_profile(
    "codex",
    requires=[Feature.READABLE_GOAL],
    channel=Channel.APP_SERVER,
)
```

The channel filter narrows candidates. It does not invent support. Asking for
`readable_goal` on `channel=Channel.SDK` still fails if no SDK-backed Codex
surface exposes native readable goals.

Ask one feature across every surface when provider docs differ:

```python
from yoke import Feature, matrix_for

for row in matrix_for("codex").feature(Feature.STREAMING):
    print(row.surface, row.channel, row.runtime, row.support)
```

Ask the adapter what a surface supports:

```python
from yoke import Feature

capabilities = harness.capabilities()
print(capabilities.support_for(Feature.MUTABLE_GOAL))
print(capabilities.support_for(Feature.GOAL_LOOP))
```

Support levels are `native`, `compiled`, `emulated`, `unsupported`, and
`unknown`.

`harness.report()` includes `lowering`, `recipes`, and `evidence` per feature
where the behavior needs explanation. `lowering` says how Yoke maps the feature
onto the provider. `recipes` show the Yoke entrypoints to call. `evidence`
links back to the provider docs or source that justify the row.

For example, Codex CLI declared subagents compile into prompt text for direct
runs but `bundle()` can write `.codex/agents/*.toml`; Codex app-server collab
agents are native provider events visible through streamed `event.agent_call`
payloads; Claude Python SDK subagents become `AgentDefinition` values; Yoke
workflows run as Yoke-owned DAG steps unless a surface exposes a distinct native
workflow primitive.

`capabilities()` is local metadata. `await harness.models()` is a live provider
call and can depend on the account currently signed in.

## Readiness

Readiness answers "is this provider surface available enough to try a run?"

```python
readiness = await harness.check()
```

It does not start an agent turn, list models, or set up credentials.

Embedding applications should use the richer, also non-paid preflight before
creating a durable run record:

```python
authentication = await harness.auth_status()
if not authentication.ready:
    raise RuntimeError(authentication.message)
```

`Authentication` reports provider, surface, accepted methods, selected method,
installation, authentication, compatibility, readiness, live-test status, and
a safe message. For an explicit Claude API key or OAuth token,
`authenticated` remains `None`: preflight confirms that the credential is
present without spending a model request to validate it. Gate execution on
`ready`; do not interpret `live_tested=False` as failure.

Codex Python SDK login is provider-persisted. After `Harness.login(...)`, call
`auth_status()` on the same or a new Harness: Yoke reads `codex.account()` and
reports the active persisted method as `api_key` or `chatgpt`. Device code is a
ChatGPT login transport, so a completed device-code login subsequently reports
`chatgpt`. `Authentication.methods` includes both external discovery and the
SDK's supported persisted login flows.

Codex app-server also reuses provider-persisted authentication, but login is
performed externally with `codex login`. Its `auth_status()` parses the safe
`codex login status` attestation: an isolated persisted API-key login reports
`method=api_key`, while a managed ChatGPT login reports `method=chatgpt`.
Unknown successful external modes remain `external`. Successful status messages
are normalized so masked credential fragments are not copied into application
records.

Current checks:

| Surface | Check |
| --- | --- |
| Claude Python SDK | `claude_agent_sdk`, then `ANTHROPIC_API_KEY` or `claude auth status` |
| Codex CLI | `codex login status` |
| Codex Python SDK | `openai_codex` import |
| Codex app-server | `codex login status` |

Current login support:

| Surface | Login |
| --- | --- |
| Codex Python SDK | `chatgpt`, `device_code`, `api_key` through `openai_codex` |
| Codex CLI | external `codex login` |
| Codex app-server | external Codex auth cache |
| Claude Python SDK | external `ANTHROPIC_API_KEY` or Claude Code auth |

Manual live smoke checks live outside the unit test suite. Start by asking the
script what is safe, what is live, and which command proves each surface:

```bash
python scripts/smoke_harnesses.py
python scripts/smoke_harnesses.py --json
python scripts/smoke_harnesses.py --plan
python scripts/smoke_harnesses.py --plan --json
python scripts/smoke_harnesses.py --json --capabilities
python scripts/smoke_harnesses.py --surface codex:app --plan
python scripts/smoke_harnesses.py --channel app_server --capabilities
python scripts/smoke_harnesses.py --feature readable_goal --json
```

`--plan` and `--list` never start provider turns. They print a smoke matrix with
`readiness` rows and opt-in `live` rows. Each row includes provider, surface,
channel, feature, safety, and the exact command to run.

Live smokes are explicit because they can be slow, billable, and
account-dependent. Examples:

```bash
python scripts/smoke_harnesses.py --surface codex:app --run-codex-app-server
python scripts/smoke_harnesses.py --surface codex:app --run-codex-app-stream
python scripts/smoke_harnesses.py --surface codex:app --run-codex-app-goal
python scripts/smoke_harnesses.py --surface codex:app --run-codex-app-goal-loop
python scripts/smoke_harnesses.py --surface codex:app --run-codex-app-fork
```

Optional SDK smokes can run with ephemeral dependencies:

```bash
uv run --with openai-codex python scripts/smoke_harnesses.py --surface codex:sdk --run-codex-sdk
uv run --with openai-codex python scripts/smoke_harnesses.py --surface codex:sdk --run-codex-sdk-stream
uv run --with claude-agent-sdk python scripts/smoke_harnesses.py --surface claude:sdk --run-claude
uv run --with claude-agent-sdk python scripts/smoke_harnesses.py --surface claude:sdk --run-claude-permissions
uv run --with claude-agent-sdk python scripts/smoke_harnesses.py --surface claude:sdk --run-claude-subagents
```

To exercise the complete folder contract on Codex and Claude concurrently,
including a packaged skill, a packaged subagent, and a subagent model, run:

```bash
uv run --with claude-agent-sdk python examples/live_folder_features.py
```

The check verifies that each requested model reaches the provider-specific
agent definition. Codex app-server events attest the effective model of the
nested run; Claude events currently do not, so the script reports that
distinction explicitly.

The first command checks surface readiness. The JSON form prints readiness-only
records for agents and integration checks. `--surface provider:surface` filters
readiness checks and accepts the same aliases as `Harness`, such as `codex:app`
and `claude:sdk`. `--capabilities` adds Yoke's declared static capability
report, including evidence URLs, to each JSON readiness record. In human output,
it prints a compact list of feature rows that have `lowering` text, so surface
behavior is visible without reading the whole matrix.

Recent live observations matter because provider surfaces differ. Codex Python
SDK streaming currently proves streamed transport plus `turn/completed`; it does
not expose final assistant text in Yoke events. Claude `can_use_tool` requires
an async prompt stream and native `PermissionResultAllow`/`PermissionResultDeny`
objects; the smoke uses a harmless hook to keep Claude's control channel open.

For optional SDK surfaces, transient `uv --with` checks are useful when you do
not want to install extras into the project environment:

```bash
uv run --with claude-agent-sdk python scripts/smoke_harnesses.py --surface claude:sdk --run-claude
uv run --with openai-codex python scripts/smoke_harnesses.py --surface codex:sdk --run-codex-sdk
```

This distinguishes package availability from provider auth/runtime behavior.

## Design references

Yoke is shaped by:

- Eve: filesystem-first authoring and discover/compile/run separation
- Claude Agent SDK: sessions, subagents, skills, hooks, MCP, plugins, task budgets
- Codex CLI: `codex exec --json`, resumable threads, structured output
- Codex SDKs: Python and TypeScript wrappers for local Codex agents
- Codex app-server: thread state, typed events, skill roots, mutable goals, collab tools
- Provider control docs: Codex separates auth, sandbox, approvals, and app-server controls; Claude exposes permissions, hooks, and runtime callbacks through SDK options
- Cosmic Python: ports, adapters, composition roots, and simple module ownership
