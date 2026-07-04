"""Folder loader for Yoke agents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from yoke.models import Agent, Goal, Permissions, Skill, Step, Tools, Workflow

AGENT_FILE = "agent.yaml"
INSTRUCTIONS_FILE = "instructions.md"
SKILLS_DIR = "skills"
SUBAGENTS_DIR = "subagents"
WORKFLOWS_DIR = "workflows"


def load(path: str | Path) -> Agent:
    """Load an agent folder.

    This is intentionally small. It establishes folder parity without yet
    compiling provider-specific artifacts.
    """

    root = Path(path)
    config = read_yaml(root / AGENT_FILE)
    instructions = read_optional_text(root / INSTRUCTIONS_FILE)
    skills = load_skills(root / SKILLS_DIR)
    subagents = load_subagents(root / SUBAGENTS_DIR)
    workflows = load_workflows(root / WORKFLOWS_DIR)
    goal = config.get("goal")
    return Agent(
        instructions=instructions or config.get("instructions"),
        description=config.get("description"),
        model=config.get("model"),
        effort=config.get("effort"),
        goal=Goal(**goal) if isinstance(goal, dict) else None,
        tools=Tools(**config["tools"]) if isinstance(config.get("tools"), dict) else Tools(),
        permissions=Permissions(**config["permissions"])
        if isinstance(config.get("permissions"), dict)
        else Permissions(),
        skills=tuple(skills),
        subagents=subagents,
        workflows=workflows,
        options=config.get("options", {}),
    )


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text())
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def read_optional_text(path: Path) -> str | None:
    if not path.exists():
        return None
    text = path.read_text().strip()
    return text or None


def load_skills(path: Path) -> list[Skill]:
    if not path.exists():
        return []
    skills: list[Skill] = []
    for child in sorted(path.iterdir()):
        if child.is_dir():
            skills.append(Skill.from_path(child, name=child.name))
        elif child.is_file():
            skills.append(Skill(name=child.stem, path=child))
    return skills


def load_subagents(path: Path) -> dict[str, Agent]:
    if not path.exists():
        return {}
    agents: dict[str, Agent] = {}
    for child in sorted(path.iterdir()):
        if child.is_dir():
            agents[child.name] = load(child)
    return agents


def load_workflows(path: Path) -> dict[str, Workflow]:
    if not path.exists():
        return {}
    workflows: dict[str, Workflow] = {}
    for child in sorted(path.glob("*.yaml")) + sorted(path.glob("*.yml")):
        data = read_yaml(child)
        name = str(data.get("name") or child.stem)
        steps = tuple(Step(**step) for step in data.get("steps", []))
        workflows[name] = Workflow(
            name=name,
            description=data.get("description"),
            steps=steps,
        )
    return workflows
