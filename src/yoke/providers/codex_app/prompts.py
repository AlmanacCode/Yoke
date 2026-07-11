"""Prompt assembly for Codex app-server."""

from __future__ import annotations

from typing import Any

from yoke.providers.codex_app.skills import is_native_skill_path


def developer_instructions(
    agent: Any,
    *,
    role_names: dict[str, str] | None = None,
    inline_skills_native: bool = False,
) -> str | None:
    parts: list[str] = []
    if agent.instructions:
        parts.append(agent.instructions)
    subagent_text = native_subagents(agent, role_names=role_names)
    if subagent_text:
        parts.append(subagent_text)
    skill_text = None if inline_skills_native else compiled_skills(agent)
    if skill_text:
        parts.append(skill_text)
    return "\n\n".join(parts) or None


def native_subagents(
    agent: Any,
    *,
    role_names: dict[str, str] | None = None,
) -> str | None:
    """Tell the parent how to select provider-native named agents."""

    subagents = getattr(agent, "subagents", {}) or {}
    if not subagents:
        return None
    sections = [
        "Available native Codex subagents follow. When one matches the work, call "
        "`spawn_agent` with its exact `agent_type`, use `fork_turns=\"none\"` "
        "(or a partial turn count), provide only the concrete task, and wait for "
        "the result. Never simulate these roles or use an untyped generic child."
    ]
    for name, subagent in subagents.items():
        role_name = (role_names or {}).get(name, name)
        parts = [f"## {name}"]
        if getattr(subagent, "description", None):
            parts.append(f"Description: {subagent.description}")
        parts.append(
            f'Invocation: spawn_agent(agent_type="{role_name}", fork_turns="none")'
        )
        sections.append("\n".join(parts))
    return "\n\n".join(sections)


def compiled_skills(agent: Any) -> str | None:
    skills = [
        skill
        for skill in agent.skills
        if skill.instructions and not is_native_skill_path(skill.path)
    ]
    if not skills:
        return None
    sections = [
        "Available Yoke skills follow. Treat each skill as optional procedure "
        "context; use it only when the user request matches its description."
    ]
    for skill in skills:
        header = skill.name or "skill"
        description = f"\nDescription: {skill.description}" if skill.description else ""
        sections.append(f"## {header}{description}\n\n{skill.instructions}")
    return "\n\n".join(sections)
