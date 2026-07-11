from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from yoke import (
    Agent,
    Channel,
    ClaudeOptions,
    CodexAppServerOptions,
    CodexOptions,
    Collection,
    Goal,
    Permissions,
    ProviderOptions,
    RequestPolicy,
    RunOptions,
    Skill,
    Step,
    ToolKind,
    Tools,
    Workflow,
    WorkflowLanguage,
    save,
)
from yoke.errors import YokeError


def test_collection_loads_named_agents_from_agents_folder(tmp_path: Path) -> None:
    agents = tmp_path / "agents"
    reviewer = agents / "reviewer"
    inert = agents / "inert"
    reviewer.mkdir(parents=True)
    inert.mkdir()
    (agents / "yoke.yaml").write_text(
        "default_provider: codex:app\n"
        "agents:\n"
        "  reviewer: reviewer\n"
        "  inert: inert\n"
    )
    (reviewer / "agent.yaml").write_text("description: Reviews code.\n")
    (reviewer / "instructions.md").write_text("Find concrete risks.\n")
    (inert / "agent.yaml").write_text("description: Explains without editing.\n")
    (inert / "instructions.md").write_text("Stay read-only.\n")

    collection = Collection.from_folder(agents)
    loaded = collection.agent("reviewer")

    assert collection.root == agents
    assert collection.default_provider == "codex:app"
    assert collection.names() == ("inert", "reviewer")
    assert loaded.description == "Reviews code."
    assert loaded.instructions == "Find concrete risks."


def test_collection_rejects_non_string_agent_paths(tmp_path: Path) -> None:
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "yoke.yaml").write_text(
        "agents:\n"
        "  reviewer:\n"
        "    path: reviewer\n"
    )

    with pytest.raises(ValueError) as error:
        Collection.from_folder(agents)

    assert "must map to a path string" in str(error.value)


def test_agent_save_round_trips_yoke_folder(tmp_path: Path) -> None:
    agent = Agent(
        description="Maintains bundle loading.",
        instructions="Be careful with provider boundaries.",
        model="gpt-5.4",
        goal=Goal("Finish safely.", token_budget=10_000),
        tools=Tools(read=True, write=True, shell=True),
        permissions=Permissions(network=True),
        skills=(
            Skill.from_text(
                "Use primary docs.",
                name="research",
                description="Research official docs.",
            ),
        ),
        subagents={
            "reviewer": Agent(
                description="Reviews code.",
                instructions="Find correctness bugs.",
            )
        },
        workflows={
            "ship": Workflow(
                name="ship",
                description="Review then finish.",
                steps=(
                    Step(
                        name="review",
                        agent="reviewer",
                        prompt="Review {input}",
                    ),
                ),
            )
        },
    )

    written = agent.save(tmp_path / "maintainer")
    loaded = Agent.from_folder(tmp_path / "maintainer")

    assert tmp_path / "maintainer" / "agent.yaml" in written
    assert (
        tmp_path / "maintainer" / "workflows" / "ship" / "review.md"
    ) in written
    assert loaded.description == "Maintains bundle loading."
    assert loaded.instructions == "Be careful with provider boundaries."
    assert loaded.model == "gpt-5.4"
    assert loaded.goal == Goal("Finish safely.", token_budget=10_000)
    assert loaded.tools.write is True
    assert loaded.tools.shell is True
    assert loaded.permissions.network is True
    assert loaded.skills[0].name == "research"
    assert loaded.skills[0].instructions == "Use primary docs."
    assert loaded.subagents["reviewer"].instructions == "Find correctness bugs."
    assert loaded.workflows["ship"].steps[0].agent == "reviewer"


def test_folder_source_round_trips_into_provider_bundles(tmp_path: Path) -> None:
    agent = Agent(
        description="Maintains release flow.",
        instructions="Coordinate carefully.",
        goal=Goal("Ship the release safely.", token_budget=200_000),
        tools=Tools(read=True, write=True, shell=True, agent=True),
        permissions=Permissions(access="write", approval="auto"),
        options={"codex_agents": {"max_threads": 3, "max_depth": 1}},
        skills=(
            Skill.from_text(
                "Check the release checklist.",
                name="release-check",
                description="Release checklist.",
            ),
        ),
        subagents={
            "reviewer": Agent(
                description="Reviews release patches.",
                instructions="Find correctness and release risks.",
                model="gpt-5.4-mini",
                permissions=Permissions(access="read"),
                options={
                    "claude_name": "release-reviewer",
                    "codex_name": "release-reviewer",
                    "nickname_candidates": ["reviewer", "relrev"],
                },
                skills=(
                    Skill.from_text(
                        "Inspect changelog and package metadata.",
                        name="package-audit",
                    ),
                ),
            )
        },
        workflows={
            "release": Workflow(
                name="release",
                description="Draft then review release notes.",
                steps=(
                    Step(name="draft", prompt="Draft notes for {input}."),
                    Step(
                        name="review",
                        agent="reviewer",
                        depends_on=("draft",),
                        prompt="Review {draft}.",
                        run=RunOptions(
                            channel=Channel.APP_SERVER,
                            goal=Goal("Review without broad edits."),
                        ),
                    ),
                ),
            ),
            "script-audit": Workflow.from_script(
                "script-audit",
                "return await agent('Audit package files.')",
                description="Provider-native package audit.",
            ),
        },
    )

    agent.save(tmp_path / "agent")
    loaded = Agent.from_folder(tmp_path / "agent")
    codex = loaded.bundle(provider="codex")
    claude = loaded.bundle(provider="claude")

    assert loaded.goal == Goal("Ship the release safely.", token_budget=200_000)
    assert loaded.options == {"codex_agents": {"max_threads": 3, "max_depth": 1}}
    assert loaded.skills[0].name == "release-check"
    assert loaded.skills[0].instructions == "Check the release checklist."
    assert loaded.skills[0].path == tmp_path / "agent" / "skills" / "release-check"
    assert loaded.subagents["reviewer"].options["claude_name"] == "release-reviewer"
    assert loaded.workflows["release"].steps[1].run == {
        "channel": "app_server",
        "goal": {"objective": "Review without broad edits."},
    }
    assert loaded.workflows["script-audit"].script == (
        "return await agent('Audit package files.')"
    )

    codex_paths = [artifact.path.as_posix() for artifact in codex.artifacts]
    assert codex_paths == [
        ".codex/config.toml",
        ".codex/agents/release-reviewer.toml",
        ".agents/skills/release-check/SKILL.md",
        ".agents/skills/package-audit/SKILL.md",
    ]
    assert "max_threads = 3" in codex.artifacts[0].text
    assert 'nickname_candidates = ["reviewer", "relrev"]' in codex.artifacts[1].text
    assert "Check the release checklist." in codex.artifacts[2].text
    assert "Inspect changelog and package metadata." in codex.artifacts[3].text

    claude_paths = [artifact.path.as_posix() for artifact in claude.artifacts]
    assert claude_paths == [
        ".claude/agents/release-reviewer.md",
        ".claude/skills/release-check/SKILL.md",
        ".claude/skills/package-audit/SKILL.md",
        ".claude/workflows/script-audit.js",
    ]
    assert "name: release-reviewer" in claude.artifacts[0].text
    assert "Check the release checklist." in claude.artifacts[1].text
    assert "Inspect changelog and package metadata." in claude.artifacts[2].text
    assert "Audit package files." in claude.artifacts[3].text


def test_folder_goals_can_be_scalar_or_mapping(tmp_path: Path) -> None:
    simple = Agent(instructions="Coordinate.", goal=Goal("Finish safely."))

    simple.save(tmp_path / "simple")
    simple_config = yaml.safe_load((tmp_path / "simple" / "agent.yaml").read_text())

    assert simple_config["goal"] == "Finish safely."
    assert Agent.from_folder(tmp_path / "simple").goal == Goal("Finish safely.")

    rich = Agent(
        instructions="Coordinate.",
        goal=Goal("Finish safely.", token_budget=10_000),
    )

    rich.save(tmp_path / "rich")
    rich_config = yaml.safe_load((tmp_path / "rich" / "agent.yaml").read_text())

    assert rich_config["goal"] == {
        "objective": "Finish safely.",
        "token_budget": 10_000,
    }
    assert Agent.from_folder(tmp_path / "rich").goal == Goal(
        "Finish safely.",
        token_budget=10_000,
    )


def test_save_function_matches_agent_method(tmp_path: Path) -> None:
    agent = Agent(instructions="Coordinate.")

    written = save(agent, tmp_path / "agent")

    assert written == (
        tmp_path / "agent" / "agent.yaml",
        tmp_path / "agent" / "instructions.md",
    )


def test_agent_save_refuses_overwrite(tmp_path: Path) -> None:
    agent = Agent(instructions="Coordinate.")

    agent.save(tmp_path / "agent")

    with pytest.raises(FileExistsError):
        agent.save(tmp_path / "agent")
    agent.save(tmp_path / "agent", overwrite=True)


def test_agent_save_copies_path_backed_skill(tmp_path: Path) -> None:
    source = tmp_path / "source-skill"
    source.mkdir()
    (source / "SKILL.md").write_text("---\nname: source\n---\nRead the source.\n")
    agent = Agent(instructions="Coordinate.", skills=(Skill.from_path(source),))

    agent.save(tmp_path / "agent")
    loaded = Agent.from_folder(tmp_path / "agent")

    assert loaded.skills[0].name == "source"
    assert loaded.skills[0].instructions == "Read the source."


def test_folder_workflows_can_be_markdown_step_directories(tmp_path: Path) -> None:
    root = tmp_path / "agent"
    (root / "workflows" / "review").mkdir(parents=True)
    (root / "agent.yaml").write_text("description: Maintains code.\n")
    (root / "instructions.md").write_text("Be careful.\n")
    (root / "workflows" / "review" / "workflow.yaml").write_text(
        "description: Draft then review.\n"
    )
    (root / "workflows" / "review" / "draft.md").write_text(
        "Draft release notes for {input}.\n"
    )
    (root / "workflows" / "review" / "review.md").write_text(
        "---\n"
        "agent: reviewer\n"
        "depends_on: draft\n"
        "output_schema:\n"
        "  type: object\n"
        "run:\n"
        "  channel: app_server\n"
        "  goal:\n"
        "    objective: Verify the draft safely.\n"
        "  permissions:\n"
        "    access: read\n"
        "---\n"
        "Review the draft:\n\n{draft}\n"
    )
    (root / "subagents" / "reviewer").mkdir(parents=True)
    (root / "subagents" / "reviewer" / "agent.yaml").write_text(
        "description: Reviews drafts.\n"
    )
    (root / "subagents" / "reviewer" / "instructions.md").write_text(
        "Find risks.\n"
    )

    agent = Agent.from_folder(root)
    workflow = agent.workflows["review"]

    assert workflow.description == "Draft then review."
    assert workflow.steps[0].name == "draft"
    assert workflow.steps[0].agent == "main"
    assert workflow.steps[0].prompt == "Draft release notes for {input}."
    assert workflow.steps[1].name == "review"
    assert workflow.steps[1].agent == "reviewer"
    assert workflow.steps[1].depends_on == ("draft",)
    assert workflow.steps[1].output_schema == {"type": "object"}
    assert workflow.steps[1].run == {
        "channel": "app_server",
        "goal": {"objective": "Verify the draft safely."},
        "permissions": {"access": "read"},
    }


def test_folder_workflow_names_are_path_derived(tmp_path: Path) -> None:
    root = tmp_path / "agent"
    workflow_dir = root / "workflows" / "review"
    workflow_dir.mkdir(parents=True)
    (root / "agent.yaml").write_text("description: Maintains code.\n")
    (workflow_dir / "workflow.yaml").write_text("name: renamed\n")
    (workflow_dir / "draft.md").write_text("Draft {input}.\n")

    with pytest.raises(ValueError) as error:
        Agent.from_folder(root)

    assert "cannot rename workflow 'review' to 'renamed'" in str(error.value)


def test_folder_workflow_step_names_are_path_derived(tmp_path: Path) -> None:
    root = tmp_path / "agent"
    workflow_dir = root / "workflows" / "review"
    workflow_dir.mkdir(parents=True)
    (root / "agent.yaml").write_text("description: Maintains code.\n")
    (workflow_dir / "draft.md").write_text(
        "---\nname: renamed\n---\nDraft {input}.\n"
    )

    with pytest.raises(ValueError) as error:
        Agent.from_folder(root)

    assert "cannot rename step 'draft' to 'renamed'" in str(error.value)


def test_folder_workflows_can_be_script_directories(tmp_path: Path) -> None:
    root = tmp_path / "agent"
    (root / "workflows" / "audit-routes").mkdir(parents=True)
    (root / "agent.yaml").write_text("description: Maintains code.\n")
    (root / "instructions.md").write_text("Be careful.\n")
    (root / "workflows" / "audit-routes" / "workflow.yaml").write_text(
        "description: Audit routes with Claude workflow runtime.\n"
        "language: javascript\n"
    )
    (root / "workflows" / "audit-routes" / "script.js").write_text(
        "const found = await agent('List route files.')\n"
        "return found\n"
    )

    agent = Agent.from_folder(root)
    workflow = agent.workflows["audit-routes"]

    assert workflow.description == "Audit routes with Claude workflow runtime."
    assert workflow.language is WorkflowLanguage.JAVASCRIPT
    assert workflow.script == (
        "const found = await agent('List route files.')\nreturn found"
    )
    assert workflow.steps == ()


def test_folder_workflows_can_be_python_program_directories(tmp_path: Path) -> None:
    root = tmp_path / "agent"
    workflow_dir = root / "workflows" / "audit-routes"
    workflow_dir.mkdir(parents=True)
    (root / "agent.yaml").write_text("description: Maintains code.\n")
    (root / "instructions.md").write_text("Be careful.\n")
    (workflow_dir / "workflow.yaml").write_text(
        "description: Audit routes with a Python workflow program.\n"
        "args:\n"
        "  scope: routes\n"
    )
    (workflow_dir / "workflow.py").write_text(
        "async def main(ctx):\n"
        "    return f'audit {ctx.args}'\n"
    )

    agent = Agent.from_folder(root)
    workflow = agent.workflows["audit-routes"]

    assert workflow.description == "Audit routes with a Python workflow program."
    assert workflow.language is WorkflowLanguage.PYTHON
    assert workflow.program_path == workflow_dir / "workflow.py"
    assert workflow.args == {"scope": "routes"}
    assert workflow.steps == ()


def test_agent_save_writes_script_workflow_directory(tmp_path: Path) -> None:
    agent = Agent(
        instructions="Coordinate.",
        workflows={
            "audit-routes": Workflow(
                name="audit-routes",
                description="Audit routes.",
                script="return await agent('Audit routes.')\n",
            )
        },
    )

    agent.save(tmp_path / "agent")

    workflow_yaml = tmp_path / "agent" / "workflows" / "audit-routes" / "workflow.yaml"
    script = tmp_path / "agent" / "workflows" / "audit-routes" / "script.js"
    loaded = Agent.from_folder(tmp_path / "agent")

    assert yaml.safe_load(workflow_yaml.read_text()) == {
        "description": "Audit routes.",
        "language": "javascript",
    }
    assert script.read_text() == "return await agent('Audit routes.')\n"
    assert loaded.workflows["audit-routes"].script == (
        "return await agent('Audit routes.')"
    )


def test_agent_save_writes_python_program_workflow_directory(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.py"
    source.write_text("async def main(ctx):\n    return 'ok'\n")
    agent = Agent(
        instructions="Coordinate.",
        workflows={
            "audit-routes": Workflow.from_program(
                "audit-routes",
                source,
                description="Audit routes.",
                args={"scope": "routes"},
            )
        },
    )

    agent.save(tmp_path / "agent")

    workflow_yaml = tmp_path / "agent" / "workflows" / "audit-routes" / "workflow.yaml"
    program = tmp_path / "agent" / "workflows" / "audit-routes" / "workflow.py"
    loaded = Agent.from_folder(tmp_path / "agent")

    assert yaml.safe_load(workflow_yaml.read_text()) == {
        "description": "Audit routes.",
        "language": "python",
        "args": {"scope": "routes"},
    }
    assert program.read_text() == "async def main(ctx):\n    return 'ok'\n"
    assert loaded.workflows["audit-routes"].program_path == program


def test_agent_save_round_trips_native_workflow_reference(tmp_path: Path) -> None:
    agent = Agent(
        instructions="Coordinate.",
        workflows={
            "nightly-audit": Workflow.from_name(
                "nightly-audit",
                args={"scope": "routes"},
                resume_from_run_id="run-123",
            )
        },
    )

    agent.save(tmp_path / "agent")

    workflow_yaml = tmp_path / "agent" / "workflows" / "nightly-audit" / "workflow.yaml"
    loaded = Agent.from_folder(tmp_path / "agent").workflows["nightly-audit"]

    assert yaml.safe_load(workflow_yaml.read_text()) == {
        "native_name": "nightly-audit",
        "args": {"scope": "routes"},
        "resume_from_run_id": "run-123",
        "language": "javascript",
    }
    assert loaded.native is True
    assert loaded.native_input() == {
        "name": "nightly-audit",
        "args": {"scope": "routes"},
        "resumeFromRunId": "run-123",
    }


def test_folder_workflow_step_run_options_write_channel(tmp_path: Path) -> None:
    agent = Agent(
        instructions="Coordinate.",
        workflows={
            "review": Workflow(
                name="review",
                steps=(
                    Step(
                        name="review",
                        prompt="Review {input}.",
                        run=RunOptions(channel=Channel.APP_SERVER),
                    ),
                ),
            )
        },
    )

    agent.save(tmp_path / "agent")

    review = tmp_path / "agent" / "workflows" / "review" / "review.md"
    frontmatter, body = review.read_text().split("---", 2)[1:]
    data = yaml.safe_load(frontmatter)

    assert data["run"]["channel"] == "app_server"
    assert body.strip() == "Review {input}."


def test_agent_save_writes_workflows_as_markdown_step_directories(
    tmp_path: Path,
) -> None:
    agent = Agent(
        instructions="Coordinate.",
        workflows={
            "review": Workflow(
                name="review",
                description="Draft then review.",
                steps=(
                    Step(name="draft", prompt="Draft {input}."),
                    Step(
                        name="review",
                        agent="reviewer",
                        depends_on=("draft",),
                        prompt="Review {draft}.",
                        output_schema={"type": "object"},
                        run=RunOptions(
                            goal=Goal("Verify the draft safely."),
                            permissions=Permissions(access="read"),
                        ),
                    ),
                ),
            )
        },
        subagents={
            "reviewer": Agent(description="Reviews.", instructions="Find bugs.")
        },
    )

    agent.save(tmp_path / "agent")

    workflow_yaml = tmp_path / "agent" / "workflows" / "review" / "workflow.yaml"
    draft = tmp_path / "agent" / "workflows" / "review" / "draft.md"
    review = tmp_path / "agent" / "workflows" / "review" / "review.md"
    loaded = Agent.from_folder(tmp_path / "agent")

    assert yaml.safe_load(workflow_yaml.read_text()) == {
        "description": "Draft then review."
    }
    assert draft.read_text().strip() == "Draft {input}."
    frontmatter, body = review.read_text().split("---", 2)[1:]
    assert yaml.safe_load(frontmatter) == {
        "agent": "reviewer",
        "depends_on": ["draft"],
        "output_schema": {"type": "object"},
        "run": {
            "goal": {"objective": "Verify the draft safely."},
            "permissions": {"access": "read"},
        },
    }
    assert body.strip() == "Review {draft}."
    assert loaded.workflows["review"].steps[1].agent == "reviewer"
    assert loaded.workflows["review"].steps[1].run == {
        "goal": {"objective": "Verify the draft safely."},
        "permissions": {"access": "read"},
    }


def test_agent_save_rejects_workflow_name_that_differs_from_path_key(
    tmp_path: Path,
) -> None:
    agent = Agent(
        instructions="Coordinate.",
        workflows={
            "review": Workflow(
                name="renamed",
                steps=(Step(name="draft", prompt="Draft {input}."),),
            )
        },
    )

    with pytest.raises(YokeError) as error:
        agent.save(tmp_path / "agent")

    assert "workflow mapping key 'review' must match Workflow.name 'renamed'" in str(
        error.value
    )


def test_agent_save_rejects_step_names_that_cannot_round_trip_as_paths(
    tmp_path: Path,
) -> None:
    agent = Agent(
        instructions="Coordinate.",
        workflows={
            "review": Workflow(
                name="review",
                steps=(Step(name="draft notes", prompt="Draft {input}."),),
            )
        },
    )

    with pytest.raises(YokeError) as error:
        agent.save(tmp_path / "agent")

    assert "workflow step name 'draft notes' cannot be serialized" in str(error.value)


def test_agent_save_rejects_runtime_only_step_options(tmp_path: Path) -> None:
    def handler(event, default):
        return None

    agent = Agent(
        instructions="Coordinate.",
        workflows={
            "review": Workflow(
                name="review",
                steps=(
                    Step(
                        name="review",
                        prompt="Review {input}.",
                        run=RunOptions(
                            provider=ProviderOptions(
                                codex=CodexOptions(
                                    app_server=CodexAppServerOptions(
                                        request_handler=handler
                                    )
                                )
                            )
                        ),
                    ),
                ),
            )
        },
    )

    with pytest.raises(YokeError) as error:
        agent.save(tmp_path / "agent")

    assert "runtime-only SDK options" in str(error.value)
    assert "workflows.review.steps.review.run.provider.codex.app_server" in str(
        error.value
    )
    assert not (tmp_path / "agent" / "agent.yaml").exists()


def test_agent_save_allows_serializable_request_policy(tmp_path: Path) -> None:
    agent = Agent(
        instructions="Coordinate.",
        workflows={
            "review": Workflow(
                name="review",
                steps=(
                    Step(
                        name="review",
                        prompt="Review {input}.",
                        run=RunOptions(
                            provider=ProviderOptions(
                                codex=CodexOptions(
                                    app_server=CodexAppServerOptions(
                                        policy=RequestPolicy.allow_tools(
                                            ToolKind.SHELL
                                        )
                                    )
                                ),
                                claude=ClaudeOptions(
                                    policy=RequestPolicy.deny_tools(
                                        ToolKind.SHELL,
                                        message="No shell.",
                                    )
                                ),
                            )
                        ),
                    ),
                ),
            )
        },
    )

    agent.save(tmp_path / "agent")

    review = tmp_path / "agent" / "workflows" / "review" / "review.md"
    text = review.read_text()
    assert "policy:" in text
    assert "tool_kinds:" in text
    assert "request_handler" not in text


def test_agent_save_rejects_callable_raw_step_options(tmp_path: Path) -> None:
    def callback():
        return None

    agent = Agent(
        instructions="Coordinate.",
        workflows={
            "review": Workflow(
                name="review",
                steps=(
                    Step(
                        name="review",
                        prompt="Review {input}.",
                        run=RunOptions(
                            provider=ProviderOptions(
                                codex=CodexOptions(raw={"callback": callback})
                            )
                        ),
                    ),
                ),
            )
        },
    )

    with pytest.raises(YokeError) as error:
        agent.save(tmp_path / "agent")

    assert "workflows.review.steps.review.run.provider.codex.raw.callback" in str(
        error.value
    )
    assert not (tmp_path / "agent" / "agent.yaml").exists()


def test_agent_save_can_explicitly_omit_runtime_only_step_options(
    tmp_path: Path,
) -> None:
    def handler(event, default):
        return None

    agent = Agent(
        instructions="Coordinate.",
        workflows={
            "review": Workflow(
                name="review",
                steps=(
                    Step(
                        name="review",
                        prompt="Review {input}.",
                        run=RunOptions(
                            provider=ProviderOptions(
                                codex=CodexOptions(
                                    app_server=CodexAppServerOptions(
                                        request_handler=handler,
                                        opt_out_notification_methods=("warning",),
                                    )
                                )
                            )
                        ),
                    ),
                ),
            )
        },
    )

    agent.save(tmp_path / "agent", allow_runtime_only=True)

    review = tmp_path / "agent" / "workflows" / "review" / "review.md"
    frontmatter, body = review.read_text().split("---", 2)[1:]
    data = yaml.safe_load(frontmatter)

    assert "request_handler" not in review.read_text()
    assert data["run"]["provider"]["codex"]["app_server"] == {
        "opt_out_notification_methods": ["warning"]
    }
    assert body.strip() == "Review {input}."
