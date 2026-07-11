"""Prompt-compiled provider helpers."""

from __future__ import annotations

from typing import Any


def compiled_subagents(agent: Any) -> str | None:
    """Render Yoke-declared subagents for providers without native delegation."""

    subagents = getattr(agent, "subagents", {}) or {}
    if not subagents:
        return None
    sections = [
        "Available Yoke subagents follow. On this provider surface they are "
        "compiled into instructions, not native delegated processes. Use a "
        "subagent by explicitly applying its role, tools, and instructions to "
        "the relevant part of the task."
    ]
    for name, subagent in subagents.items():
        parts = [f"## {name}"]
        if getattr(subagent, "description", None):
            parts.append(f"Description: {subagent.description}")
        hints = runtime_hints(subagent)
        if hints:
            parts.append(f"Runtime hints: {hints}")
        tools = enabled_tools(getattr(subagent, "tools", None))
        if tools:
            parts.append(f"Tools: {', '.join(tools)}")
        body = getattr(subagent, "instructions", None) or getattr(
            subagent, "description", None
        )
        if body:
            parts.append(f"Instructions:\n{body}")
        sections.append("\n".join(parts))
    return "\n\n".join(sections)


def runtime_hints(agent: Any) -> str | None:
    hints: list[str] = []
    if getattr(agent, "model", None):
        hints.append(f"model={agent.model}")
    if getattr(agent, "effort", None):
        hints.append(f"effort={agent.effort}")
    return ", ".join(hints) or None


def enabled_tools(tools: Any) -> list[str]:
    if tools is None:
        return []
    names = []
    for name in ("read", "write", "shell", "web", "agent"):
        if getattr(tools, name, False):
            names.append(name)
    return names
