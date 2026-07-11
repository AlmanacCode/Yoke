"""Provider-native filesystem artifacts compiled from Yoke agents."""

from __future__ import annotations

import json
import re
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import model_validator

from yoke.capabilities import Feature
from yoke.errors import YokeError
from yoke.models import (
    Agent,
    Provider,
    Skill,
    Surface,
    Tools,
    Workflow,
    YokeModel,
)
from yoke.providers.codex_agents import (
    codex_agent_files,
    codex_agent_settings,
    codex_agent_settings_toml,
)


class ArtifactComponent(StrEnum):
    """Provider artifact component kind."""

    FILE = "file"
    CONFIG = "config"
    AGENT = "agent"
    SKILL = "skill"
    WORKFLOW = "workflow"
    PLUGIN = "plugin"


class Artifact(YokeModel):
    """One file Yoke can write explicitly for a provider surface."""

    path: Path
    text: str
    kind: str
    component: ArtifactComponent = ArtifactComponent.FILE
    feature: Feature | None = None
    description: str | None = None
    lowering: str | None = None


class Bundle(YokeModel):
    """Provider-native files compiled from a Yoke agent."""

    provider: Provider
    surface: Surface | str | None = None
    artifacts: tuple[Artifact, ...] = ()

    @model_validator(mode="after")
    def reject_duplicate_artifact_paths(self) -> Bundle:
        """Reject bundles that would write multiple artifacts to one path."""

        seen: set[str] = set()
        for artifact in self.artifacts:
            path = artifact.path.as_posix()
            if path in seen:
                raise YokeError(f"bundle artifacts compile to the same path: {path}")
            seen.add(path)
        return self

    @property
    def features(self) -> tuple[Feature, ...]:
        """Return Yoke features represented by this bundle."""

        features: list[Feature] = []
        for artifact in self.artifacts:
            if artifact.feature is not None and artifact.feature not in features:
                features.append(artifact.feature)
        return tuple(features)

    def write(self, root: str | Path, *, overwrite: bool = False) -> tuple[Path, ...]:
        """Write the bundle under `root` and return written paths."""

        target = Path(root)
        written: list[Path] = []
        for artifact in self.artifacts:
            path = target / artifact.path
            if path.exists() and not overwrite:
                raise FileExistsError(f"{path} already exists")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(artifact.text)
            written.append(path)
        return tuple(written)


def bundle(
    agent: Agent,
    *,
    provider: Provider | str,
    surface: Surface | str | None = None,
) -> Bundle:
    """Compile a Yoke agent into provider-native files."""

    provider_value = Provider(provider)
    surface_value = normalize_surface(surface)
    if provider_value is Provider.CODEX:
        return Bundle(
            provider=provider_value,
            surface=surface_value,
            artifacts=codex_artifacts(agent),
        )
    if provider_value is Provider.CLAUDE:
        return Bundle(
            provider=provider_value,
            surface=surface_value,
            artifacts=claude_artifacts(agent),
        )
    return Bundle(provider=provider_value, surface=surface_value)


def normalize_surface(value: Surface | str | None) -> Surface | str | None:
    if isinstance(value, str):
        try:
            return Surface(value)
        except ValueError:
            return value
    return value


def codex_artifacts(agent: Agent) -> tuple[Artifact, ...]:
    artifacts: list[Artifact] = []
    settings = codex_agent_settings(agent)
    if settings is not None:
        artifacts.append(
            Artifact(
                path=Path(".codex/config.toml"),
                text=codex_agent_settings_toml(settings),
                kind="codex_agents_config",
                component=ArtifactComponent.CONFIG,
                feature=Feature.FILESYSTEM_AGENT,
                description="Codex project subagent settings",
                lowering=(
                    "Yoke Codex agent settings compiled to "
                    ".codex/config.toml [agents]."
                ),
            )
        )
    artifacts.extend(
        [
            Artifact(
                path=file.path,
                text=file.text,
                kind="codex_agent",
                component=ArtifactComponent.AGENT,
                feature=Feature.FILESYSTEM_AGENT,
                description=f"Codex custom agent {file.name}",
                lowering=(
                    "Yoke subagent compiled to Codex custom-agent TOML at "
                    f"{file.path.as_posix()}."
                ),
            )
            for file in codex_agent_files(agent)
        ]
    )
    artifacts.extend(
        skill_artifact(
            skill,
        directory=".agents/skills",
        kind="codex_skill",
        component=ArtifactComponent.SKILL,
        feature=Feature.SKILLS,
        require_name=True,
        lowering=(
            "Yoke skill with loaded instructions compiled to Codex "
            "filesystem skill."
        ),
    )
        for skill in agent_inline_skills(agent)
    )
    return tuple(artifacts)


def claude_artifacts(agent: Agent) -> tuple[Artifact, ...]:
    artifacts = [
        claude_agent_artifact(name, subagent)
        for name, subagent in agent.subagents.items()
    ]
    artifacts.extend(
        skill_artifact(
            skill,
        directory=".claude/skills",
        kind="claude_skill",
        component=ArtifactComponent.SKILL,
        feature=Feature.SKILLS,
        require_name=False,
        lowering=(
            "Yoke skill with loaded instructions compiled to Claude "
            "filesystem skill."
        ),
        )
        for skill in agent_inline_skills(agent)
    )
    artifacts.extend(
        claude_workflow_artifact(name, workflow)
        for name, workflow in agent.workflows.items()
        if workflow.script is not None
    )
    return tuple(artifacts)


def claude_agent_artifact(name: str, agent: Agent) -> Artifact:
    agent_name = artifact_name(agent.options.get("claude_name"), name)
    frontmatter: dict[str, Any] = {
        "name": agent_name,
        "description": agent.description or f"Yoke subagent {agent_name}.",
    }
    tools = claude_tool_names(agent.tools)
    if tools:
        frontmatter["tools"] = tools
    if agent.model:
        frontmatter["model"] = agent.model
    if agent.effort:
        frontmatter["effort"] = str(agent.effort)
    skills = [skill.name for skill in agent.skills if skill.name]
    if skills:
        frontmatter["skills"] = skills
    body = agent.instructions or agent.description or (
        "Follow the parent agent's task for this subagent role."
    )
    return Artifact(
        path=Path(".claude/agents") / f"{slug(agent_name)}.md",
        text=markdown_with_frontmatter(frontmatter, body),
        kind="claude_agent",
        component=ArtifactComponent.AGENT,
        feature=Feature.DECLARED_SUBAGENTS,
        description=f"Claude custom subagent {agent_name}",
        lowering=(
            "Yoke subagent compiled to Claude custom subagent markdown at "
            f".claude/agents/{slug(agent_name)}.md."
        ),
    )


def claude_workflow_artifact(name: str, workflow: Workflow) -> Artifact:
    workflow_name = artifact_name(name, workflow.name)
    return Artifact(
        path=Path(".claude/workflows") / f"{slug(workflow_name)}.js",
        text=claude_workflow_text(workflow_name, workflow),
        kind="claude_workflow",
        component=ArtifactComponent.WORKFLOW,
        feature=Feature.NATIVE_WORKFLOW,
        description=f"Claude dynamic workflow {workflow_name}",
        lowering=(
            "Yoke script workflow compiled to Claude dynamic workflow script at "
            f".claude/workflows/{slug(workflow_name)}.js."
        ),
    )


def claude_workflow_text(name: str, workflow: Workflow) -> str:
    if workflow.script_path is not None:
        return (
            "export const meta = {\n"
            f"  name: {json.dumps(name)},\n"
            + (
                f"  description: {json.dumps(workflow.description)},\n"
                if workflow.description
                else ""
            )
            + "}\n\n"
            f"export {{ default }} from {json.dumps(str(workflow.script_path))}\n"
        )
    script = (workflow.script or "").strip()
    if re.search(r"\bexport\s+const\s+meta\b", script):
        return f"{script}\n"
    lines = [
        "export const meta = {",
        f"  name: {json.dumps(name)},",
    ]
    if workflow.description:
        lines.append(f"  description: {json.dumps(workflow.description)},")
    lines.extend(["}", "", script, ""])
    return "\n".join(lines)


def skill_artifact(
    skill: Skill,
    *,
    directory: str,
    kind: str,
    component: ArtifactComponent,
    feature: Feature,
    require_name: bool,
    lowering: str,
) -> Artifact:
    name = skill.name or "skill"
    frontmatter: dict[str, Any] = {
        "description": skill.description or f"Yoke skill {name}.",
    }
    if require_name or skill.name:
        frontmatter["name"] = name
    return Artifact(
        path=Path(directory) / slug(name) / "SKILL.md",
        text=markdown_with_frontmatter(frontmatter, skill.instructions or ""),
        kind=kind,
        component=component,
        feature=feature,
        description=f"{kind} {name}",
        lowering=f"{lowering} Path: {directory}/{slug(name)}/SKILL.md.",
    )


def artifact_skills(skills: tuple[Skill, ...]) -> tuple[Skill, ...]:
    """Return skills with loaded text that can be written into a bundle."""

    return tuple(skill for skill in skills if skill.instructions)


def agent_inline_skills(agent: Agent) -> tuple[Skill, ...]:
    """Return inline skills declared anywhere in an agent tree."""

    found: list[Skill] = []
    seen: dict[str, Skill] = {}
    for skill in artifact_skills(agent.skills):
        add_unique_skill(found, seen, skill)
    for subagent in agent.subagents.values():
        for skill in agent_inline_skills(subagent):
            add_unique_skill(found, seen, skill)
    return tuple(found)


def add_unique_skill(found: list[Skill], seen: dict[str, Skill], skill: Skill) -> None:
    path = skill_artifact_path(skill)
    existing = seen.get(path)
    if existing is not None:
        if skill_identity(existing) != skill_identity(skill):
            raise YokeError(
                "inline skills compile to the same provider path with different "
                f"content: {path}"
            )
        return
    found.append(skill)
    seen[path] = skill


def skill_artifact_path(skill: Skill) -> str:
    return slug(skill.name or "skill")


def skill_identity(skill: Skill) -> tuple[str | None, str | None, str | None]:
    return (skill.name, skill.description, skill.instructions)


def claude_tool_names(tools: Tools) -> list[str]:
    names: list[str] = []
    if tools.read:
        names.extend(["Read", "Grep", "Glob"])
    if tools.write:
        names.extend(["Write", "Edit"])
    if tools.shell:
        names.append("Bash")
    if tools.web:
        names.extend(["WebFetch", "WebSearch"])
    if tools.agent:
        names.append("Agent")
    return names


def artifact_name(configured: Any, fallback: str) -> str:
    if isinstance(configured, str) and configured.strip():
        return configured.strip()
    return fallback.strip()


def slug(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip()).strip("-")
    return normalized or "artifact"


def markdown_with_frontmatter(frontmatter: dict[str, Any], body: str) -> str:
    return f"---\n{yaml.safe_dump(frontmatter, sort_keys=False)}---\n{body.strip()}\n"
