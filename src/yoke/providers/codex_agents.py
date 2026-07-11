"""Codex custom-agent file compilation.

Codex loads project-scoped custom agents from `.codex/agents/*.toml`.
Yoke keeps that as a provider compile target, not as an implicit side effect of
running a prompt.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import AliasChoices, Field

from yoke.models import Access, Agent, Permissions, Skill, YokeModel


class CodexAgentSettings(YokeModel):
    """Project-level Codex `[agents]` settings."""

    max_threads: int | None = Field(
        default=None,
        validation_alias=AliasChoices("max_threads", "maxThreads"),
    )
    max_depth: int | None = Field(
        default=None,
        validation_alias=AliasChoices("max_depth", "maxDepth"),
    )
    job_max_runtime_seconds: int | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "job_max_runtime_seconds",
            "jobMaxRuntimeSeconds",
        ),
    )

    @property
    def configured(self) -> bool:
        """Whether any setting is explicitly configured."""

        return any(
            value is not None
            for value in (
                self.max_threads,
                self.max_depth,
                self.job_max_runtime_seconds,
            )
        )


class CodexAgentFile(YokeModel):
    """One `.codex/agents/*.toml` file Yoke can materialize explicitly."""

    name: str
    path: Path
    text: str


def codex_agent_files(
    agent: Agent,
    *,
    directory: str | Path = ".codex/agents",
) -> tuple[CodexAgentFile, ...]:
    """Compile direct Yoke subagents to Codex custom-agent TOML files."""

    root = Path(directory)
    files: list[CodexAgentFile] = []
    for name, subagent in agent.subagents.items():
        codex_name = codex_agent_name(name, subagent)
        filename = f"{slug(codex_name)}.toml"
        files.append(
            CodexAgentFile(
                name=codex_name,
                path=root / filename,
                text=codex_agent_toml(codex_name, subagent),
            )
        )
    return tuple(files)


def codex_agent_settings(agent: Agent) -> CodexAgentSettings | None:
    """Return project-level Codex agent settings from a Yoke agent."""

    value = agent.options.get("codex_agents", agent.options.get("codexAgents"))
    if value is None:
        return None
    settings = (
        value
        if isinstance(value, CodexAgentSettings)
        else CodexAgentSettings.model_validate(value)
        if isinstance(value, dict)
        else None
    )
    if settings is None or not settings.configured:
        return None
    return settings


def codex_agent_settings_toml(settings: CodexAgentSettings) -> str:
    """Render project-level Codex `[agents]` settings."""

    lines = ["[agents]"]
    if settings.max_threads is not None:
        lines.append(f"max_threads = {settings.max_threads}")
    if settings.max_depth is not None:
        lines.append(f"max_depth = {settings.max_depth}")
    if settings.job_max_runtime_seconds is not None:
        lines.append(
            f"job_max_runtime_seconds = {settings.job_max_runtime_seconds}"
        )
    return "\n".join(lines) + "\n"


def codex_agent_toml(name: str, agent: Agent) -> str:
    """Render one Codex custom-agent TOML document."""

    lines = [
        f"name = {toml_string(name)}",
        f"description = {toml_string(description_for(name, agent))}",
    ]
    if agent.model:
        lines.append(f"model = {toml_string(agent.model)}")
    if agent.effort:
        lines.append(f"model_reasoning_effort = {toml_string(str(agent.effort))}")

    sandbox = sandbox_mode(agent.permissions)
    if sandbox:
        lines.append(f"sandbox_mode = {toml_string(sandbox)}")

    nicknames = option_list(agent, "nickname_candidates")
    if nicknames:
        lines.append(f"nickname_candidates = {toml_array(nicknames)}")

    lines.append(f"developer_instructions = {toml_multiline(instructions_for(agent))}")

    mcp_servers = option_mapping(agent, "mcp_servers")
    for server_name, config in mcp_servers.items():
        lines.append("")
        lines.append(f"[mcp_servers.{server_name}]")
        for key, value in config.items():
            lines.append(f"{key} = {toml_value(value)}")

    for skill in path_skills(agent.skills):
        lines.append("")
        lines.append("[[skills.config]]")
        lines.append(f"path = {toml_string(str(skill.path))}")
        lines.append("enabled = true")

    return "\n".join(lines) + "\n"


def codex_agent_name(name: str, agent: Agent) -> str:
    configured = agent.options.get("codex_name")
    if isinstance(configured, str) and configured.strip():
        return configured.strip()
    return name.strip()


def description_for(name: str, agent: Agent) -> str:
    if agent.description and agent.description.strip():
        return agent.description.strip()
    return f"Yoke subagent {name}."


def instructions_for(agent: Agent) -> str:
    body = agent.instructions or agent.description
    if body is None or not body.strip():
        return "Follow the parent agent's task for this subagent role."
    return body.strip()


def sandbox_mode(permissions: Permissions) -> str | None:
    match permissions.access:
        case Access.READ:
            return "read-only"
        case Access.WRITE:
            return "workspace-write"
        case Access.FULL:
            return "danger-full-access"
    return None


def option_list(agent: Agent, key: str) -> list[str]:
    value = agent.options.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def option_mapping(agent: Agent, key: str) -> dict[str, dict[str, Any]]:
    value = agent.options.get(key)
    if not isinstance(value, dict):
        return {}
    return {
        str(name): config
        for name, config in value.items()
        if isinstance(name, str) and isinstance(config, dict)
    }


def path_skills(skills: tuple[Skill, ...]) -> tuple[Skill, ...]:
    return tuple(skill for skill in skills if skill.path is not None)


def slug(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip()).strip("-")
    return normalized or "agent"


def toml_string(value: str) -> str:
    return json.dumps(value)


def toml_multiline(value: str) -> str:
    escaped = value.replace('"""', '\\"\\"\\"')
    return f'"""\n{escaped}\n"""'


def toml_array(values: list[str]) -> str:
    return "[" + ", ".join(toml_string(value) for value in values) + "]"


def toml_value(value: Any) -> str:
    if isinstance(value, str):
        return toml_string(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return toml_array(value)
    return toml_string(str(value))
