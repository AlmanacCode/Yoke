from __future__ import annotations

from pathlib import Path

import pytest

from yoke import (
    Access,
    Agent,
    Artifact,
    ArtifactComponent,
    Bundle,
    CodexAgentSettings,
    Effort,
    Permissions,
    Skill,
    Tools,
    Workflow,
    bundle,
)
from yoke.errors import YokeError


def test_codex_bundle_compiles_agents_and_inline_skills() -> None:
    agent = Agent(
        instructions="Coordinate work.",
        skills=(
            Skill.from_text(
                "Use primary sources.",
                name="docs-research",
                description="Research official docs.",
            ),
        ),
        subagents={
            "reviewer": Agent(
                description="Review code.",
                instructions="Find correctness issues.",
                model="gpt-5.4-mini",
                effort=Effort.HIGH,
                permissions=Permissions(access=Access.READ),
                skills=(Skill.from_text("Check APIs.", name="api-check"),),
            )
        },
    )

    compiled = bundle(agent, provider="codex", surface="codex_cli")

    assert compiled.provider == "codex"
    assert compiled.surface == "codex_cli"
    assert [artifact.kind for artifact in compiled.artifacts] == [
        "codex_agent",
        "codex_skill",
        "codex_skill",
    ]
    assert [artifact.component for artifact in compiled.artifacts] == [
        ArtifactComponent.AGENT,
        ArtifactComponent.SKILL,
        ArtifactComponent.SKILL,
    ]
    assert [str(artifact.feature) for artifact in compiled.artifacts] == [
        "filesystem_agent",
        "skills",
        "skills",
    ]
    assert [str(feature) for feature in compiled.features] == [
        "filesystem_agent",
        "skills",
    ]
    assert compiled.artifacts[0].path.as_posix() == ".codex/agents/reviewer.toml"
    assert compiled.artifacts[0].lowering == (
        "Yoke subagent compiled to Codex custom-agent TOML at "
        ".codex/agents/reviewer.toml."
    )
    assert 'name = "reviewer"' in compiled.artifacts[0].text
    assert 'model_reasoning_effort = "high"' in compiled.artifacts[0].text
    assert (
        compiled.artifacts[1].path.as_posix()
        == ".agents/skills/docs-research/SKILL.md"
    )
    assert compiled.artifacts[1].lowering == (
        "Yoke skill with loaded instructions compiled to Codex filesystem skill. Path: "
        ".agents/skills/docs-research/SKILL.md."
    )
    assert "name: docs-research" in compiled.artifacts[1].text
    assert "description: Research official docs." in compiled.artifacts[1].text
    assert "Use primary sources." in compiled.artifacts[1].text
    assert (
        compiled.artifacts[2].path.as_posix()
        == ".agents/skills/api-check/SKILL.md"
    )
    assert "name: api-check" in compiled.artifacts[2].text
    assert "Check APIs." in compiled.artifacts[2].text


def test_codex_bundle_compiles_project_agent_settings() -> None:
    agent = Agent(
        instructions="Coordinate work.",
        options={
            "codex_agents": CodexAgentSettings(
                max_threads=8,
                max_depth=1,
                job_max_runtime_seconds=900,
            )
        },
    )

    compiled = bundle(agent, provider="codex", surface="codex_cli")

    assert [artifact.kind for artifact in compiled.artifacts] == [
        "codex_agents_config"
    ]
    artifact = compiled.artifacts[0]
    assert artifact.component is ArtifactComponent.CONFIG
    assert artifact.feature == "filesystem_agent"
    assert artifact.path.as_posix() == ".codex/config.toml"
    assert artifact.lowering == (
        "Yoke Codex agent settings compiled to .codex/config.toml [agents]."
    )
    assert artifact.text == (
        "[agents]\n"
        "max_threads = 8\n"
        "max_depth = 1\n"
        "job_max_runtime_seconds = 900\n"
    )


def test_claude_bundle_compiles_agents_and_inline_skills() -> None:
    agent = Agent(
        instructions="Coordinate work.",
        skills=(Skill.from_text("Follow release process.", name="release"),),
        subagents={
            "researcher": Agent(
                description="Research code paths.",
                instructions="Read first, then summarize.",
                model="sonnet",
                tools=Tools(read=True, shell=True),
                skills=(Skill.from_text("Inspect APIs.", name="api-research"),),
            )
        },
    )

    compiled = agent.bundle(provider="claude", surface="claude_python_sdk")

    assert compiled.provider == "claude"
    assert compiled.surface == "claude_python_sdk"
    assert [artifact.kind for artifact in compiled.artifacts] == [
        "claude_agent",
        "claude_skill",
        "claude_skill",
    ]
    assert [artifact.component for artifact in compiled.artifacts] == [
        ArtifactComponent.AGENT,
        ArtifactComponent.SKILL,
        ArtifactComponent.SKILL,
    ]
    assert [str(artifact.feature) for artifact in compiled.artifacts] == [
        "declared_subagents",
        "skills",
        "skills",
    ]
    assert compiled.artifacts[0].path.as_posix() == ".claude/agents/researcher.md"
    assert compiled.artifacts[0].lowering == (
        "Yoke subagent compiled to Claude custom subagent markdown at "
        ".claude/agents/researcher.md."
    )
    assert "name: researcher" in compiled.artifacts[0].text
    assert "description: Research code paths." in compiled.artifacts[0].text
    assert "model: sonnet" in compiled.artifacts[0].text
    assert "- Bash" in compiled.artifacts[0].text
    assert "- api-research" in compiled.artifacts[0].text
    assert "Read first, then summarize." in compiled.artifacts[0].text
    assert compiled.artifacts[1].path.as_posix() == ".claude/skills/release/SKILL.md"
    assert compiled.artifacts[1].lowering == (
        "Yoke skill with loaded instructions compiled to Claude filesystem "
        "skill. Path: "
        ".claude/skills/release/SKILL.md."
    )
    assert "name: release" in compiled.artifacts[1].text
    assert "Follow release process." in compiled.artifacts[1].text
    assert (
        compiled.artifacts[2].path.as_posix()
        == ".claude/skills/api-research/SKILL.md"
    )
    assert "name: api-research" in compiled.artifacts[2].text
    assert "Inspect APIs." in compiled.artifacts[2].text


def test_bundle_dedupes_identical_recursive_inline_skills() -> None:
    shared = Skill.from_text("Use the shared guide.", name="shared")
    agent = Agent(
        instructions="Coordinate work.",
        skills=(shared,),
        subagents={
            "researcher": Agent(
                description="Research.",
                instructions="Research.",
                skills=(shared,),
            )
        },
    )

    compiled = agent.bundle(provider="claude")

    assert [artifact.path.as_posix() for artifact in compiled.artifacts] == [
        ".claude/agents/researcher.md",
        ".claude/skills/shared/SKILL.md",
    ]


def test_bundle_rejects_conflicting_recursive_inline_skill_paths() -> None:
    agent = Agent(
        instructions="Coordinate work.",
        skills=(Skill.from_text("Root instructions.", name="shared"),),
        subagents={
            "researcher": Agent(
                description="Research.",
                instructions="Research.",
                skills=(Skill.from_text("Child instructions.", name="shared"),),
            )
        },
    )

    with pytest.raises(YokeError, match="same provider path"):
        agent.bundle(provider="claude")


def test_bundle_rejects_duplicate_artifact_paths() -> None:
    with pytest.raises(YokeError, match="same path"):
        Bundle(
            provider="claude",
            artifacts=(
                Artifact(path=Path(".claude/skills/a/SKILL.md"), text="one", kind="x"),
                Artifact(path=Path(".claude/skills/a/SKILL.md"), text="two", kind="x"),
            ),
        )


def test_claude_bundle_compiles_script_workflows() -> None:
    agent = Agent(
        instructions="Coordinate work.",
        workflows={
            "audit-routes": Workflow(
                name="audit-routes",
                description="Audit routes.",
                script="return await agent('Audit routes.')",
            )
        },
    )

    compiled = agent.bundle(provider="claude", surface="claude_python_sdk")

    assert [artifact.kind for artifact in compiled.artifacts] == ["claude_workflow"]
    artifact = compiled.artifacts[0]
    assert artifact.component is ArtifactComponent.WORKFLOW
    assert artifact.feature == "native_workflow"
    assert artifact.path.as_posix() == ".claude/workflows/audit-routes.js"
    assert artifact.lowering == (
        "Yoke script workflow compiled to Claude dynamic workflow script at "
        ".claude/workflows/audit-routes.js."
    )
    assert 'name: "audit-routes"' in artifact.text
    assert 'description: "Audit routes."' in artifact.text
    assert "return await agent('Audit routes.')" in artifact.text


def test_claude_bundle_preserves_workflow_meta_when_script_defines_it() -> None:
    agent = Agent(
        instructions="Coordinate work.",
        workflows={
            "audit-routes": Workflow(
                name="audit-routes",
                script=(
                    "export const meta = { name: 'custom' }\n"
                    "return await agent('Audit routes.')"
                ),
            )
        },
    )

    compiled = bundle(agent, provider="claude")

    assert compiled.artifacts[0].text == (
        "export const meta = { name: 'custom' }\n"
        "return await agent('Audit routes.')\n"
    )


def test_bundle_write_is_explicit_and_refuses_overwrite(tmp_path: Path) -> None:
    compiled = bundle(
        Agent(instructions="test"),
        provider="codex",
        surface="codex_cli",
    ).model_copy(
        update={
            "artifacts": (
                Artifact(path=Path("out/file.txt"), text="hello", kind="test"),
            )
        }
    )

    written = compiled.write(tmp_path)

    assert written == (tmp_path / "out/file.txt",)
    assert (tmp_path / "out/file.txt").read_text() == "hello"
    with pytest.raises(FileExistsError):
        compiled.write(tmp_path)
    compiled.write(tmp_path, overwrite=True)
