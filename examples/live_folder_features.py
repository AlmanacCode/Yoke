"""Live-check a folder agent's skill, subagent, and subagent model.

This script makes real provider calls. Run it explicitly from the repository root.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from yoke import Agent, Harness, RunOptions, ToolKind

ROOT = Path(__file__).parent / "live_folder_features"


async def run(provider: str) -> bool:
    surface = "codex_app_server" if provider == "codex" else "claude_python_sdk"
    agent = Agent.from_folder(ROOT / provider)
    reviewer = agent.subagents["folder-reviewer"]
    expected_model = reviewer.model
    bundle = agent.bundle(provider=provider)
    subagent_artifact = next(
        artifact
        for artifact in bundle.artifacts
        if "agents/folder-reviewer" in artifact.path.as_posix()
    )
    harness = Harness(
        provider=provider,
        surface=surface,
        agent=agent,
        cwd=Path.cwd(),
    )
    result = await harness.run(
        "Use the folder-proof skill, then delegate to folder-reviewer. "
        "Return both exact markers from them.",
        RunOptions(inherit_goal=False, max_turns=10),
    )
    output = result.output or ""
    agent_events = tuple(
        event
        for event in result.events
        if event.agent is not None
        or (event.tool is not None and event.tool.kind is ToolKind.AGENT)
    )
    observed_models = tuple(
        event.agent.model
        for event in agent_events
        if event.agent is not None and event.agent.model
    )
    checks = {
        "loaded_skill": agent.skills[0].name == "folder-proof",
        "loaded_subagent": reviewer.instructions.endswith(
            "yoke-folder-subagent-proof"
        ),
        "loaded_model": expected_model is not None,
        "lowered_model": expected_model in subagent_artifact.text,
        "skill_used": "yoke-folder-skill-proof" in output,
        "subagent_used": "yoke-folder-subagent-proof" in output,
        "agent_events": bool(agent_events),
    }
    print(
        f"{provider}: status={result.status} expected_model={expected_model!r} "
        f"observed_models={observed_models!r} checks={checks!r} output={output!r}"
    )
    if not observed_models:
        print(
            f"{provider}: provider events did not report an effective subagent "
            "model; configuration was verified, execution identity was not"
        )
    return result.ok and all(checks.values())


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--provider",
        action="append",
        choices=("codex", "claude"),
        dest="providers",
    )
    args = parser.parse_args()
    providers = tuple(args.providers or ("codex", "claude"))
    results = await asyncio.gather(*(run(provider) for provider in providers))
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
