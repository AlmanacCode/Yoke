from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

from yoke import (
    Agent,
    Channel,
    ClaudeOptions,
    ClaudePermissionMode,
    CodexOptions,
    CodexSandbox,
    Collaboration,
    Event,
    Feature,
    Goal,
    Harness,
    Model,
    Permissions,
    ProviderOptions,
    Run,
    Session,
    Skill,
    Support,
    Workflow,
    adapter_for,
    capabilities_for,
    clear_adapters,
    fits_for,
    matrix_for,
    profile_for,
    profiles_for,
    report_for,
    reports_for,
    runtime_for,
    select_profile,
)
from yoke.adapters import register
from yoke.capabilities import Capabilities
from yoke.errors import UnsupportedFeature
from yoke.options import GoalLoopOptions, RunOptions, SessionOptions, WorkflowOptions


@pytest.fixture(autouse=True)
def reset_adapters_between_tests():
    clear_adapters()
    yield
    clear_adapters()


def collaboration_provider() -> ProviderOptions:
    return ProviderOptions(
        codex=CodexOptions(
            collaboration=Collaboration(
                mode="plan",
                settings={"model": "gpt-5.4"},
            )
        )
    )


def test_unknown_capability_is_not_support() -> None:
    capabilities = Capabilities.from_map({Feature.ONE_SHOT: Support.UNKNOWN})

    assert capabilities.support_for(Feature.ONE_SHOT) is Support.UNKNOWN
    assert not capabilities.supports(Feature.ONE_SHOT)


def test_capabilities_are_declared_per_surface() -> None:
    codex_cli = adapter_for("codex", "codex_cli").capabilities
    codex_app = adapter_for("codex", "codex_app_server").capabilities
    claude = adapter_for("claude", "claude_python_sdk").capabilities

    assert codex_cli.support_for(Feature.READABLE_GOAL) is Support.UNSUPPORTED
    assert codex_app.support_for(Feature.READABLE_GOAL) is Support.NATIVE
    assert claude.support_for(Feature.READABLE_GOAL) is Support.UNSUPPORTED
    assert codex_cli.support_for(Feature.SESSION_LIST) is Support.UNSUPPORTED
    assert codex_app.support_for(Feature.SESSION_LIST) is Support.NATIVE
    assert claude.support_for(Feature.SESSION_LIST) is Support.NATIVE
    assert codex_app.support_for(Feature.SESSION_READ) is Support.NATIVE
    assert claude.support_for(Feature.SESSION_READ) is Support.NATIVE
    assert codex_app.support_for(Feature.SESSION_RESUME) is Support.NATIVE
    assert claude.support_for(Feature.SESSION_RESUME) is Support.NATIVE
    assert codex_app.support_for(Feature.SESSION_COMPACT) is Support.NATIVE
    assert claude.support_for(Feature.SESSION_COMPACT) is Support.UNSUPPORTED
    assert capabilities_for("codex", "codex_python_sdk").support_for(
        Feature.SESSION_COMPACT
    ) is Support.UNKNOWN
    assert codex_app.support_for(Feature.SESSION_RENAME) is Support.NATIVE
    assert codex_app.support_for(Feature.SESSION_TAG) is Support.UNSUPPORTED
    assert claude.support_for(Feature.SESSION_RENAME) is Support.NATIVE
    assert claude.support_for(Feature.SESSION_TAG) is Support.NATIVE
    assert codex_cli.support_for(Feature.GOAL_LOOP) is Support.NATIVE
    assert codex_app.support_for(Feature.GOAL_LOOP) is Support.NATIVE
    assert claude.support_for(Feature.GOAL_LOOP) is Support.NATIVE
    assert capabilities_for("claude", "claude_cli").support_for(
        Feature.GOAL_LOOP
    ) is Support.NATIVE

    assert codex_cli.support_for(Feature.MODELS) is Support.UNSUPPORTED
    assert codex_app.support_for(Feature.MODELS) is Support.NATIVE
    assert claude.support_for(Feature.MODELS) is Support.UNSUPPORTED
    assert codex_cli.support_for(Feature.LOGIN) is Support.UNSUPPORTED
    assert capabilities_for("codex", "codex_python_sdk").support_for(
        Feature.LOGIN
    ) is Support.NATIVE
    assert claude.support_for(Feature.LOGIN) is Support.UNSUPPORTED
    assert claude.support_for(Feature.PERMISSIONS) is Support.NATIVE
    assert claude.support_for(Feature.CLAUDE_PERMISSIONS) is Support.NATIVE
    assert claude.support_for(Feature.CODEX_PERMISSIONS) is Support.UNSUPPORTED
    assert codex_cli.support_for(Feature.PERMISSIONS) is Support.NATIVE
    assert codex_cli.support_for(Feature.CODEX_PERMISSIONS) is Support.UNSUPPORTED
    assert codex_cli.support_for(Feature.REQUEST_EVENTS) is Support.UNSUPPORTED
    assert codex_cli.support_for(Feature.REQUEST_CALLBACKS) is Support.UNSUPPORTED
    assert codex_app.support_for(Feature.CODEX_PERMISSIONS) is Support.NATIVE
    assert codex_app.support_for(Feature.REQUEST_EVENTS) is Support.NATIVE
    assert codex_app.support_for(Feature.REQUEST_CALLBACKS) is Support.UNSUPPORTED
    assert claude.support_for(Feature.REQUEST_EVENTS) is Support.UNSUPPORTED
    assert claude.support_for(Feature.REQUEST_CALLBACKS) is Support.NATIVE

    assert codex_cli.support_for(Feature.SKILLS) is Support.NATIVE
    assert codex_cli.support_for(Feature.PLUGINS) is Support.NATIVE
    assert codex_cli.support_for(Feature.MCP) is Support.NATIVE
    assert codex_cli.support_for(Feature.FILESYSTEM_AGENT) is Support.NATIVE
    assert claude.support_for(Feature.DECLARED_SUBAGENTS) is Support.NATIVE
    assert claude.support_for(Feature.PLUGINS) is Support.NATIVE

    assert codex_cli.support_for(Feature.WORKFLOW) is Support.EMULATED
    assert codex_app.support_for(Feature.WORKFLOW) is Support.EMULATED
    assert claude.support_for(Feature.WORKFLOW) is Support.EMULATED
    assert codex_app.support_for(Feature.NATIVE_WORKFLOW) is Support.UNSUPPORTED
    assert capabilities_for("claude", "claude_typescript_sdk").support_for(
        Feature.NATIVE_WORKFLOW
    ) is Support.NATIVE

    assert codex_app.support_for(Feature.INLINE_SUBAGENTS) is Support.UNSUPPORTED
    assert codex_cli.support_for(Feature.DECLARED_SUBAGENTS) is Support.COMPILED
    assert codex_app.support_for(Feature.DECLARED_SUBAGENTS) is Support.COMPILED
    assert codex_cli.support_for(Feature.COLLAB_AGENT_TOOLS) is Support.UNSUPPORTED
    assert codex_app.support_for(Feature.COLLAB_AGENT_TOOLS) is Support.NATIVE
    assert codex_app.support_for(Feature.COLLABORATION_MODE) is Support.NATIVE
    assert codex_app.support_for(Feature.EXPERIMENTAL_API) is Support.NATIVE
    assert codex_app.support_for(Feature.PLUGINS) is Support.NATIVE
    assert codex_app.support_for(Feature.INTERRUPT) is Support.NATIVE
    assert codex_app.support_for(Feature.FORK) is Support.NATIVE
    assert claude.support_for(Feature.INTERRUPT) is Support.NATIVE
    assert codex_cli.support_for(Feature.COLLABORATION_MODE) is Support.UNSUPPORTED
    assert codex_cli.support_for(Feature.EXPERIMENTAL_API) is Support.UNSUPPORTED
    assert codex_cli.support_for(Feature.INTERRUPT) is Support.UNSUPPORTED
    assert codex_cli.support_for(Feature.FORK) is Support.UNSUPPORTED
    assert claude.support_for(Feature.COLLAB_AGENT_TOOLS) is Support.UNSUPPORTED


def test_harness_and_session_expose_surface_capabilities() -> None:
    harness = Harness(
        provider="codex",
        surface="codex_app_server",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )
    session = Session(
        provider="codex",
        surface="codex_app_server",
        id="thread-1",
    )

    assert harness.capabilities().support_for(Feature.MODELS) is Support.NATIVE
    assert session.capabilities().support_for(Feature.READABLE_GOAL) is Support.NATIVE
    assert harness.profile().surface == "codex_app_server"
    assert harness.profile().support_for(Feature.MODELS) is Support.NATIVE
    assert harness.report().surface == "codex_app_server"
    assert harness.report().model_dump()["provider"] == "codex"
    assert harness.report().runtime == "codex_app_server"
    assert session.profile().supports(Feature.READABLE_GOAL)
    assert session.report().surface == "codex_app_server"
    assert harness.fit(Feature.MODELS).ok
    assert session.fit(Feature.READABLE_GOAL).ok
    assert session.fit(Feature.SESSION_COMPACT).ok
    assert session.fit(Feature.SESSION_RENAME).ok
    assert harness.fits(Feature.MODELS)[0].profile.surface == "codex_app_server"
    assert session.fits(Feature.READABLE_GOAL)[0].profile.surface == (
        "codex_app_server"
    )
    assert harness.plan(features=(Feature.MODELS,)).profile.surface == (
        "codex_app_server"
    )
    assert session.plan(features=(Feature.READABLE_GOAL,)).ok


def test_harness_plan_uses_option_features_without_running() -> None:
    harness = Harness(
        provider="codex",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )
    plan = harness.plan(RunOptions(output_schema=StructuredAnswer))

    assert plan.features == (Feature.STRUCTURED_OUTPUT,)
    assert plan.profile.surface == "codex_app_server"
    assert plan.ok


def test_run_event_callback_selects_or_rejects_the_surface() -> None:
    callback = RunOptions(on_event=lambda event: None)
    automatic = Harness(
        provider="codex",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    plan = automatic.plan(callback)

    assert plan.ok
    assert plan.features == (Feature.RUN_EVENT_CALLBACKS,)
    assert plan.profile.surface == "codex_app_server"

    for surface in ("codex_cli", "codex_python_sdk"):
        unsupported = automatic.model_copy(update={"surface": surface})
        with pytest.raises(UnsupportedFeature, match="run_event_callbacks"):
            unsupported.plan(callback).raise_for_status()


def test_claude_run_event_callback_uses_python_sdk() -> None:
    harness = Harness(
        provider="claude",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    plan = harness.plan(RunOptions(on_event=lambda event: None))

    assert plan.ok
    assert plan.profile.surface == "claude_python_sdk"


@pytest.mark.asyncio
async def test_run_event_callback_fails_before_unsupported_codex_run() -> None:
    harness = Harness(
        provider="codex",
        surface="codex_cli",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    with pytest.raises(UnsupportedFeature, match="run_event_callbacks"):
        await harness.run("do not start", RunOptions(on_event=lambda event: None))


def test_agent_features_declare_goal_skills_subagents_and_workflows() -> None:
    agent = Agent(
        instructions="Coordinate.",
        goal=Goal("Finish safely."),
        skills=(Skill.from_text("Use primary docs.", name="research"),),
        subagents={
            "reviewer": Agent(
                description="Reviews patches.",
                instructions="Find correctness bugs.",
            )
        },
        workflows={"review": Workflow("review")},
    )

    assert agent.features() == (
        Feature.GOAL,
        Feature.SKILLS,
        Feature.DECLARED_SUBAGENTS,
        Feature.WORKFLOW,
    )


def test_harness_plan_uses_agent_feature_requirements() -> None:
    harness = Harness(
        provider="codex",
        agent=Agent(
            instructions="Coordinate.",
            skills=(Skill.from_text("Use primary docs.", name="research"),),
            subagents={
                "reviewer": Agent(
                    description="Reviews patches.",
                    instructions="Find correctness bugs.",
                )
            },
            workflows={"review": Workflow("review")},
        ),
        cwd=Path.cwd(),
    )

    plan = harness.plan()

    assert plan.features == (
        Feature.SKILLS,
        Feature.DECLARED_SUBAGENTS,
        Feature.WORKFLOW,
    )
    assert plan.ok
    assert plan.profile.surface == "codex_app_server"


def test_plan_reports_explain_selected_surface_lowering() -> None:
    harness = Harness(
        provider="codex",
        agent=Agent(
            instructions="Coordinate.",
            goal=Goal("Ship safely."),
            skills=(Skill.from_text("Use primary docs.", name="research"),),
            subagents={
                "reviewer": Agent(
                    description="Reviews patches.",
                    instructions="Find correctness bugs.",
                )
            },
            workflows={"review": Workflow("review")},
        ),
        cwd=Path.cwd(),
    )

    plan = harness.plan()
    rows = {row.feature: row for row in plan.reports}

    assert plan.profile.surface == "codex_app_server"
    assert set(rows) == {
        "goal",
        "skills",
        "declared_subagents",
        "workflow",
    }
    assert rows["goal"].support == "native"
    assert "thread/goal" in (rows["goal"].lowering or "")
    assert rows["skills"].support == "native"
    assert "skill roots" in (rows["skills"].lowering or "")
    assert rows["declared_subagents"].support == "compiled"
    assert "spawn_agent" in (rows["declared_subagents"].lowering or "")
    assert rows["workflow"].support == "emulated"
    assert "app-server turns" in (rows["workflow"].lowering or "")
    assert "await harness.workflow(workflow, prompt)" in rows["workflow"].recipes
    assert "https://developers.openai.com/codex/app-server" in (
        rows["goal"].evidence
    )
    assert plan.report(Feature.GOAL) == rows["goal"]
    assert plan.report(Feature.READABLE_GOAL) is None


def test_agent_features_include_subagent_shape() -> None:
    agent = Agent(
        instructions="Coordinate.",
        subagents={
            "researcher": Agent(
                description="Researcher.",
                instructions="Research.",
                goal=Goal("Research safely."),
                skills=(Skill.from_text("Use source docs.", name="sources"),),
                workflows={"summarize": Workflow("summarize")},
            )
        },
    )

    assert agent.features() == (
        Feature.DECLARED_SUBAGENTS,
        Feature.GOAL,
        Feature.SKILLS,
        Feature.WORKFLOW,
    )


def test_agent_feature_requirements_guard_explicit_surface() -> None:
    harness = Harness(
        provider="codex",
        surface="codex_typescript_sdk",
        agent=Agent(
            instructions="Coordinate.",
            skills=(Skill.from_text("Use primary docs.", name="research"),),
        ),
        cwd=Path.cwd(),
    )

    with pytest.raises(UnsupportedFeature, match="skills"):
        harness.run_sync("Use the research skill.")


def test_harness_plan_can_require_neutral_permissions_feature() -> None:
    harness = Harness(
        provider="codex",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )
    plan = harness.plan(features=(Feature.PERMISSIONS,))

    assert plan.features == (Feature.PERMISSIONS,)
    assert plan.profile.surface == "codex_app_server"
    assert plan.ok

    explicit_cli = harness.model_copy(update={"surface": "codex_cli"}).plan(
        features=(Feature.PERMISSIONS,)
    )
    assert explicit_cli.profile.surface == "codex_cli"
    assert explicit_cli.ok


def test_harness_plan_uses_codex_native_permission_features() -> None:
    harness = Harness(
        provider="codex",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )
    options = RunOptions(
        provider=ProviderOptions(
            codex=CodexOptions(sandbox=CodexSandbox.WORKSPACE_WRITE)
        )
    )

    plan = harness.plan(options)

    assert plan.features == (Feature.CODEX_PERMISSIONS,)
    assert plan.profile.surface == "codex_app_server"
    assert plan.ok


def test_harness_plan_uses_claude_native_permission_features() -> None:
    harness = Harness(
        provider="claude",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )
    options = RunOptions(
        provider=ProviderOptions(
            claude=ClaudeOptions(
                permission_mode=ClaudePermissionMode.DONT_ASK,
            )
        )
    )

    plan = harness.plan(options)

    assert plan.features == (Feature.CLAUDE_PERMISSIONS,)
    assert plan.profile.surface == "claude_python_sdk"
    assert plan.ok


def test_harness_plan_can_require_request_callbacks() -> None:
    harness = Harness(
        provider="claude",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    plan = harness.plan(features=(Feature.REQUEST_CALLBACKS,))

    assert plan.ok
    assert plan.profile.surface == "claude_python_sdk"
    assert plan.profile.support_for(Feature.REQUEST_CALLBACKS) is Support.NATIVE


def test_codex_request_events_are_not_request_callbacks() -> None:
    codex = Harness(
        provider="codex",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    events = codex.plan(features=(Feature.REQUEST_EVENTS,))

    assert events.ok
    assert events.profile.surface == "codex_app_server"
    with pytest.raises(UnsupportedFeature, match="request_callbacks"):
        codex.plan(features=(Feature.REQUEST_CALLBACKS,))


def test_harness_plan_uses_claude_runtime_permission_features() -> None:
    harness = Harness(
        provider="claude",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    def can_use_tool(*_args, **_kwargs):
        return None

    options = RunOptions(
        provider=ProviderOptions(
            claude=ClaudeOptions(
                can_use_tool=can_use_tool,
                hooks={"PreToolUse": (can_use_tool,)},
            )
        )
    )

    plan = harness.plan(options)

    assert plan.features == (Feature.CLAUDE_PERMISSIONS, Feature.REQUEST_CALLBACKS)
    assert plan.profile.surface == "claude_python_sdk"
    assert plan.ok


def test_harness_plan_dedupes_option_and_explicit_features() -> None:
    harness = Harness(
        provider="codex",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    plan = harness.plan(
        RunOptions(output_schema=StructuredAnswer),
        features=(Feature.STRUCTURED_OUTPUT,),
    )

    assert plan.features == (Feature.STRUCTURED_OUTPUT,)


def test_harness_plan_respects_explicit_surface() -> None:
    harness = Harness(
        provider="codex",
        surface="codex_typescript_sdk",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )
    plan = harness.plan(RunOptions(output_schema=StructuredAnswer))

    assert plan.profile.surface == "codex_typescript_sdk"
    assert plan.provider == "codex"
    assert plan.surface == "codex_typescript_sdk"
    assert not plan.ok
    assert plan.missing == (Feature.STRUCTURED_OUTPUT,)
    assert plan.fit.missing == (Feature.STRUCTURED_OUTPUT,)


def test_plan_can_raise_for_status() -> None:
    ok_plan = Harness(
        provider="codex",
        surface="codex_app_server",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    ).plan(RunOptions(output_schema=StructuredAnswer))

    assert ok_plan.raise_for_status() is ok_plan

    bad_plan = Harness(
        provider="codex",
        surface="codex_typescript_sdk",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    ).plan(RunOptions(output_schema=StructuredAnswer))

    try:
        bad_plan.raise_for_status()
    except UnsupportedFeature as error:
        assert "codex:codex_typescript_sdk" in str(error)
        assert "structured_output" in str(error)
    else:
        raise AssertionError("expected UnsupportedFeature")


def test_profile_for_resolves_default_surface() -> None:
    profile = profile_for("codex")

    assert profile.default
    assert profile.provider == "codex"
    assert profile.surface == "codex_app_server"
    assert profile.support_for(Feature.ONE_SHOT) is Support.NATIVE


def test_profile_helpers_accept_provider_surface_aliases() -> None:
    codex = profile_for("codex", "app")
    claude = profile_for("claude", "sdk")
    compact_codex = profile_for("codex:app-server")
    compact_claude = profile_for("claude:agent-sdk")

    assert codex.surface == "codex_app_server"
    assert codex.support_for(Feature.READABLE_GOAL) is Support.NATIVE
    assert claude.surface == "claude_python_sdk"
    assert claude.support_for(Feature.STREAMING) is Support.NATIVE
    assert compact_codex.surface == "codex_app_server"
    assert compact_claude.surface == "claude_python_sdk"


def test_harness_accepts_compact_provider_surface_specs() -> None:
    harness = Harness(
        "codex:app",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )
    session = Session("claude:sdk", id="session-1")

    assert harness.provider == "codex"
    assert harness.surface == "codex_app_server"
    assert harness.profile().channel is Channel.APP_SERVER
    assert harness.profile().runtime == "codex_app_server"
    assert session.provider == "claude"
    assert session.surface == "claude_python_sdk"
    assert session.profile().channel is Channel.SDK


def test_compact_provider_surface_rejects_conflicting_explicit_surface() -> None:
    try:
        Harness(
            "codex:app",
            surface="cli",
            agent=Agent(instructions="test"),
            cwd=Path.cwd(),
        )
    except ValueError as error:
        assert "conflicts with explicit surface" in str(error)
    else:
        raise AssertionError("expected ValueError")


def test_report_for_returns_json_friendly_surface_capabilities() -> None:
    report = report_for("codex", "app")
    features = {feature.feature: feature for feature in report.features}

    assert report.key == "codex:codex_app_server"
    assert report.provider == "codex"
    assert report.surface == "codex_app_server"
    assert report.channel == "app_server"
    assert report.runtime == "codex_app_server"
    assert report.runnable is True
    assert "https://developers.openai.com/codex/app-server" in report.evidence
    assert features["readable_goal"].support == "native"
    assert features["readable_goal"].note is None
    assert features["readable_goal"].lowering == (
        "Session.get_goal calls app-server thread/goal/get."
    )
    assert features["readable_goal"].recipes == ("goal = await session.get_goal()",)
    assert "https://developers.openai.com/codex/app-server" in (
        features["readable_goal"].evidence
    )
    assert all(isinstance(feature.feature, str) for feature in report.features)
    assert all(isinstance(feature.support, str) for feature in report.features)
    assert all(
        isinstance(recipe, str)
        for feature in report.features
        for recipe in feature.recipes
    )
    assert all(
        isinstance(source, str)
        for feature in report.features
        for source in feature.evidence
    )
    assert all(isinstance(source, str) for source in report.evidence)


def test_feature_reports_explain_provider_surface_differences() -> None:
    codex_cli = report_for("codex", "cli")
    codex_app = report_for("codex", "app")
    claude = report_for("claude", "sdk")

    codex_cli_features = {feature.feature: feature for feature in codex_cli.features}
    codex_app_features = {feature.feature: feature for feature in codex_app.features}
    claude_features = {feature.feature: feature for feature in claude.features}

    assert codex_cli_features["readable_goal"].support == "unsupported"
    assert codex_app_features["readable_goal"].support == "native"
    assert claude_features["readable_goal"].support == "unsupported"
    assert codex_app_features["goal_loop"].support == "native"
    assert "follow-goals" in codex_app_features["goal_loop"].evidence[0]
    assert codex_app_features["readable_goal"].evidence == (
        "https://developers.openai.com/codex/app-server",
    )
    assert "https://developers.openai.com/codex/subagents" in (
        codex_app_features["collab_agent_tools"].evidence
    )
    assert "https://code.claude.com/docs/en/agent-sdk/subagents" in (
        claude_features["inline_subagents"].evidence
    )
    assert "https://code.claude.com/docs/en/agent-sdk/python" in (
        claude_features["session_list"].evidence
    )
    assert "prompt text" in codex_cli_features["declared_subagents"].lowering
    assert ".codex/agents" in codex_cli_features["filesystem_agent"].lowering
    assert "collabToolCall" in codex_app_features["collab_agent_tools"].lowering
    assert (
        "collabAgentToolCall"
        in codex_app_features["collab_agent_tools"].lowering
    )
    assert "event.agent_call" in codex_app_features["collab_agent_tools"].recipes
    assert "AgentDefinition" in claude_features["inline_subagents"].lowering
    assert claude_features["inline_subagents"].recipes == (
        "Agent(subagents=[Agent(name=..., instructions=...)])",
    )
    assert "SDK turns" in claude_features["workflow"].lowering
    assert "list_sessions" in claude_features["session_list"].lowering
    assert "thread/list" in codex_app_features["session_list"].lowering


def test_feature_reports_explain_native_vs_emulated_workflows() -> None:
    claude_python = report_for("claude", "sdk")
    claude_typescript = report_for("claude", "typescript")
    codex_app = report_for("codex", "app")

    claude_python_features = {
        feature.feature: feature for feature in claude_python.features
    }
    claude_typescript_features = {
        feature.feature: feature for feature in claude_typescript.features
    }
    codex_app_features = {feature.feature: feature for feature in codex_app.features}

    assert claude_python_features["workflow"].support == "emulated"
    assert "not Claude's TypeScript Workflow tool" in (
        claude_python_features["workflow"].lowering
    )
    assert claude_typescript_features["native_workflow"].support == "native"
    assert "native Workflow tool" in (
        claude_typescript_features["native_workflow"].lowering
    )
    assert claude_typescript_features["native_workflow"].recipes == (
        "Tracked as provider-native; no built-in Yoke Python adapter yet.",
    )
    assert codex_app_features["workflow"].support == "emulated"
    assert "native collab agents" in codex_app_features["workflow"].lowering


def test_feature_reports_include_surface_specific_yoke_recipes() -> None:
    codex_app = {
        feature.feature: feature for feature in report_for("codex", "app").features
    }
    codex_sdk = {
        feature.feature: feature for feature in report_for("codex", "sdk").features
    }
    claude_sdk = {
        feature.feature: feature for feature in report_for("claude", "sdk").features
    }

    assert "async for event in session.stream(prompt): ..." in (
        codex_app["streaming"].recipes
    )
    assert codex_app["mutable_goal"].recipes == (
        "await session.set_goal(goal)",
        "await session.clear_goal()",
    )
    assert 'await harness.login("chatgpt")' in codex_sdk["login"].recipes
    assert "fork = await session.fork()" in claude_sdk["fork"].recipes
    assert "sessions = await harness.sessions(limit=10)" in (
        claude_sdk["session_list"].recipes
    )
    assert "history = await harness.read_session(thread_id)" in (
        codex_app["session_read"].recipes
    )


def test_goal_loop_is_distinct_from_goal_state() -> None:
    codex_app = {
        feature.feature: feature for feature in report_for("codex", "app").features
    }
    codex_sdk = {
        feature.feature: feature for feature in report_for("codex", "sdk").features
    }
    claude_cli = {
        feature.feature: feature for feature in report_for("claude", "cli").features
    }
    claude_sdk = {
        feature.feature: feature for feature in report_for("claude", "sdk").features
    }

    assert codex_app["goal"].support == "native"
    assert codex_app["goal_loop"].support == "native"
    assert "persisted goal state" in (codex_app["goal_loop"].lowering or "")
    assert "provider-owned" in (codex_app["goal_loop"].lowering or "")
    assert codex_sdk["goal"].support == "compiled"
    assert codex_sdk["goal_loop"].support == "unsupported"
    assert claude_cli["goal_loop"].support == "native"
    assert "/goal <condition>" in claude_cli["goal_loop"].recipes
    assert claude_sdk["goal"].support == "compiled"
    assert claude_sdk["goal_loop"].support == "native"
    assert "/goal" in (claude_sdk["goal_loop"].lowering or "")
    assert "readable or mutable goal state" in (claude_sdk["goal_loop"].note or "")
    assert "https://code.claude.com/docs/en/goal" in (
        claude_sdk["goal_loop"].evidence
    )


def test_plugins_are_distinct_from_skills() -> None:
    claude_sdk = {
        feature.feature: feature for feature in report_for("claude", "sdk").features
    }
    codex_cli = {
        feature.feature: feature for feature in report_for("codex", "cli").features
    }
    codex_sdk = {
        feature.feature: feature for feature in report_for("codex", "sdk").features
    }
    codex_app = {
        feature.feature: feature for feature in report_for("codex", "app").features
    }

    assert claude_sdk["skills"].support == "native"
    assert claude_sdk["plugins"].support == "native"
    assert "local plugins" in (claude_sdk["plugins"].lowering or "")
    assert codex_cli["plugins"].support == "native"
    assert "app, CLI, and IDE" in (codex_cli["plugins"].note or "")
    assert codex_sdk["skills"].support == "compiled"
    assert codex_sdk["plugins"].support == "unsupported"
    assert codex_app["plugins"].support == "native"
    assert "external agent configuration" in (codex_app["plugins"].lowering or "")


def test_provider_report_can_show_one_feature_across_surfaces() -> None:
    rows = matrix_for("codex").feature(Feature.STREAMING)
    support = {row.surface: row.support for row in rows}

    assert support["codex_cli"] == "native"
    assert support["codex_python_sdk"] == "native"
    assert support["codex_app_server"] == "native"
    assert support["codex_typescript_sdk"] == "unknown"
    app_server = next(row for row in rows if row.surface == "codex_app_server")
    assert app_server.channel == "app_server"
    assert app_server.runtime == "codex_app_server"
    assert "session.stream" in " ".join(app_server.recipes)
    assert "app-server" in " ".join(app_server.evidence)


def test_reports_for_filters_runnable_surfaces() -> None:
    reports = reports_for("codex", runnable=True)

    assert {report.surface for report in reports} == {
        "codex_cli",
        "codex_python_sdk",
        "codex_app_server",
    }


def test_profiles_for_lists_known_provider_surfaces() -> None:
    profiles = profiles_for("codex")

    assert {profile.surface for profile in profiles} >= {
        "codex_cli",
        "codex_python_sdk",
        "codex_typescript_sdk",
        "codex_app_server",
    }
    assert {profile.surface for profile in profiles_for("codex", runnable=True)} == {
        "codex_cli",
        "codex_python_sdk",
        "codex_app_server",
    }


def test_profiles_expose_provider_channel() -> None:
    assert profile_for("codex", "cli").channel is Channel.CLI
    assert profile_for("codex", "sdk").channel is Channel.SDK
    assert profile_for("codex", "app").channel is Channel.APP_SERVER
    assert profile_for("claude", "sdk").channel is Channel.SDK
    assert profile_for("claude", "cli").channel is Channel.CLI
    assert report_for("codex", "app").model_dump()["channel"] == "app_server"


def test_profiles_expose_provider_runtime() -> None:
    assert profile_for("codex", "cli").runtime == "codex_exec"
    assert profile_for("codex", "sdk").runtime == "codex_app_server"
    assert profile_for("codex", "app").runtime == "codex_app_server"
    assert profile_for("codex", "typescript").runtime == "codex_sdk"
    assert profile_for("claude", "sdk").runtime == "claude_code"
    assert profile_for("claude", "typescript").runtime == "claude_code"
    assert profile_for("claude", "cli").runtime == "claude_code"
    assert runtime_for("codex", "codex_python_sdk") == "codex_app_server"
    assert report_for("codex", "sdk").model_dump()["runtime"] == "codex_app_server"


def test_profile_helpers_filter_by_channel() -> None:
    codex_app = profiles_for("codex", channel=Channel.APP_SERVER)
    codex_sdk = profiles_for("codex", channel="sdk")
    claude_cli = reports_for("claude", channel=Channel.CLI)

    assert [profile.surface for profile in codex_app] == ["codex_app_server"]
    assert {profile.surface for profile in codex_sdk} == {
        "codex_python_sdk",
        "codex_typescript_sdk",
    }
    assert [report.surface for report in claude_cli] == ["claude_cli"]


def test_matrix_for_returns_json_friendly_provider_surface_matrix() -> None:
    matrix = matrix_for("codex", channel=Channel.APP_SERVER, runnable=True)

    assert matrix.provider == "codex"
    assert matrix.channel == "app_server"
    assert matrix.runnable is True
    assert [surface.surface for surface in matrix.surfaces] == [
        "codex_app_server"
    ]
    assert matrix.model_dump()["surfaces"][0]["channel"] == "app_server"
    assert matrix.model_dump()["surfaces"][0]["runtime"] == "codex_app_server"


def test_channel_filter_participates_in_surface_selection() -> None:
    sdk_fit = fits_for(
        "codex",
        requires=[Feature.STREAMING],
        channel=Channel.SDK,
    )[0]
    app_profile = select_profile(
        "codex",
        requires=[Feature.READABLE_GOAL],
        channel=Channel.APP_SERVER,
    )

    assert sdk_fit.profile.channel is Channel.SDK
    assert sdk_fit.profile.surface == "codex_python_sdk"
    assert app_profile.surface == "codex_app_server"


def test_channel_filter_reports_when_surface_class_cannot_satisfy_features() -> None:
    try:
        select_profile(
            "codex",
            requires=[Feature.READABLE_GOAL],
            channel=Channel.SDK,
        )
    except UnsupportedFeature as error:
        assert "sdk codex surface" in str(error)
        assert "readable_goal" in str(error)
    else:
        raise AssertionError("expected UnsupportedFeature")


def test_select_profile_uses_required_features() -> None:
    codex = select_profile(
        "codex",
        requires=[Feature.READABLE_GOAL, Feature.STREAMING],
    )
    claude = select_profile("claude", requires=[Feature.WORKFLOW])

    assert codex.surface == "codex_app_server"
    assert claude.surface == "claude_typescript_sdk"
    assert not claude.runnable


def test_native_workflow_is_distinct_from_portable_workflow() -> None:
    conceptual = select_profile("claude", requires=[Feature.NATIVE_WORKFLOW])

    assert conceptual.surface == "claude_typescript_sdk"
    assert conceptual.runnable is False

    try:
        select_profile(
            "claude",
            requires=[Feature.NATIVE_WORKFLOW],
            runnable=True,
        )
    except UnsupportedFeature as error:
        assert "native_workflow" in str(error)
    else:
        raise AssertionError("expected UnsupportedFeature")


def test_select_profile_can_require_runnable_surface() -> None:
    codex = select_profile(
        "codex",
        requires=[Feature.READABLE_GOAL, Feature.STREAMING],
        runnable=True,
    )

    assert codex.surface == "codex_app_server"
    assert codex.runnable


def test_select_profile_can_require_codex_experimental_api() -> None:
    codex = select_profile(
        "codex",
        requires=[Feature.EXPERIMENTAL_API],
        runnable=True,
    )

    assert codex.surface == "codex_app_server"


def test_select_profile_reports_unsupported_requirements() -> None:
    try:
        select_profile("claude", requires=[Feature.MODELS])
    except UnsupportedFeature as error:
        assert "models" in str(error)
        assert "Considered:" in str(error)
    else:
        raise AssertionError("expected UnsupportedFeature")


def test_fits_for_explains_surface_candidates() -> None:
    fits = fits_for(
        "claude",
        requires=[Feature.WORKFLOW],
    )

    assert fits[0].profile.surface == "claude_typescript_sdk"
    assert fits[0].ok
    assert fits[0].profile.runnable is False
    assert [fit.profile.surface for fit in fits_for("claude", runnable=True)] == [
        "claude_python_sdk"
    ]


def test_harness_require_selects_surface_when_unset() -> None:
    harness = Harness(
        provider="codex",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    ).require(Feature.READABLE_GOAL, Feature.STREAMING)

    assert harness.surface == "codex_app_server"


def test_harness_plan_and_require_accept_channel() -> None:
    harness = Harness(
        provider="codex",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    plan = harness.plan(channel=Channel.APP_SERVER)
    required = harness.require(channel=Channel.APP_SERVER)
    fits = harness.fits(Feature.STREAMING, channel=Channel.SDK)

    assert plan.ok
    assert plan.channel is Channel.APP_SERVER
    assert plan.profile.surface == "codex_app_server"
    assert required.surface == "codex_app_server"
    assert {fit.profile.channel for fit in fits} == {Channel.SDK}


def test_harness_accepts_persistent_channel_constraint() -> None:
    harness = Harness(
        provider="codex",
        channel=Channel.APP_SERVER,
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    plan = harness.plan()
    required = harness.require()

    assert plan.ok
    assert plan.channel is Channel.APP_SERVER
    assert plan.profile.surface == "codex_app_server"
    assert required.surface == "codex_app_server"
    assert required.channel is Channel.APP_SERVER


def test_harness_persistent_channel_validates_explicit_surface() -> None:
    harness = Harness(
        provider="codex",
        surface="codex_cli",
        channel=Channel.APP_SERVER,
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    plan = harness.plan()

    assert not plan.ok
    assert plan.channel_mismatch
    try:
        harness.require()
    except UnsupportedFeature as error:
        assert "not requested channel app_server" in str(error)
    else:
        raise AssertionError("expected UnsupportedFeature")


def test_explicit_harness_surface_rejects_mismatched_channel() -> None:
    harness = Harness(
        provider="codex",
        surface="codex_cli",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    plan = harness.plan(channel=Channel.APP_SERVER)

    assert not plan.ok
    assert plan.channel_mismatch
    try:
        harness.require(channel=Channel.APP_SERVER)
    except UnsupportedFeature as error:
        assert "not requested channel app_server" in str(error)
    else:
        raise AssertionError("expected UnsupportedFeature")


def test_harness_require_uses_runnable_surfaces_by_default() -> None:
    harness = Harness(
        provider="claude",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    runnable = harness.require(Feature.WORKFLOW)
    assert runnable.surface == "claude_python_sdk"
    assert runnable.profile().support_for(Feature.WORKFLOW) is Support.EMULATED

    conceptual = harness.require(Feature.WORKFLOW, runnable=False)
    assert conceptual.surface == "claude_typescript_sdk"


def test_harness_require_validates_explicit_surface() -> None:
    harness = Harness(
        provider="codex",
        surface="codex_cli",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    assert harness.require(Feature.ONE_SHOT) is harness
    try:
        harness.require(Feature.READABLE_GOAL)
    except UnsupportedFeature as error:
        assert "readable_goal" in str(error)
    else:
        raise AssertionError("expected UnsupportedFeature")


def test_session_require_validates_explicit_surface() -> None:
    session = Session(provider="codex", surface="codex_cli", id="thread-1")

    assert session.require(Feature.STREAMING) is session
    try:
        session.require(Feature.READABLE_GOAL)
    except UnsupportedFeature as error:
        assert "readable_goal" in str(error)
    else:
        raise AssertionError("expected UnsupportedFeature")


def test_session_plan_and_require_accept_channel() -> None:
    session = Session(provider="codex", id="thread-1")

    plan = session.plan(channel=Channel.APP_SERVER)
    required = session.require(channel=Channel.APP_SERVER)
    fits = session.fits(Feature.STREAMING, channel=Channel.SDK)

    assert plan.profile.surface == "codex_app_server"
    assert required.surface == "codex_app_server"
    assert {fit.profile.channel for fit in fits} == {Channel.SDK}


def test_session_accepts_persistent_channel_constraint() -> None:
    session = Session(provider="codex", channel=Channel.APP_SERVER, id="thread-1")

    plan = session.plan()
    required = session.require()

    assert plan.ok
    assert plan.profile.surface == "codex_app_server"
    assert required.surface == "codex_app_server"
    assert required.channel is Channel.APP_SERVER


def test_session_goal_methods_guard_goal_capabilities() -> None:
    session = Session(provider="codex", surface="codex_cli", id="thread-1")

    try:
        session.get_goal_sync()
    except UnsupportedFeature as error:
        assert "readable_goal" in str(error)
    else:
        raise AssertionError("expected UnsupportedFeature")


def test_session_interrupt_guards_interrupt_capability() -> None:
    session = Session(provider="codex", surface="codex_cli", id="thread-1")

    try:
        session.interrupt_sync()
    except UnsupportedFeature as error:
        assert "interrupt" in str(error)
    else:
        raise AssertionError("expected UnsupportedFeature")


def test_session_fork_guards_fork_capability() -> None:
    session = Session(provider="codex", surface="codex_cli", id="thread-1")

    try:
        session.fork_sync()
    except UnsupportedFeature as error:
        assert "fork" in str(error)
    else:
        raise AssertionError("expected UnsupportedFeature")


def test_models_selects_surface_with_model_support() -> None:
    clear_adapters()
    harness = Harness(
        provider="codex",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    ).with_adapter(ModelAdapter())

    try:
        models = harness.models_sync()
    finally:
        clear_adapters()

    assert models[0].id == "codex_app_server"


def test_login_selects_programmatic_login_surface() -> None:
    clear_adapters()
    harness = Harness(
        provider="codex",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    ).with_adapter(LoginAdapter())

    try:
        login = harness.login_sync("device_code")
    finally:
        clear_adapters()

    assert login.surface == "codex_python_sdk"


def test_login_validates_explicit_surface() -> None:
    harness = Harness(
        provider="codex",
        surface="codex_cli",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    try:
        harness.login_sync("device_code")
    except UnsupportedFeature as error:
        assert "login" in str(error)
    else:
        raise AssertionError("expected UnsupportedFeature")


def test_run_options_guard_structured_output_surface() -> None:
    clear_adapters()
    harness = Harness(
        provider="codex",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    ).with_adapter(StructuredRunAdapter())

    try:
        run = harness.run_sync(
            "return data",
            RunOptions(output_schema=StructuredAnswer),
        )
    finally:
        clear_adapters()

    assert run.output == "codex_app_server"


def test_run_options_declare_implied_features() -> None:
    options = RunOptions(output_schema=StructuredAnswer)

    assert options.features() == (Feature.STRUCTURED_OUTPUT,)
    assert isinstance(options.features()[0], Feature)
    assert RunOptions().features() == ()
    assert RunOptions(on_event=lambda event: None).features() == (
        Feature.RUN_EVENT_CALLBACKS,
    )
    assert RunOptions(channel=Channel.APP_SERVER).features() == ()
    assert RunOptions(goal=Goal("finish safely")).features() == (Feature.GOAL,)
    assert RunOptions(inherit_goal=False).features(Goal("finish safely")) == ()
    assert RunOptions().features(Goal("finish safely")) == (Feature.GOAL,)
    assert RunOptions(provider=collaboration_provider()).features(provider="codex") == (
        Feature.COLLABORATION_MODE,
    )
    assert (
        RunOptions(provider=collaboration_provider()).features(provider="claude") == ()
    )
    assert RunOptions(permissions=Permissions(access="write")).features() == ()
    assert RunOptions(
        provider=ProviderOptions(
            claude=ClaudeOptions(permission_mode=ClaudePermissionMode.DONT_ASK)
        )
    ).features(provider="claude") == (Feature.CLAUDE_PERMISSIONS,)
    assert RunOptions(
        provider=ProviderOptions(
            codex=CodexOptions(sandbox=CodexSandbox.WORKSPACE_WRITE)
        )
    ).features(provider="codex") == (Feature.CODEX_PERMISSIONS,)


def test_session_options_declare_implied_features() -> None:
    assert SessionOptions().features() == (Feature.SESSION,)
    assert SessionOptions(channel=Channel.APP_SERVER).features() == (Feature.SESSION,)
    assert SessionOptions(goal=Goal("finish safely")).features() == (
        Feature.SESSION,
        Feature.GOAL,
    )
    assert SessionOptions().features(Goal("finish safely")) == (
        Feature.SESSION,
        Feature.GOAL,
    )
    assert SessionOptions(inherit_goal=False).features(Goal("finish safely")) == (
        Feature.SESSION,
    )
    assert SessionOptions(provider=collaboration_provider()).features(
        provider="codex"
    ) == (
        Feature.SESSION,
        Feature.COLLABORATION_MODE,
    )
    assert SessionOptions(provider=collaboration_provider()).features(
        provider="claude"
    ) == (Feature.SESSION,)
    assert SessionOptions(permissions=Permissions(access="write")).features() == (
        Feature.SESSION,
    )


def test_goal_loop_options_declare_goal_loop_feature() -> None:
    assert GoalLoopOptions(goal=Goal("finish safely")).features() == (
        Feature.GOAL_LOOP,
    )


def test_workflow_options_declare_implied_features() -> None:
    assert WorkflowOptions().features() == (Feature.WORKFLOW,)
    assert WorkflowOptions(channel=Channel.APP_SERVER).features() == (
        Feature.WORKFLOW,
    )
    assert WorkflowOptions(native=True).features() == (
        Feature.WORKFLOW,
        Feature.NATIVE_WORKFLOW,
    )
    assert WorkflowOptions().features(Goal("finish workflow")) == (
        Feature.WORKFLOW,
        Feature.GOAL,
    )
    assert WorkflowOptions(output_schema=StructuredAnswer).features() == (
        Feature.WORKFLOW,
        Feature.STRUCTURED_OUTPUT,
    )
    assert WorkflowOptions(
        run=RunOptions(output_schema=StructuredAnswer)
    ).features() == (
        Feature.WORKFLOW,
        Feature.STRUCTURED_OUTPUT,
    )
    assert WorkflowOptions(
        run=RunOptions(provider=collaboration_provider())
    ).features(provider="codex") == (
        Feature.WORKFLOW,
        Feature.COLLABORATION_MODE,
    )


def test_provider_options_declare_collaboration_mode_feature() -> None:
    assert collaboration_provider().features() == (Feature.COLLABORATION_MODE,)
    assert collaboration_provider().features(provider="codex") == (
        Feature.COLLABORATION_MODE,
    )
    assert collaboration_provider().features(provider="claude") == ()
    raw = ProviderOptions(codex={"collaboration_mode": {"mode": "plan"}})
    assert raw.features() == (Feature.COLLABORATION_MODE,)
    assert raw.features(provider="claude") == ()


def test_provider_options_declare_experimental_api_feature() -> None:
    typed = ProviderOptions(codex=CodexOptions(experimental_api=True))
    raw = ProviderOptions(codex={"experimentalApi": True})
    nested = ProviderOptions(codex={"raw": {"experimental_api": True}})

    assert typed.features(provider="codex") == (Feature.EXPERIMENTAL_API,)
    assert raw.features(provider="codex") == (Feature.EXPERIMENTAL_API,)
    assert nested.features(provider="codex") == (Feature.EXPERIMENTAL_API,)
    assert typed.features(provider="claude") == ()


def test_provider_options_declare_native_permission_features() -> None:
    codex_typed = ProviderOptions(
        codex=CodexOptions(sandbox=CodexSandbox.WORKSPACE_WRITE)
    )
    codex_raw = ProviderOptions(codex={"approvalPolicy": "on-request"})
    codex_nested = ProviderOptions(codex={"raw": {"networkAccess": True}})
    claude_typed = ProviderOptions(
        claude=ClaudeOptions(permission_mode=ClaudePermissionMode.DONT_ASK)
    )
    claude_raw = ProviderOptions(claude={"allowedTools": ("Read",)})
    claude_runtime = ProviderOptions(claude={"raw": {"canUseTool": lambda: None}})

    assert codex_typed.features(provider="codex") == (Feature.CODEX_PERMISSIONS,)
    assert codex_raw.features(provider="codex") == (Feature.CODEX_PERMISSIONS,)
    assert codex_nested.features(provider="codex") == (Feature.CODEX_PERMISSIONS,)
    assert codex_typed.features(provider="claude") == ()
    assert claude_typed.features(provider="claude") == (
        Feature.CLAUDE_PERMISSIONS,
    )
    assert claude_raw.features(provider="claude") == (Feature.CLAUDE_PERMISSIONS,)
    assert claude_runtime.features(provider="claude") == (
        Feature.CLAUDE_PERMISSIONS,
        Feature.REQUEST_CALLBACKS,
    )
    assert claude_typed.features(provider="codex") == ()


def test_run_options_experimental_api_selects_app_server() -> None:
    harness = Harness(
        provider="codex",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )
    options = RunOptions(
        provider=ProviderOptions(codex=CodexOptions(experimental_api=True))
    )

    plan = harness.plan(options)

    assert plan.features == (Feature.EXPERIMENTAL_API,)
    assert plan.profile.surface == "codex_app_server"


def test_run_options_channel_participates_in_planning() -> None:
    harness = Harness(
        provider="codex",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    plan = harness.plan(RunOptions(channel=Channel.APP_SERVER))

    assert plan.ok
    assert plan.channel is Channel.APP_SERVER
    assert plan.profile.surface == "codex_app_server"


def test_session_options_channel_participates_in_planning() -> None:
    harness = Harness(
        provider="codex",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    plan = harness.plan(SessionOptions(channel=Channel.APP_SERVER))

    assert plan.ok
    assert plan.channel is Channel.APP_SERVER
    assert plan.profile.surface == "codex_app_server"


def test_workflow_options_channel_participates_in_planning() -> None:
    harness = Harness(
        provider="codex",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    plan = harness.plan(WorkflowOptions(channel=Channel.APP_SERVER))

    assert plan.ok
    assert plan.channel is Channel.APP_SERVER
    assert plan.profile.surface == "codex_app_server"


def test_native_workflow_planning_selects_tracked_provider_native_surface() -> None:
    harness = Harness(
        provider="claude",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    plan = harness.plan(WorkflowOptions(native=True), runnable=False)

    assert plan.ok
    assert plan.features == (Feature.WORKFLOW, Feature.NATIVE_WORKFLOW)
    assert plan.profile.surface == "claude_typescript_sdk"
    assert plan.profile.support_for(Feature.NATIVE_WORKFLOW) is Support.NATIVE


def test_native_workflow_planning_rejects_runnable_python_surface() -> None:
    harness = Harness(
        provider="claude",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    with pytest.raises(UnsupportedFeature, match="native_workflow"):
        harness.plan(WorkflowOptions(native=True))


def test_goal_loop_planning_selects_codex_loop_surface() -> None:
    harness = Harness(
        provider="codex",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    plan = harness.plan(GoalLoopOptions(goal=Goal("finish safely")))

    assert plan.ok
    assert plan.features == (Feature.GOAL_LOOP,)
    assert plan.profile.support_for(Feature.GOAL_LOOP) is Support.NATIVE


def test_goal_loop_planning_selects_runnable_claude_sdk_surface() -> None:
    harness = Harness(
        provider="claude",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    plan = harness.plan(GoalLoopOptions(goal=Goal("finish safely")))

    assert plan.ok
    assert plan.profile.surface == "claude_python_sdk"
    assert plan.profile.support_for(Feature.GOAL_LOOP) is Support.NATIVE


def test_goal_loop_planning_can_still_inspect_claude_cli_surface() -> None:
    harness = Harness(
        provider="claude",
        surface="claude_cli",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    plan = harness.plan(
        GoalLoopOptions(goal=Goal("finish safely")),
        runnable=False,
    )

    assert plan.ok
    assert plan.profile.surface == "claude_cli"


def test_goal_does_not_force_native_goal_surface_for_run() -> None:
    clear_adapters()
    harness = Harness(
        provider="codex",
        surface="codex_cli",
        agent=Agent(instructions="test", goal=Goal("finish safely")),
        cwd=Path.cwd(),
    ).with_adapter(GoalRunAdapter())

    try:
        run = harness.run_sync("do it")
    finally:
        clear_adapters()

    assert run.output == "codex_cli"


def test_goal_planning_uses_goal_feature_without_forcing_mutable_goals() -> None:
    harness = Harness(
        provider="codex",
        agent=Agent(instructions="test", goal=Goal("finish safely")),
        cwd=Path.cwd(),
    )

    plan = harness.plan(RunOptions())

    assert plan.features == (Feature.GOAL,)
    assert plan.profile.surface == "codex_app_server"
    assert plan.profile.support_for(Feature.GOAL) is Support.NATIVE


def test_harness_plan_keeps_default_surface_when_it_satisfies_features() -> None:
    harness = Harness(
        provider="codex",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    plan = harness.plan(features=(Feature.GOAL,))

    assert plan.ok
    assert plan.profile.default
    assert plan.profile.surface == "codex_app_server"


def test_run_options_validate_explicit_structured_output_surface() -> None:
    harness = Harness(
        provider="codex",
        surface="codex_typescript_sdk",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    try:
        harness.run_sync("return data", RunOptions(output_schema=StructuredAnswer))
    except UnsupportedFeature as error:
        assert "structured_output" in str(error)
    else:
        raise AssertionError("expected UnsupportedFeature")


def test_session_stream_options_guard_structured_output_surface() -> None:
    session = Session(provider="codex", surface="codex_typescript_sdk", id="thread-1")

    try:
        session.stream_sync(
            "return data",
            RunOptions(output_schema=StructuredAnswer),
        )
    except UnsupportedFeature as error:
        assert "streaming" in str(error) or "structured_output" in str(error)
    else:
        raise AssertionError("expected UnsupportedFeature")


def test_session_stream_selects_surface_for_streaming_and_options() -> None:
    clear_adapters()
    register(StructuredRunAdapter())
    session = Session(provider="codex", id="thread-1")

    try:
        events = session.stream_sync(
            "return data",
            RunOptions(output_schema=StructuredAnswer),
        )
    finally:
        clear_adapters()

    assert str(events[0].kind) == "done"


class ModelAdapter:
    provider = "codex"
    surface = "codex_app_server"
    capabilities = capabilities_for("codex", "codex_app_server")

    async def models(self, harness: Harness) -> tuple[Model, ...]:
        return (Model(id=str(harness.surface)),)


class LoginAdapter:
    provider = "codex"
    surface = "codex_python_sdk"
    capabilities = capabilities_for("codex", "codex_python_sdk")

    async def login(self, harness: Harness, method: str, *, api_key: str | None = None):
        from yoke import Login

        return Login(provider="codex", surface=harness.surface, method=method)


class StructuredAnswer(BaseModel):
    value: str


class StructuredRunAdapter:
    provider = "codex"
    surface = "codex_app_server"
    capabilities = capabilities_for("codex", "codex_app_server")

    async def run(
        self,
        harness: Harness,
        prompt: str,
        options: RunOptions,
    ) -> Run:
        return Run(provider="codex", output=str(harness.surface))

    async def stream(self, session: Session, turn, options: RunOptions):
        yield Event(kind="done")


class GoalRunAdapter:
    provider = "codex"
    surface = "codex_cli"
    capabilities = capabilities_for("codex", "codex_cli")

    async def run(
        self,
        harness: Harness,
        prompt: str,
        options: RunOptions,
    ) -> Run:
        return Run(provider="codex", output=self.surface)


def test_capabilities_for_tracks_surfaces_without_built_in_adapters() -> None:
    claude_ts = capabilities_for("claude", "claude_typescript_sdk")
    codex_ts = capabilities_for("codex", "codex_typescript_sdk")

    assert claude_ts.support_for(Feature.WORKFLOW) is Support.NATIVE
    assert codex_ts.support_for(Feature.SESSION) is Support.NATIVE
    assert codex_ts.support_for(Feature.STREAMING) is Support.UNKNOWN


def test_capability_notes_explain_surface_gaps() -> None:
    codex_sdk = capabilities_for("codex", "codex_python_sdk")
    codex_sdk_fork = codex_sdk.features[Feature.FORK]
    codex_sdk_interrupt = codex_sdk.features[Feature.INTERRUPT]
    workflow = capabilities_for("claude", "claude_python_sdk").features[
        Feature.WORKFLOW
    ]
    claude_fork = capabilities_for("claude", "claude_python_sdk").features[
        Feature.FORK
    ]
    claude_cli = capabilities_for("claude", "claude_cli")
    claude_ts = capabilities_for("claude", "claude_typescript_sdk")

    assert codex_sdk.features[Feature.GOAL].support is Support.COMPILED
    assert "does not expose native" in (codex_sdk.features[Feature.GOAL].note or "")
    assert codex_sdk_fork.support is Support.NATIVE
    assert "thread_fork" in (codex_sdk_fork.note or "")
    assert codex_sdk_interrupt.support is Support.NATIVE
    assert "streamed turns" in (codex_sdk_interrupt.note or "")
    assert "TypeScript-SDK-native" in (workflow.note or "")
    assert claude_fork.support is Support.NATIVE
    assert "fork_session=True" in (claude_fork.note or "")
    assert claude_cli.support_for(Feature.FORK) is Support.NATIVE
    assert "Codex" not in (claude_cli.features[Feature.INTERRUPT].note or "")
    assert "Codex" not in (claude_ts.features[Feature.INTERRUPT].note or "")


def test_model_selection_explains_agent_model_on_unverifiable_surface() -> None:
    harness = Harness(
        "claude:sdk",
        agent=Agent(instructions="test", model="sonnet"),
        cwd=Path.cwd(),
    )

    selection = harness.model_selection()

    assert selection.model == "sonnet"
    assert str(selection.source) == "agent"
    assert selection.surface == "claude_python_sdk"
    assert selection.model_listing == "unsupported"
    assert selection.verifiable is False
    assert "does not expose model listing" in selection.note


def test_model_selection_prefers_run_option_model_on_listable_surface() -> None:
    harness = Harness(
        "codex:app",
        agent=Agent(instructions="test", model="agent-model"),
        cwd=Path.cwd(),
    )

    selection = harness.model_selection(RunOptions(model="run-model"))

    assert selection.model == "run-model"
    assert str(selection.source) == "run"
    assert selection.surface == "codex_app_server"
    assert selection.model_listing == "native"
    assert selection.verifiable is True
    assert "Call models()" in selection.note


def test_model_selection_names_session_model_source() -> None:
    harness = Harness(
        "codex:sdk",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    selection = harness.model_selection(SessionOptions(model="session-model"))

    assert selection.model == "session-model"
    assert str(selection.source) == "session"
    assert selection.surface == "codex_python_sdk"
    assert selection.verifiable is True


def test_model_selection_reports_provider_default_without_model() -> None:
    harness = Harness(
        "codex:app",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    selection = harness.model_selection()

    assert selection.model is None
    assert str(selection.source) == "provider_default"
    assert selection.verifiable is True
    assert "provider default model" in selection.note


def test_explain_combines_model_selection_and_feature_lowering() -> None:
    class Summary(BaseModel):
        value: str

    harness = Harness(
        "codex:app",
        agent=Agent(
            instructions="test",
            model="agent-model",
            goal=Goal("Finish safely."),
        ),
        cwd=Path.cwd(),
    )

    explanation = harness.explain(RunOptions(output_schema=Summary))

    assert explanation.provider == "codex"
    assert explanation.surface == "codex_app_server"
    assert explanation.channel == "app_server"
    assert explanation.ok is True
    assert explanation.model.model == "agent-model"
    assert str(explanation.model.source) == "agent"
    assert explanation.model.verifiable is True
    assert "goal" in explanation.features
    assert "structured_output" in explanation.features
    goal = explanation.report(Feature.GOAL)
    structured = explanation.report(Feature.STRUCTURED_OUTPUT)
    assert goal is not None
    assert goal.support == "native"
    assert "thread/goal" in (goal.lowering or "")
    assert structured is not None
    assert structured.support == "native"


def test_explain_shows_claude_declared_subagents_and_model_limit() -> None:
    harness = Harness(
        "claude:sdk",
        agent=Agent(
            instructions="root",
            model="sonnet",
            subagents={
                "reviewer": Agent(
                    description="Review the change.",
                    instructions="Review carefully.",
                )
            },
        ),
        cwd=Path.cwd(),
    )

    explanation = harness.explain()

    assert explanation.ok is True
    assert explanation.surface == "claude_python_sdk"
    assert explanation.model.model == "sonnet"
    assert explanation.model.verifiable is False
    assert "declared_subagents" in explanation.features
    subagents = explanation.report(Feature.DECLARED_SUBAGENTS)
    assert subagents is not None
    assert subagents.support == "native"
    assert "AgentDefinition" in (subagents.note or "")


def test_explain_can_describe_unsupported_native_workflow_request() -> None:
    harness = Harness(
        "codex:app",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    explanation = harness.explain(WorkflowOptions(native=True))

    assert explanation.ok is False
    assert explanation.surface == "codex_app_server"
    assert explanation.missing == ("native_workflow",)
    native = explanation.report(Feature.NATIVE_WORKFLOW)
    assert native is not None
    assert native.support == "unsupported"
