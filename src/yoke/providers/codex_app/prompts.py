"""Prompt assembly for Codex app-server."""

from __future__ import annotations

from typing import Any

from yoke.providers.codex_app.skills import is_native_skill_path
from yoke.providers.compiled import enabled_tools, runtime_hints


def developer_instructions(agent: Any) -> str | None:
    parts: list[str] = []
    if agent.instructions:
        parts.append(agent.instructions)
    subagent_text = native_subagents(agent)
    if subagent_text:
        parts.append(subagent_text)
    skill_text = compiled_skills(agent)
    if skill_text:
        parts.append(skill_text)
    return "\n\n".join(parts) or None


def native_subagents(agent: Any) -> str | None:
    """Describe declared agents as real Codex collaboration calls."""

    subagents = getattr(agent, "subagents", {}) or {}
    if not subagents:
        return None
    sections = [
        "Available Yoke subagents follow. These are real delegated agents, not "
        "roles for the parent to simulate. When a request calls for one, invoke "
        "the native `spawn_agent` tool, pass the declared model override when "
        "present, include the declared instructions in its task, and wait for "
        "the child result. Never claim a subagent ran unless a spawn succeeded."
    ]
    for name, subagent in subagents.items():
        parts = [f"## {name}"]
        if getattr(subagent, "description", None):
            parts.append(f"Description: {subagent.description}")
        hints = runtime_hints(subagent)
        if hints:
            parts.append(f"Spawn overrides: {hints}")
        tools = enabled_tools(getattr(subagent, "tools", None))
        if tools:
            parts.append(f"Requested tools: {', '.join(tools)}")
        body = getattr(subagent, "instructions", None) or getattr(
            subagent, "description", None
        )
        if body:
            parts.append(f"Child task instructions:\n{body}")
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
