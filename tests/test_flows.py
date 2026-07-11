from __future__ import annotations

import asyncio
from pathlib import Path

from yoke import (
    Agent,
    Feature,
    Harness,
    Run,
    Support,
    Workflow,
    WorkflowMemory,
    WorkflowOptions,
    WorkflowStore,
    clear_adapters,
    register,
)
from yoke.capabilities import Capabilities


class FakeWorkflowAdapter:
    provider = "claude"
    surface = "fake"
    capabilities = Capabilities.from_map(
        {
            Feature.ONE_SHOT: Support.NATIVE,
            Feature.WORKFLOW: Support.EMULATED,
            Feature.GOAL: Support.COMPILED,
        }
    )

    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.agents: list[str | None] = []
        self.active = 0
        self.max_active = 0

    async def run(self, harness, prompt, options):
        self.prompts.append(prompt)
        self.agents.append(harness.agent.description)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(0.01)
            return Run(
                provider="claude",
                surface="fake",
                output=f"{harness.agent.description}:{prompt}",
            )
        finally:
            self.active -= 1


def test_workflow_runs_agents_pipeline_phases_and_returns_one_output() -> None:
    asyncio.run(run_workflow_pipeline_check())


async def run_workflow_pipeline_check() -> None:
    clear_adapters()
    fake = register(FakeWorkflowAdapter())
    harness = Harness(
        provider="claude",
        surface="fake",
        cwd=Path.cwd(),
        agent=Agent(
            instructions="Coordinate.",
            description="main",
            subagents={
                "researcher": Agent(
                    instructions="Research.",
                    description="researcher",
                ),
                "reviewer": Agent(
                    instructions="Review.",
                    description="reviewer",
                ),
            },
        ),
    )

    async def program(ctx):
        async with ctx.phase("research"):
            found = await ctx.agent("researcher", f"Find {ctx.args['topic']}")
        reviews = await ctx.pipeline(
            ["api", "cli"],
            lambda item: ctx.agent("reviewer", f"Review {item}"),
            phase="review",
            concurrency=2,
        )
        return ctx.summarize((found, *reviews), separator=" | ")

    workflow = Workflow("audit", description="Audit routes.").run(program)

    result = await harness.workflow(
        workflow,
        {"topic": "routes"},
        WorkflowOptions(concurrency=2, resume="workflow-run-1"),
    )

    assert result.ok
    assert result.workflow == "audit"
    assert result.run_id == "workflow-run-1"
    assert result.resume_from_run_id == "workflow-run-1"
    assert result.output == (
        "researcher:Find routes | reviewer:Review api | reviewer:Review cli"
    )
    assert fake.prompts == ["Find routes", "Review api", "Review cli"]
    assert fake.agents == ["researcher", "reviewer", "reviewer"]
    assert fake.max_active == 2
    assert [trace.kind for trace in result.traces] == [
        "phase_start",
        "agent",
        "phase_end",
        "phase_start",
        "agent",
        "agent",
        "phase_end",
        "pipeline",
        "summary",
    ]
    assert result.traces[1].phase == "research"
    assert result.traces[7].phase == "review"
    assert {trace.id for trace in result.traces} == {"workflow-run-1"}


def test_workflow_runs_python_program_with_workflow_semantics() -> None:
    asyncio.run(run_workflow_program_check())


async def run_workflow_program_check() -> None:
    clear_adapters()
    fake = register(FakeWorkflowAdapter())
    harness = Harness(
        provider="claude",
        surface="fake",
        cwd=Path.cwd(),
        agent=Agent(
            instructions="Coordinate.",
            description="main",
            subagents={
                "reviewer": Agent(instructions="Review.", description="reviewer")
            },
        ),
    )

    async def program(ctx):
        return await ctx.agent("reviewer", f"Review {ctx.args}")

    workflow = Workflow("review").run(program)
    result = await harness.workflow(
        workflow,
        "api",
        WorkflowOptions(resume="workflow-run-1", memory=WorkflowMemory()),
    )

    assert result.ok
    assert result.workflow == "review"
    assert result.run_id == "workflow-run-1"
    assert result.output == "reviewer:Review api"
    assert result.traces[0].agent == "reviewer"
    assert fake.prompts == ["Review api"]


def test_workflow_sync_supports_sync_programs() -> None:
    clear_adapters()
    register(FakeWorkflowAdapter())
    harness = Harness(
        provider="claude",
        surface="fake",
        cwd=Path.cwd(),
        agent=Agent(instructions="Coordinate.", description="main"),
    )
    workflow = Workflow("hello").run(lambda ctx: f"hello {ctx.args}")

    result = harness.workflow_sync(workflow, "world")

    assert result.ok
    assert result.output == "hello world"
    assert result.data is None
    assert result.traces == ()


def test_program_workflow_overall_timeout_is_a_typed_failure() -> None:
    asyncio.run(run_program_workflow_timeout_check())


async def run_program_workflow_timeout_check() -> None:
    clear_adapters()
    register(FakeWorkflowAdapter())
    harness = Harness(
        provider="claude",
        surface="fake",
        cwd=Path.cwd(),
        agent=Agent(instructions="Coordinate.", description="main"),
    )

    async def program(ctx):
        await asyncio.sleep(1)
        return "late"

    result = await harness.workflow(
        Workflow("bounded").run(program),
        options=WorkflowOptions(timeout_seconds=0.01),
    )

    assert not result.ok
    assert result.failed_step_name == "program"
    assert result.interrupted_steps == ("program",)
    assert result.failure is not None
    assert result.failure.message == "workflow timed out"


def test_workflow_unknown_agent_fails_with_flow_result() -> None:
    asyncio.run(run_workflow_unknown_agent_check())


async def run_workflow_unknown_agent_check() -> None:
    clear_adapters()
    register(FakeWorkflowAdapter())
    harness = Harness(
        provider="claude",
        surface="fake",
        cwd=Path.cwd(),
        agent=Agent(instructions="Coordinate.", description="main"),
    )

    async def program(ctx):
        return await ctx.agent("missing", "do work")

    result = await harness.workflow(Workflow("bad").run(program))

    assert not result.ok
    assert result.failure is not None
    assert "unknown agent" in result.failure.message


def test_workflow_memory_replays_unchanged_agent_calls() -> None:
    asyncio.run(run_workflow_memory_replay_check())


async def run_workflow_memory_replay_check() -> None:
    clear_adapters()
    fake = register(FakeWorkflowAdapter())
    memory = WorkflowMemory()
    harness = Harness(
        provider="claude",
        surface="fake",
        cwd=Path.cwd(),
        agent=Agent(
            instructions="Coordinate.",
            description="main",
            subagents={
                "reviewer": Agent(instructions="Review.", description="reviewer")
            },
        ),
    )

    async def program(ctx):
        return await ctx.agent("reviewer", f"Review {ctx.args}")

    workflow = Workflow("review").run(program)

    first = await harness.workflow(
        workflow,
        "api",
        WorkflowOptions(resume="run-1", memory=memory),
    )
    second = await harness.workflow(
        workflow,
        "api",
        WorkflowOptions(resume="run-1", memory=memory),
    )
    third = await harness.workflow(
        workflow,
        "cli",
        WorkflowOptions(resume="run-1", memory=memory),
    )

    assert first.output == "reviewer:Review api"
    assert second.output == "reviewer:Review api"
    assert third.output == "reviewer:Review cli"
    assert fake.prompts == ["Review api", "Review cli"]
    assert first.traces[0].cached is False
    assert second.traces[0].cached is True
    assert third.traces[0].cached is False


def test_workflow_store_replays_across_store_instances(tmp_path: Path) -> None:
    asyncio.run(run_workflow_store_replay_check(tmp_path))


async def run_workflow_store_replay_check(tmp_path: Path) -> None:
    clear_adapters()
    fake = register(FakeWorkflowAdapter())
    path = tmp_path / "workflow.jsonl"
    harness = Harness(
        provider="claude",
        surface="fake",
        cwd=Path.cwd(),
        agent=Agent(
            instructions="Coordinate.",
            description="main",
            subagents={
                "reviewer": Agent(instructions="Review.", description="reviewer")
            },
        ),
    )

    async def program(ctx):
        return await ctx.agent("reviewer", f"Review {ctx.args}")

    workflow = Workflow("review").run(program)

    first = await harness.workflow(
        workflow,
        "api",
        WorkflowOptions(resume="run-1", memory=WorkflowStore(path)),
    )
    second = await harness.workflow(
        workflow,
        "api",
        WorkflowOptions(resume="run-1", memory=WorkflowStore(path)),
    )

    assert first.output == "reviewer:Review api"
    assert second.output == "reviewer:Review api"
    assert fake.prompts == ["Review api"]
    assert first.traces[0].cached is False
    assert second.traces[0].cached is True
    assert path.read_text().count("\n") == 1
    assert "provider_session_id" not in path.read_text()


def test_workflow_runs_python_program_from_file(tmp_path: Path) -> None:
    asyncio.run(run_workflow_program_file_check(tmp_path))


async def run_workflow_program_file_check(tmp_path: Path) -> None:
    clear_adapters()
    register(FakeWorkflowAdapter())
    program = tmp_path / "workflow.py"
    program.write_text(
        "async def main(ctx):\n"
        "    run = await ctx.agent('reviewer', f'Review {ctx.args}')\n"
        "    return run.output\n"
    )
    harness = Harness(
        provider="claude",
        surface="fake",
        cwd=Path.cwd(),
        agent=Agent(
            instructions="Coordinate.",
            description="main",
            subagents={
                "reviewer": Agent(instructions="Review.", description="reviewer")
            },
        ),
    )

    result = await harness.workflow(
        Workflow.from_program("review", program),
        "api",
        WorkflowOptions(resume="file-run-1"),
    )

    assert result.ok
    assert result.workflow == "review"
    assert result.run_id == "file-run-1"
    assert result.output == "reviewer:Review api"
    assert result.traces[0].agent == "reviewer"


def test_workflow_program_uses_configured_args_by_default(tmp_path: Path) -> None:
    asyncio.run(run_workflow_program_default_args_check(tmp_path))


async def run_workflow_program_default_args_check(tmp_path: Path) -> None:
    clear_adapters()
    register(FakeWorkflowAdapter())
    program = tmp_path / "workflow.py"
    program.write_text("async def main(ctx):\n    return ctx.args['scope']\n")
    harness = Harness(
        provider="claude",
        surface="fake",
        cwd=Path.cwd(),
        agent=Agent(instructions="Coordinate.", description="main"),
    )

    result = await harness.workflow(
        Workflow.from_program("audit", program, args={"scope": "routes"})
    )

    assert result.ok
    assert result.output == "routes"
