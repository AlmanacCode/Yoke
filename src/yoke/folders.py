"""Yoke-native folder writer."""

from __future__ import annotations

import shutil
from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from yoke.errors import YokeError
from yoke.loader import (
    AGENT_FILE,
    INSTRUCTIONS_FILE,
    SKILL_FILE,
    SKILLS_DIR,
    SUBAGENTS_DIR,
    WORKFLOW_PROGRAM_FILE,
    WORKFLOW_SCRIPT_FILE,
    WORKFLOWS_DIR,
)
from yoke.models import Agent, Skill, Workflow
from yoke.options import RuntimeOption, runtime_options


def save(
    agent: Agent,
    path: str | Path,
    *,
    overwrite: bool = False,
    allow_runtime_only: bool = False,
) -> tuple[Path, ...]:
    """Write `agent` as a Yoke-native folder and return written paths."""

    if not allow_runtime_only:
        raise_for_runtime_options(agent)
    root = Path(path)
    written: list[Path] = []
    root.mkdir(parents=True, exist_ok=True)
    written.append(write_file(root / AGENT_FILE, agent_config(agent), overwrite))
    if agent.instructions:
        written.append(
            write_file(root / INSTRUCTIONS_FILE, agent.instructions, overwrite)
        )
    for skill in agent.skills:
        written.extend(write_skill(root / SKILLS_DIR, skill, overwrite))
    for name, subagent in agent.subagents.items():
        written.extend(
            save(
                subagent,
                root / SUBAGENTS_DIR / slug(name),
                overwrite=overwrite,
                allow_runtime_only=allow_runtime_only,
            )
        )
    for name, workflow in agent.workflows.items():
        written.extend(
            write_workflow(
                root / WORKFLOWS_DIR,
                name,
                workflow,
                overwrite,
                allow_runtime_only,
            )
        )
    return tuple(written)


def raise_for_runtime_options(agent: Agent) -> None:
    """Reject folder saves that would silently omit runtime-only values."""

    options = agent_runtime_options(agent)
    if not options:
        return
    details = "; ".join(f"{item.path}: {item.reason}" for item in options)
    raise YokeError(
        "Yoke folders cannot serialize runtime-only SDK options. "
        "Remove them or call save(..., allow_runtime_only=True) to omit them. "
        f"{details}"
    )


def agent_runtime_options(agent: Agent, prefix: str = "") -> tuple[RuntimeOption, ...]:
    """Return runtime-only options reachable from a folder-serializable agent."""

    found: list[RuntimeOption] = []
    found.extend(runtime_options(agent.options, join_path(prefix, "options")))
    for name, subagent in agent.subagents.items():
        found.extend(
            agent_runtime_options(
                subagent,
                join_path(prefix, f"subagents.{name}"),
            )
        )
    for name, workflow in agent.workflows.items():
        workflow_path = join_path(prefix, f"workflows.{name}")
        if workflow.handler is not None:
            found.append(
                RuntimeOption(
                    path=join_path(workflow_path, "handler"),
                    reason=(
                        "Workflow handlers are live Python callables. Use "
                        "Workflow.from_program(...) or a workflow.py folder file "
                        "when the workflow should round-trip."
                    ),
                )
            )
        for step in workflow.steps:
            found.extend(
                runtime_options(
                    step.run,
                    join_path(workflow_path, f"steps.{step.name}.run"),
                )
            )
    return tuple(found)


def join_path(prefix: str, suffix: str) -> str:
    """Join dotted option path fragments."""

    return f"{prefix}.{suffix}" if prefix else suffix


def agent_config(agent: Agent) -> str:
    data: dict[str, Any] = {}
    if agent.description:
        data["description"] = agent.description
    if agent.model:
        data["model"] = agent.model
    if agent.effort:
        data["effort"] = plain(agent.effort)
    if agent.goal:
        data["goal"] = goal_config(agent.goal)
    tools = plain(agent.tools, exclude_defaults=True)
    if tools:
        data["tools"] = tools
    permissions = plain(agent.permissions, exclude_defaults=True)
    if permissions:
        data["permissions"] = permissions
    if agent.options:
        data["options"] = plain(agent.options)
    return yaml.safe_dump(data, sort_keys=False)


def write_workflow(
    root: Path,
    name: str,
    workflow: Workflow,
    overwrite: bool,
    allow_runtime_only: bool,
) -> tuple[Path, ...]:
    """Write a workflow as an Eve-like markdown step folder."""

    require_path_identity(name, "workflow")
    if workflow.name != name:
        raise YokeError(
            f"workflow mapping key {name!r} must match Workflow.name "
            f"{workflow.name!r}; folder identity comes from the path"
        )
    target = root / name
    written: list[Path] = []
    metadata: dict[str, Any] = {}
    if workflow.description:
        metadata["description"] = workflow.description
    if workflow.program_path is not None:
        metadata["language"] = "python"
        if workflow.args is not None:
            metadata["args"] = workflow.args
        if metadata:
            written.append(
                write_file(
                    target / "workflow.yaml",
                    yaml.safe_dump(metadata, sort_keys=False),
                    overwrite,
                )
            )
        copy_file(workflow.program_path, target / WORKFLOW_PROGRAM_FILE, overwrite)
        written.append(target / WORKFLOW_PROGRAM_FILE)
        return tuple(written)
    if workflow.handler is not None:
        if allow_runtime_only:
            return ()
        raise YokeError("workflow handler cannot be serialized")
    if workflow.native:
        if workflow.language:
            metadata["language"] = plain(workflow.language)
        if workflow.script_path is not None:
            metadata["script_path"] = str(workflow.script_path)
        if workflow.native_name is not None:
            metadata["native_name"] = workflow.native_name
        if workflow.args is not None:
            metadata["args"] = workflow.args
        if workflow.resume_from_run_id is not None:
            metadata["resume_from_run_id"] = workflow.resume_from_run_id
        if metadata:
            written.append(
                write_file(
                    target / "workflow.yaml",
                    yaml.safe_dump(metadata, sort_keys=False),
                    overwrite,
                )
            )
        if workflow.script is not None:
            written.append(
                write_file(target / WORKFLOW_SCRIPT_FILE, workflow.script, overwrite)
            )
        return tuple(written)
    if metadata:
        written.append(
            write_file(
                target / "workflow.yaml",
                yaml.safe_dump(metadata, sort_keys=False),
                overwrite,
            )
    )
    for step in workflow.steps:
        require_path_identity(step.name, "workflow step")
        written.append(
            write_file(
                target / f"{step.name}.md",
                step_markdown(step),
                overwrite,
            )
        )
    return tuple(written)


def step_markdown(step: Any) -> str:
    frontmatter: dict[str, Any] = {}
    if step.agent != "main":
        frontmatter["agent"] = step.agent
    if step.depends_on:
        frontmatter["depends_on"] = list(step.depends_on)
    if step.output_schema is not None:
        frontmatter["output_schema"] = plain(step.output_schema)
    if step.run is not None:
        run = plain(step.run, exclude_unset=True)
        if run:
            frontmatter["run"] = run
    if frontmatter:
        return markdown(frontmatter, step.prompt)
    return step.prompt


def goal_config(goal: Any) -> Any:
    data = plain(goal, exclude_defaults=True)
    if isinstance(data, dict) and set(data) == {"objective"}:
        return data["objective"]
    return data


def write_skill(root: Path, skill: Skill, overwrite: bool) -> tuple[Path, ...]:
    name = skill.name or skill_name_from_path(skill.path)
    target = root / slug(name)
    if skill.instructions is not None:
        frontmatter: dict[str, Any] = {"name": name}
        if skill.description:
            frontmatter["description"] = skill.description
        return (
            write_file(
                target / SKILL_FILE,
                markdown(frontmatter, skill.instructions),
                overwrite,
            ),
        )
    if skill.path is None:
        return ()
    source = skill.path
    if source.is_dir():
        copy_dir(source, target, overwrite)
        return tuple(path for path in target.rglob("*") if path.is_file())
    if source.is_file():
        suffix = source.suffix or ".md"
        copied = target.with_suffix(suffix)
        copy_file(source, copied, overwrite)
        return (copied,)
    raise FileNotFoundError(f"skill path does not exist: {source}")


def skill_name_from_path(path: Path | None) -> str:
    if path is None:
        return "skill"
    if path.name == SKILL_FILE:
        return path.parent.name
    return path.stem if path.is_file() else path.name


def write_file(path: Path, text: str, overwrite: bool) -> Path:
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n")
    return path


def require_path_identity(name: str, kind: str) -> None:
    """Reject names that cannot round-trip as folder/file identity."""

    if name == slug(name):
        return
    raise YokeError(
        f"{kind} name {name!r} cannot be serialized as path identity "
        f"{slug(name)!r}; rename it before saving"
    )


def copy_file(source: Path, target: Path, overwrite: bool) -> None:
    if target.exists() and not overwrite:
        raise FileExistsError(f"{target} already exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def copy_dir(source: Path, target: Path, overwrite: bool) -> None:
    if target.exists() and not overwrite:
        raise FileExistsError(f"{target} already exists")
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)


def markdown(frontmatter: dict[str, Any], body: str) -> str:
    return f"---\n{yaml.safe_dump(frontmatter, sort_keys=False)}---\n{body.strip()}\n"


def plain(
    value: Any,
    *,
    exclude_defaults: bool = False,
    exclude_unset: bool = False,
) -> Any:
    if isinstance(value, BaseModel):
        return {
            key: plain(
                item,
                exclude_defaults=exclude_defaults,
                exclude_unset=exclude_unset,
            )
            for key, item in value.model_dump(
                mode="python",
                exclude_none=True,
                exclude_defaults=exclude_defaults,
                exclude_unset=exclude_unset,
            ).items()
        }
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, dict):
        return {
            str(key): plain(
                item,
                exclude_defaults=exclude_defaults,
                exclude_unset=exclude_unset,
            )
            for key, item in value.items()
        }
    if isinstance(value, tuple | list):
        return [
            plain(
                item,
                exclude_defaults=exclude_defaults,
                exclude_unset=exclude_unset,
            )
            for item in value
        ]
    return value


def slug(value: str) -> str:
    return "-".join(value.strip().split()) or "item"
