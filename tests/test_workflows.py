from __future__ import annotations

import asyncio
from pathlib import Path
from time import monotonic

from yoke import (
    Agent,
    Channel,
    Failure,
    Feature,
    Goal,
    Harness,
    Permissions,
    ProviderOptions,
    Run,
    RunOptions,
    RunStatus,
    Step,
    Support,
    Workflow,
    WorkflowLanguage,
    WorkflowOptions,
    WorkflowRun,
    WorkflowRunMode,
    clear_adapters,
    register,
)
from yoke.capabilities import Capabilities
from yoke.errors import UnsupportedFeature
from yoke.workflows import workflow_features


class FakeAdapter:
    provider = "claude"
    surface = "fake"
    capabilities = Capabilities.from_map(
        {
            Feature.ONE_SHOT: Support.NATIVE,
            Feature.WORKFLOW: Support.EMULATED,
            Feature.STRUCTURED_OUTPUT: Support.NATIVE,
            Feature.GOAL: Support.COMPILED,
        }
    )

    def __init__(self) -> None:
        self.schemas: list[dict[str, object] | None] = []
        self.prompts: list[str] = []
        self.goals: list[Goal | None] = []
        self.permissions: list[Permissions | None] = []
        self.providers: list[ProviderOptions | None] = []
        self.fail_at: int | None = None
        self.sleep_seconds: float = 0
        self.active = 0
        self.max_active = 0
        self.cancelled_prompts: list[str] = []

    async def run(self, harness, prompt, options):
        self.schemas.append(options.output_schema)
        self.prompts.append(prompt)
        self.goals.append(options.goal)
        self.permissions.append(options.permissions)
        self.providers.append(options.provider)
        call_number = len(self.schemas)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            if self.sleep_seconds:
                await asyncio.sleep(self.sleep_seconds)
            if self.fail_at == call_number:
                return Run(
                    provider="claude",
                    status=RunStatus.FAILED,
                    output="step failed",
                    failure=Failure(message="fake step failed"),
                )
            return Run(provider="claude", output=f"out-{call_number}")
        except asyncio.CancelledError:
            self.cancelled_prompts.append(prompt)
            raise
        finally:
            self.active -= 1

    async def start(self, harness, options):  # pragma: no cover - unused port method
        raise NotImplementedError

    async def send(self, session, turn, options):  # pragma: no cover - unused
        raise NotImplementedError

    async def stream(self, session, turn, options):  # pragma: no cover - unused
        if False:
            yield None

    async def get_goal(self, session):  # pragma: no cover - unused port method
        return None

    async def set_goal(self, session, goal):  # pragma: no cover - unused port method
        return session

    async def clear_goal(self, session):  # pragma: no cover - unused port method
        return session

    async def close(self, session):  # pragma: no cover - unused port method
        return None

    async def workflow(self, harness, workflow, prompt, options):
        raise UnsupportedFeature("fake adapter has no native workflow runner")


class FakeCodexAppWorkflowAdapter(FakeAdapter):
    provider = "codex"
    surface = "codex_app_server"
    capabilities = Capabilities.from_map(
        {
            Feature.ONE_SHOT: Support.NATIVE,
            Feature.WORKFLOW: Support.EMULATED,
        }
    )

    async def run(self, harness, prompt, options):
        self.prompts.append(f"{harness.surface}:{prompt}")
        return Run(provider="codex", output=str(harness.surface))


class FakeNativeWorkflowAdapter(FakeAdapter):
    capabilities = Capabilities.from_map(
        {
            Feature.ONE_SHOT: Support.NATIVE,
            Feature.WORKFLOW: Support.NATIVE,
            Feature.NATIVE_WORKFLOW: Support.NATIVE,
        }
    )

    async def workflow(self, harness, workflow, prompt, options):
        self.prompts.append(f"native:{workflow.name}:{prompt}")
        return WorkflowRun(
            workflow=workflow.name,
            mode=WorkflowRunMode.PROVIDER_NATIVE,
            provider=harness.provider,
            surface=harness.surface,
            output=f"native output for {prompt}",
            data={"input": workflow.native_input(), "native": options.native},
        )


class FakeMissingNativeWorkflowAdapter:
    provider = "claude"
    surface = "missing_native"
    capabilities = Capabilities.from_map(
        {
            Feature.ONE_SHOT: Support.NATIVE,
            Feature.WORKFLOW: Support.NATIVE,
            Feature.NATIVE_WORKFLOW: Support.NATIVE,
        }
    )

    async def run(self, harness, prompt, options):  # pragma: no cover - unused
        return Run(provider="claude", output=prompt)


def test_workflow_steps_pass_step_schema_or_workflow_fallback() -> None:
    asyncio.run(run_workflow_schema_check())


async def run_workflow_schema_check() -> None:
    clear_adapters()
    fake = register(FakeAdapter())
    workflow = Workflow(
        name="schema-check",
        steps=(
            Step(
                name="first",
                agent="main",
                prompt="first {input}",
                output_schema={"type": "object", "title": "StepSchema"},
            ),
            Step(name="second", agent="main", prompt="second {first}"),
        ),
    )
    harness = Harness(
        provider="claude",
        surface="fake",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    result = await harness.workflow(
        workflow,
        "hello",
        WorkflowOptions(output_schema={"type": "object", "title": "WorkflowFallback"}),
    )

    assert result.output == "out-2"
    assert result.mode is WorkflowRunMode.YOKE_PORTABLE
    assert result.provider == "claude"
    assert result.surface == "fake"
    assert [step.agent for step in result.steps] == ["main", "main"]
    assert [step.provider for step in result.steps] == ["claude", "claude"]
    assert [step.surface for step in result.steps] == ["fake", "fake"]
    assert [step.mode for step in result.steps] == [
        WorkflowRunMode.YOKE_PORTABLE,
        WorkflowRunMode.YOKE_PORTABLE,
    ]
    assert result.steps[0].prompt == "first hello"
    assert result.steps[0].depends_on == ()
    assert result.steps[1].prompt == "second out-1"
    assert result.steps[1].depends_on == ("first",)
    assert fake.schemas == [
        {"type": "object", "title": "StepSchema"},
        {"type": "object", "title": "WorkflowFallback"},
    ]
    assert fake.prompts == ["first hello", "second out-1"]


def test_workflow_fail_fast_stops_on_failed_step() -> None:
    asyncio.run(run_workflow_fail_fast_check())


async def run_workflow_fail_fast_check() -> None:
    clear_adapters()
    fake = register(FakeAdapter())
    fake.fail_at = 1
    harness = Harness(
        provider="claude",
        surface="fake",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )
    workflow = Workflow(
        name="failure-check",
        steps=(
            Step(name="first", agent="main", prompt="first {input}"),
            Step(name="second", agent="main", prompt="second {first}"),
        ),
    )

    result = await harness.workflow(workflow, "hello")

    assert result.status is RunStatus.FAILED
    assert result.failure is not None
    assert result.failure.message == "fake step failed"
    assert result.output == "step failed"
    assert [step.step for step in result.steps] == ["first"]
    assert result.failed_step is not None
    assert result.failed_step.step == "first"
    assert fake.prompts == ["first hello"]


def test_workflow_can_continue_after_failed_step() -> None:
    asyncio.run(run_workflow_continue_after_failure_check())


async def run_workflow_continue_after_failure_check() -> None:
    clear_adapters()
    fake = register(FakeAdapter())
    fake.fail_at = 1
    harness = Harness(
        provider="claude",
        surface="fake",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )
    workflow = Workflow(
        name="failure-check",
        steps=(
            Step(name="first", agent="main", prompt="first {input}"),
            Step(name="second", agent="main", prompt="second {first}"),
        ),
    )

    result = await harness.workflow(
        workflow,
        "hello",
        WorkflowOptions(fail_fast=False),
    )

    assert result.status is RunStatus.FAILED
    assert result.failure is not None
    assert result.failure.message == "fake step failed"
    assert result.output == "out-2"
    assert [step.step for step in result.steps] == ["first", "second"]
    assert fake.prompts == ["first hello", "second step failed"]


def test_workflow_runs_ready_steps_concurrently() -> None:
    asyncio.run(run_workflow_concurrency_check())


async def run_workflow_concurrency_check() -> None:
    clear_adapters()
    fake = register(FakeAdapter())
    fake.sleep_seconds = 0.01
    harness = Harness(
        provider="claude",
        surface="fake",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )
    workflow = Workflow(
        name="concurrency-check",
        steps=(
            Step(name="alpha", agent="main", prompt="alpha {input}"),
            Step(name="beta", agent="main", prompt="beta {input}"),
            Step(name="join", agent="main", prompt="join {alpha} {beta}"),
        ),
    )

    result = await harness.workflow(
        workflow,
        "hello",
        WorkflowOptions(concurrency=2),
    )

    assert result.status is RunStatus.SUCCEEDED
    assert result.failed_step is None
    assert result.output == "out-3"
    assert [step.step for step in result.steps] == ["alpha", "beta", "join"]
    assert [step.depends_on for step in result.steps] == [(), (), ("alpha", "beta")]
    assert fake.max_active == 2
    assert fake.prompts == [
        "alpha hello",
        "beta hello",
        "join out-1 out-2",
    ]


def test_workflow_step_timeout_is_typed_and_observable() -> None:
    asyncio.run(run_workflow_step_timeout_check())


async def run_workflow_step_timeout_check() -> None:
    clear_adapters()
    fake = register(FakeAdapter())
    fake.sleep_seconds = 0.05
    events = []
    harness = Harness(
        provider="claude",
        surface="fake",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )
    workflow = Workflow(
        name="timeout-check",
        steps=(Step(name="slow", prompt="slow {input}"),),
    )

    result = await harness.workflow(
        workflow,
        "hello",
        WorkflowOptions(step_timeout_seconds=0.01, on_event=events.append),
    )

    assert result.status is RunStatus.FAILED
    assert result.failed_step_name == "slow"
    assert result.interrupted_steps == ()
    assert result.failed_step is not None
    assert result.failure is not None
    assert "timed out" in result.failure.message
    assert [event.kind for event in events] == ["step_started", "step_timed_out"]
    assert events[-1].name == "slow"
    assert fake.cancelled_prompts == ["slow hello"]


def test_workflow_callback_may_be_async_and_follows_dependency_order() -> None:
    asyncio.run(run_workflow_async_callback_check())


async def run_workflow_async_callback_check() -> None:
    clear_adapters()
    register(FakeAdapter())
    seen: list[tuple[str, str | None]] = []

    async def observe(event) -> None:
        await asyncio.sleep(0)
        seen.append((event.kind, event.name))

    harness = Harness(
        provider="claude",
        surface="fake",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )
    result = await harness.workflow(
        Workflow(
            name="events",
            steps=(
                Step(name="first", prompt="first {input}"),
                Step(name="second", prompt="second {first}"),
            ),
        ),
        "hello",
        WorkflowOptions(on_event=observe),
    )

    assert result.ok
    assert seen == [
        ("step_started", "first"),
        ("step_completed", "first"),
        ("step_started", "second"),
        ("step_completed", "second"),
    ]
    assert [(trace.kind, trace.name) for trace in result.traces] == seen


def test_fail_fast_cancels_concurrent_siblings_and_keeps_completed_results() -> None:
    asyncio.run(run_workflow_fail_fast_cancellation_check())


async def run_workflow_fail_fast_cancellation_check() -> None:
    class VariedAdapter(FakeAdapter):
        async def run(self, harness, prompt, options):
            self.prompts.append(prompt)
            self.active += 1
            try:
                if prompt.startswith("done"):
                    await asyncio.sleep(0.005)
                    return Run(provider="claude", output="finished")
                if prompt.startswith("fail"):
                    await asyncio.sleep(0.015)
                    return Run(
                        provider="claude",
                        status=RunStatus.FAILED,
                        output="failed",
                        failure=Failure(message="planned failure"),
                    )
                await asyncio.sleep(1)
                return Run(provider="claude", output="too late")
            except asyncio.CancelledError:
                self.cancelled_prompts.append(prompt)
                raise
            finally:
                self.active -= 1

    clear_adapters()
    fake = register(VariedAdapter())
    events = []
    harness = Harness(
        provider="claude",
        surface="fake",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )
    started = monotonic()
    result = await harness.workflow(
        Workflow(
            name="cancel",
            steps=(
                Step(name="done", prompt="done {input}"),
                Step(name="fail", prompt="fail {input}"),
                Step(name="slow", prompt="slow {input}"),
            ),
        ),
        "hello",
        WorkflowOptions(concurrency=3, on_event=events.append),
    )

    assert monotonic() - started < 0.2
    assert result.status is RunStatus.FAILED
    assert [step.step for step in result.steps] == ["done", "fail"]
    assert result.failed_step_name == "fail"
    assert result.interrupted_steps == ("slow",)
    assert fake.cancelled_prompts == ["slow hello"]
    assert ("step_completed", "done") in [
        (event.kind, event.name) for event in events
    ]
    assert ("step_failed", "fail") in [
        (event.kind, event.name) for event in events
    ]


def test_overall_timeout_preserves_results_and_interrupted_steps() -> None:
    asyncio.run(run_workflow_overall_timeout_check())


async def run_workflow_overall_timeout_check() -> None:
    class VariedAdapter(FakeAdapter):
        async def run(self, harness, prompt, options):
            self.prompts.append(prompt)
            try:
                await asyncio.sleep(0.005 if prompt.startswith("quick") else 1)
                return Run(provider="claude", output=prompt)
            except asyncio.CancelledError:
                self.cancelled_prompts.append(prompt)
                raise

    clear_adapters()
    fake = register(VariedAdapter())
    harness = Harness(
        provider="claude",
        surface="fake",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )
    result = await harness.workflow(
        Workflow(
            name="overall",
            steps=(
                Step(name="quick", prompt="quick {input}"),
                Step(name="slow", prompt="slow {input}"),
            ),
        ),
        "hello",
        WorkflowOptions(concurrency=2, timeout_seconds=0.02),
    )

    assert result.status is RunStatus.FAILED
    assert [step.step for step in result.steps] == ["quick"]
    assert result.interrupted_steps == ("slow",)
    assert result.failed_step_name == "slow"
    assert result.failure is not None
    assert "workflow timed out" in result.failure.message
    assert fake.cancelled_prompts == ["slow hello"]
    assert result.traces[-1].kind == "step_timed_out"
    assert result.traces[-1].name == "slow"


def test_workflow_callback_is_runtime_only_and_timeouts_serialize() -> None:
    def callback(event) -> None:
        pass

    options = WorkflowOptions(
        timeout_seconds=10,
        step_timeout_seconds=2,
        on_event=callback,
    )

    assert [item.path for item in options.runtime_options()] == ["on_event"]
    assert options.model_dump(mode="json", exclude={"on_event"}) == {
        "channel": None,
        "concurrency": 4,
        "fail_fast": True,
        "native": False,
        "resume": None,
        "memory": None,
        "run": RunOptions().model_dump(mode="json"),
        "output_schema": None,
        "timeout_seconds": 10.0,
        "step_timeout_seconds": 2.0,
    }


def test_provider_exception_becomes_typed_failure_and_cancels_sibling() -> None:
    asyncio.run(run_provider_exception_check())


async def run_provider_exception_check() -> None:
    class RaisingAdapter(FakeAdapter):
        async def run(self, harness, prompt, options):
            self.prompts.append(prompt)
            try:
                if prompt.startswith("done"):
                    await asyncio.sleep(0.005)
                    return Run(provider="claude", output="kept")
                if prompt.startswith("raise"):
                    await asyncio.sleep(0.015)
                    raise ConnectionError("provider transport broke")
                await asyncio.sleep(1)
                return Run(provider="claude", output="late")
            except asyncio.CancelledError:
                self.cancelled_prompts.append(prompt)
                raise

    clear_adapters()
    fake = register(RaisingAdapter())
    harness = Harness(
        provider="claude",
        surface="fake",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )
    result = await harness.workflow(
        Workflow(
            name="provider-exception",
            steps=(
                Step(name="done", prompt="done {input}"),
                Step(name="raise", prompt="raise {input}"),
                Step(name="slow", prompt="slow {input}"),
            ),
        ),
        "hello",
        WorkflowOptions(concurrency=3),
    )

    assert not result.ok
    assert [step.step for step in result.steps] == ["done", "raise"]
    assert result.steps[0].run.output == "kept"
    assert result.failed_step_name == "raise"
    assert result.interrupted_steps == ("slow",)
    assert result.failure is not None
    assert result.failure.message == "provider transport broke"
    assert "ConnectionError" in (result.failure.raw or "")
    assert fake.cancelled_prompts == ["slow hello"]
    assert [(trace.kind, trace.name) for trace in result.traces][-1] == (
        "step_failed",
        "raise",
    )


def test_observer_exception_is_recorded_without_stopping_workflow() -> None:
    asyncio.run(run_observer_exception_check())


async def run_observer_exception_check() -> None:
    clear_adapters()
    register(FakeAdapter())

    async def broken_observer(event) -> None:
        raise RuntimeError(f"cannot observe {event.kind}")

    harness = Harness(
        provider="claude",
        surface="fake",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )
    result = await harness.workflow(
        Workflow(
            name="observer",
            steps=(Step(name="one", prompt="one {input}"),),
        ),
        "hello",
        WorkflowOptions(on_event=broken_observer),
    )

    assert result.ok
    assert [trace.kind for trace in result.traces] == [
        "step_started",
        "observer_failed",
        "step_completed",
        "observer_failed",
    ]
    failures = [trace for trace in result.traces if trace.kind == "observer_failed"]
    assert [trace.name for trace in failures] == ["one", "one"]
    assert failures[0].data == {"event_kind": "step_started"}
    assert failures[0].output == "cannot observe step_started"


def test_workflow_options_pass_run_options_to_each_step() -> None:
    asyncio.run(run_workflow_run_options_check())


async def run_workflow_run_options_check() -> None:
    clear_adapters()
    fake = register(FakeAdapter())
    goal = Goal("Finish the workflow.")
    permissions = Permissions(network=True)
    provider = ProviderOptions(codex={"raw": {"example": True}})
    harness = Harness(
        provider="claude",
        surface="fake",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )
    workflow = Workflow(
        name="options-check",
        steps=(
            Step(name="first", prompt="first {input}"),
            Step(name="second", prompt="second {first}"),
        ),
    )

    result = await harness.workflow(
        workflow,
        "hello",
        WorkflowOptions(
            run=RunOptions(
                goal=goal,
                permissions=permissions,
                provider=provider,
                output_schema={"type": "object", "title": "RunSchema"},
            )
        ),
    )

    assert result.status is RunStatus.SUCCEEDED
    assert fake.goals == [goal, goal]
    assert fake.permissions == [permissions, permissions]
    assert fake.providers == [provider, provider]
    assert fake.schemas == [
        {"type": "object", "title": "RunSchema"},
        {"type": "object", "title": "RunSchema"},
    ]


def test_run_accepts_yaml_style_options() -> None:
    asyncio.run(run_yaml_style_run_options_check())


async def run_yaml_style_run_options_check() -> None:
    clear_adapters()
    fake = register(FakeAdapter())
    harness = Harness(
        provider="claude",
        surface="fake",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    result = await harness.run(
        "hello",
        {
            "goal": {"objective": "Dict run goal."},
            "output_schema": {"type": "object", "title": "DictRunSchema"},
        },
    )

    assert result.status is RunStatus.SUCCEEDED
    assert fake.goals == [Goal("Dict run goal.")]
    assert fake.schemas == [{"type": "object", "title": "DictRunSchema"}]


def test_workflow_steps_can_override_run_options() -> None:
    asyncio.run(run_workflow_step_run_options_check())


async def run_workflow_step_run_options_check() -> None:
    clear_adapters()
    fake = register(FakeAdapter())
    workflow_goal = Goal("Default workflow goal.")
    step_goal = Goal("Step-specific goal.")
    workflow_permissions = Permissions(access="read")
    step_permissions = Permissions(access="write")
    harness = Harness(
        provider="claude",
        surface="fake",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )
    workflow = Workflow(
        name="step-options-check",
        steps=(
            Step(
                name="first",
                prompt="first {input}",
                run=RunOptions(
                    goal=step_goal,
                    permissions=step_permissions,
                    output_schema={"type": "object", "title": "StepRunSchema"},
                ),
            ),
            Step(name="second", prompt="second {first}"),
        ),
    )

    result = await harness.workflow(
        workflow,
        "hello",
        WorkflowOptions(
            run=RunOptions(
                goal=workflow_goal,
                permissions=workflow_permissions,
                output_schema={"type": "object", "title": "WorkflowRunSchema"},
            )
        ),
    )

    assert result.status is RunStatus.SUCCEEDED
    assert fake.goals == [step_goal, workflow_goal]
    assert fake.permissions == [step_permissions, workflow_permissions]
    assert fake.schemas == [
        {"type": "object", "title": "StepRunSchema"},
        {"type": "object", "title": "WorkflowRunSchema"},
    ]


def test_workflow_steps_accept_yaml_style_run_options() -> None:
    asyncio.run(run_workflow_yaml_style_step_run_options_check())


async def run_workflow_yaml_style_step_run_options_check() -> None:
    clear_adapters()
    fake = register(FakeAdapter())
    harness = Harness(
        provider="claude",
        surface="fake",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )
    workflow = Workflow(
        name="yaml-step-options-check",
        steps=(
            Step(
                name="first",
                prompt="first {input}",
                run={"goal": {"objective": "YAML-style step goal."}},
            ),
        ),
    )

    result = await harness.workflow(workflow, "hello")

    assert result.status is RunStatus.SUCCEEDED
    assert fake.goals[0] == Goal("YAML-style step goal.")


def test_workflow_features_include_step_run_options() -> None:
    workflow = Workflow(
        name="feature-check",
        steps=(
            Step(
                name="first",
                prompt="first {input}",
                run=RunOptions(goal=Goal("Step goal.")),
            ),
        ),
    )

    features = workflow_features(
        workflow,
        WorkflowOptions(),
        Agent(instructions="test"),
        provider="codex",
    )

    assert Feature.WORKFLOW in features
    assert Feature.GOAL in features


def test_workflow_options_channel_selects_surface() -> None:
    asyncio.run(run_workflow_options_channel_selects_surface())


async def run_workflow_options_channel_selects_surface() -> None:
    clear_adapters()
    fake = register(FakeCodexAppWorkflowAdapter())
    workflow = Workflow(
        name="channel-check",
        steps=(Step(name="first", prompt="first {input}"),),
    )
    harness = Harness(
        provider="codex",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    result = await harness.workflow(
        workflow,
        "hello",
        WorkflowOptions(channel=Channel.APP_SERVER),
    )

    assert result.output == "codex_app_server"
    assert result.mode is WorkflowRunMode.YOKE_PORTABLE
    assert result.provider == "codex"
    assert result.surface == "codex_app_server"
    assert fake.prompts == ["codex_app_server:first hello"]


def test_script_workflow_requires_native_workflow_feature() -> None:
    workflow = Workflow(
        name="audit-routes",
        script="return await agent('Audit the routes')",
    )

    features = workflow_features(
        workflow,
        WorkflowOptions(),
        Agent(instructions="test"),
        provider="claude",
    )

    assert workflow.language is WorkflowLanguage.JAVASCRIPT
    assert Feature.WORKFLOW in features
    assert Feature.NATIVE_WORKFLOW in features


def test_script_workflow_runs_through_native_adapter() -> None:
    asyncio.run(run_script_workflow_native_adapter_check())


async def run_script_workflow_native_adapter_check() -> None:
    clear_adapters()
    fake = register(FakeNativeWorkflowAdapter())
    harness = Harness(
        provider="claude",
        surface="fake",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )
    workflow = Workflow(
        name="audit-routes",
        script="return await agent('Audit the routes')",
    )

    result = await harness.workflow(workflow, "hello")

    assert result.mode is WorkflowRunMode.PROVIDER_NATIVE
    assert result.provider == "claude"
    assert result.surface == "fake"
    assert result.output == "native output for hello"
    assert result.data == {
        "input": {"script": "return await agent('Audit the routes')"},
        "native": False,
    }
    assert fake.prompts == ["native:audit-routes:hello"]


def test_script_workflow_rejects_runnable_surface_without_native_workflows() -> None:
    clear_adapters()
    harness = Harness(
        provider="codex",
        surface="codex_app_server",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )
    workflow = Workflow.from_script(
        "audit-routes",
        "return await agent('Audit the routes')",
    )

    try:
        harness.workflow_sync(workflow, "hello")
    except UnsupportedFeature as error:
        assert "native_workflow" in str(error)
        assert "codex:codex_app_server" in str(error)
    else:
        raise AssertionError("expected UnsupportedFeature")


def test_native_workflow_runtime_error_names_boundary() -> None:
    asyncio.run(run_native_workflow_runtime_error_check())


async def run_native_workflow_runtime_error_check() -> None:
    clear_adapters()
    register(FakeMissingNativeWorkflowAdapter())
    harness = Harness(
        provider="claude",
        surface="missing_native",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )
    workflow = Workflow.from_script(
        "audit-routes",
        "return await agent('Audit the routes')",
    )

    try:
        await harness.workflow(workflow, "hello")
    except UnsupportedFeature as error:
        message = str(error)
        assert "claude:missing_native" in message
        assert "provider-native workflow 'audit-routes'" in message
        assert "inline script" in message
        assert "Use portable step workflows or Workflow.run(...)" in message
    else:
        raise AssertionError("expected UnsupportedFeature")


def test_native_option_delegates_step_workflow_to_native_adapter() -> None:
    asyncio.run(run_native_option_step_workflow_check())


async def run_native_option_step_workflow_check() -> None:
    clear_adapters()
    fake = register(FakeNativeWorkflowAdapter())
    harness = Harness(
        provider="claude",
        surface="fake",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )
    workflow = Workflow(
        name="native-steps",
        steps=(Step(name="first", prompt="first {input}"),),
    )

    result = await harness.workflow(
        workflow,
        "hello",
        WorkflowOptions(native=True),
    )

    assert result.mode is WorkflowRunMode.PROVIDER_NATIVE
    assert result.data == {"input": {}, "native": True}
    assert fake.prompts == ["native:native-steps:hello"]


def test_workflow_accepts_yaml_style_options() -> None:
    asyncio.run(run_yaml_style_workflow_options_check())


async def run_yaml_style_workflow_options_check() -> None:
    clear_adapters()
    fake = register(FakeNativeWorkflowAdapter())
    harness = Harness(
        provider="claude",
        surface="fake",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )
    workflow = Workflow(
        name="native-dict-options",
        steps=(Step(name="first", prompt="first {input}"),),
    )

    result = await harness.workflow(workflow, "hello", {"native": True})

    assert result.mode is WorkflowRunMode.PROVIDER_NATIVE
    assert result.data == {"input": {}, "native": True}
    assert fake.prompts == ["native:native-dict-options:hello"]


def test_file_workflow_requires_native_workflow_feature() -> None:
    workflow = Workflow.from_file(
        "audit-routes",
        "workflows/audit-routes.js",
        args={"scope": "routes"},
    )

    features = workflow_features(
        workflow,
        WorkflowOptions(),
        Agent(instructions="test"),
        provider="claude",
    )

    assert workflow.native is True
    assert workflow.native_input() == {
        "scriptPath": "workflows/audit-routes.js",
        "args": {"scope": "routes"},
    }
    assert Feature.NATIVE_WORKFLOW in features


def test_named_workflow_matches_claude_workflow_tool_input() -> None:
    workflow = Workflow.from_name(
        "nightly-audit",
        args={"changed": True},
        resume_from_run_id="run-123",
    )

    assert workflow.native is True
    assert workflow.steps == ()
    assert workflow.native_input() == {
        "name": "nightly-audit",
        "args": {"changed": True},
        "resumeFromRunId": "run-123",
    }


def test_workflow_rejects_steps_and_native_body_together() -> None:
    try:
        Workflow(
            name="invalid",
            script="return 1",
            steps=(Step(name="step", prompt="{input}"),),
        )
    except ValueError as exc:
        assert "either portable steps or a native workflow body" in str(exc)
    else:  # pragma: no cover - assertion branch
        raise AssertionError("workflow accepted both steps and script")


def test_workflow_rejects_resume_without_invocation_target() -> None:
    try:
        Workflow(name="invalid", resume_from_run_id="run-123")
    except ValueError as exc:
        assert "script, native_name, or script_path" in str(exc)
    else:  # pragma: no cover - assertion branch
        raise AssertionError("workflow accepted resume without target")
