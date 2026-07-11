"""Manual smoke checks for real local harness surfaces.

Run from the repository root:

    python scripts/smoke_harnesses.py

Add `--run-codex-cli`, `--run-codex-sdk`, `--run-codex-app-server`,
`--run-claude`, `--run-claude-hooks`, or `--run-claude-subagents` to perform
one tiny provider turn. Add `--run-codex-app-workflow` or
`--run-claude-workflow` to perform a folder-first Python Workflow smoke with
durable replay. Add provider-specific fork, goal, or metadata flags to exercise
native session controls. The default mode only checks readiness because real
provider operations can be slow, billable, and account-dependent.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if SRC.exists():
    sys.path.insert(0, str(SRC))

from yoke import (  # noqa: E402
    Access,
    Agent,
    Approval,
    Channel,
    ClaudeOptions,
    CodexAppServerOptions,
    CodexOptions,
    Collaboration,
    CollaborationSettings,
    Feature,
    ForkOptions,
    Goal,
    GoalLoopOptions,
    Harness,
    Permissions,
    Provider,
    ProviderOptions,
    Response,
    RunOptions,
    SessionOptions,
    Skill,
    Surface,
    ToolKind,
    WorkflowOptions,
    WorkflowStore,
)


def main() -> int:
    args = parse_args()
    agent = Agent(instructions="You are a concise smoke-test agent.")
    cwd = Path.cwd()
    all_checks = (
        Harness(
            provider=Provider.CODEX,
            surface=Surface.CODEX_CLI,
            agent=agent,
            cwd=cwd,
        ),
        Harness(
            provider=Provider.CODEX,
            surface=Surface.CODEX_APP_SERVER,
            agent=agent,
            cwd=cwd,
        ),
        Harness(
            provider=Provider.CODEX,
            surface=Surface.CODEX_PYTHON_SDK,
            agent=agent,
            cwd=cwd,
        ),
        Harness(
            provider=Provider.CLAUDE,
            surface=Surface.CLAUDE_PYTHON_SDK,
            agent=agent,
            cwd=cwd,
        ),
    )
    checks = filter_channels(
        filter_checks(all_checks, args.surface),
        args.channel,
    )
    checks = filter_features(checks, args.feature)
    if args.list or args.plan:
        records = smoke_plan_records(checks)
        if args.json:
            print(json.dumps({"smokes": records}, indent=2))
        else:
            print_smoke_plan(records)
        return 0
    by_surface = {str(harness.surface): harness for harness in all_checks}
    readiness_results = []
    for harness in checks:
        readiness = harness.check_sync()
        readiness_results.append((harness, readiness))
        if args.json:
            continue
        print_readiness(harness, readiness)
        if args.capabilities:
            print_capabilities(harness)
    if args.json:
        print(
            json.dumps(
                {
                    "readiness": [
                        readiness_record(
                            harness,
                            readiness,
                            include_capabilities=args.capabilities,
                        )
                        for harness, readiness in readiness_results
                    ]
                },
                indent=2,
            )
        )
        return 0
    if args.run_codex_cli:
        result = by_surface["codex_cli"].run_sync(
            "Reply with exactly: yoke-smoke",
            RunOptions(inherit_goal=False, max_turns=1),
        )
        print(f"codex_cli run: {result.status}: {result.output}")
        if not result.ok:
            return 1
    if args.run_codex_app_server:
        result = by_surface["codex_app_server"].run_sync(
            "Reply with exactly: yoke-app-smoke",
            RunOptions(inherit_goal=False, max_turns=1),
        )
        print(f"codex_app_server run: {result.status}: {result.output}")
        if not result.ok:
            return 1
    if args.run_codex_app_stream:
        status = run_codex_app_stream_smoke(by_surface["codex_app_server"])
        if status:
            return status
    if args.run_codex_app_skills:
        status = run_skill_smoke(
            by_surface["codex_app_server"],
            marker="yoke-codex-skill-smoke",
            label="codex_app_server skills",
        )
        if status:
            return status
    if args.run_codex_app_collab:
        status = run_codex_app_collab_smoke(by_surface["codex_app_server"])
        if status:
            return status
    if args.run_codex_app_workflow:
        status = run_workflow_program_smoke(
            by_surface["codex_app_server"],
            marker="yoke-codex-workflow-smoke",
            label="codex_app_server workflow",
        )
        if status:
            return status
    if args.run_codex_sdk:
        result = by_surface["codex_python_sdk"].run_sync(
            "Reply with exactly: yoke-sdk-smoke",
            RunOptions(inherit_goal=False, max_turns=1),
        )
        print(f"codex_python_sdk run: {result.status}: {result.output}")
        if not result.ok:
            return 1
    if args.run_codex_sdk_stream:
        status = run_stream_smoke(
            by_surface["codex_python_sdk"],
            marker="yoke-sdk-stream-smoke",
            label="codex_python_sdk stream",
            completion="turn/completed",
            require_provider_session=False,
            require_text=False,
        )
        if status:
            return status
    if args.run_claude:
        result = by_surface["claude_python_sdk"].run_sync(
            "Reply with exactly: yoke-claude-smoke",
            RunOptions(inherit_goal=False, max_turns=1),
        )
        print(f"claude_python_sdk run: {result.status}: {result.output}")
        if not result.ok:
            return 1
    if args.run_claude_hooks:
        status = run_claude_hooks_smoke(by_surface["claude_python_sdk"])
        if status:
            return status
    if args.run_claude_permissions:
        status = run_claude_permission_smoke(by_surface["claude_python_sdk"])
        if status:
            return status
    if args.run_claude_skills:
        status = run_skill_smoke(
            by_surface["claude_python_sdk"],
            marker="yoke-claude-skill-smoke",
            label="claude_python_sdk skills",
        )
        if status:
            return status
    if args.run_claude_subagents:
        status = run_claude_subagent_smoke(by_surface["claude_python_sdk"])
        if status:
            return status
    if args.run_claude_workflow:
        status = run_workflow_program_smoke(
            by_surface["claude_python_sdk"],
            marker="yoke-claude-workflow-smoke",
            label="claude_python_sdk workflow",
        )
        if status:
            return status
    if args.run_codex_app_request:
        status = run_codex_app_request_smoke(by_surface["codex_app_server"])
        if status:
            return status
    if args.run_codex_app_goal:
        session = by_surface["codex_app_server"].start_sync(
            SessionOptions(goal=Goal("Verify Yoke native app-server goals."))
        )
        try:
            initial = session.get_goal_sync()
            session = session.set_goal_sync(Goal("Verify updated Yoke goal."))
            updated = session.get_goal_sync()
            session = session.clear_goal_sync()
            cleared = session.get_goal_sync()
        finally:
            session.close_sync()
        print(
            "codex_app_server goal: "
            f"initial={goal_objective(initial)!r} "
            f"updated={goal_objective(updated)!r} "
            f"cleared={goal_objective(cleared)!r}"
        )
        if (
            goal_objective(initial) != "Verify Yoke native app-server goals."
            or goal_objective(updated) != "Verify updated Yoke goal."
            or cleared is not None
        ):
            return 1
    if args.run_codex_app_goal_loop:
        status = run_codex_app_goal_loop_smoke(by_surface["codex_app_server"])
        if status:
            return status
    if args.run_codex_app_rename:
        status = run_codex_app_rename_smoke(by_surface["codex_app_server"])
        if status:
            return status
    if args.run_codex_app_fork:
        session = by_surface["codex_app_server"].start_sync(
            SessionOptions(inherit_goal=False)
        )
        fork = None
        try:
            source = session.run_sync(
                "Reply with exactly: yoke-fork-source",
                RunOptions(inherit_goal=False, max_turns=1),
            )
            if not source.ok:
                print(f"codex_app_server fork source failed: {source.output}")
                return 1
            fork = session.fork_sync(ForkOptions(ephemeral=True))
            print(f"codex_app_server fork: source={session.id} fork={fork.id}")
        finally:
            if fork is not None:
                fork.close_sync()
            session.close_sync()
        if fork is None or fork.id == session.id:
            return 1
    if args.run_codex_sdk_fork:
        session = by_surface["codex_python_sdk"].start_sync(
            SessionOptions(inherit_goal=False)
        )
        fork = None
        try:
            source = session.run_sync(
                "Reply with exactly: yoke-sdk-fork-source",
                RunOptions(inherit_goal=False, max_turns=1),
            )
            if not source.ok:
                print(f"codex_python_sdk fork source failed: {source.output}")
                return 1
            fork = session.fork_sync(ForkOptions(ephemeral=True))
            print(f"codex_python_sdk fork: source={session.id} fork={fork.id}")
        finally:
            if fork is not None:
                fork.close_sync()
            session.close_sync()
        if fork is None or fork.id == session.id:
            return 1
    if args.run_claude_fork:
        status = asyncio.run(
            run_claude_fork_smoke(by_surface["claude_python_sdk"])
        )
        if status:
            return status
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json",
        action="store_true",
        help="print readiness-only results as JSON and do not start provider runs",
    )
    parser.add_argument(
        "--surface",
        action="append",
        metavar="PROVIDER:SURFACE",
        help=(
            "limit readiness checks to a provider surface; aliases such as "
            "codex:app and claude:sdk are accepted"
        ),
    )
    parser.add_argument(
        "--channel",
        action="append",
        choices=[
            str(channel) for channel in Channel if channel is not Channel.CUSTOM
        ],
        help=(
            "limit readiness checks to an exposure channel; repeat for multiple "
            "channels"
        ),
    )
    parser.add_argument(
        "--feature",
        action="append",
        choices=[str(feature) for feature in Feature],
        help=(
            "limit readiness checks to surfaces that support a feature; repeat "
            "for multiple required features"
        ),
    )
    parser.add_argument(
        "--capabilities",
        action="store_true",
        help="include declared static capability reports in JSON readiness records",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="list readiness and live smoke commands without running providers",
    )
    parser.add_argument(
        "--plan",
        action="store_true",
        help="print the smoke matrix plan without running providers",
    )
    parser.add_argument(
        "--run-codex-cli",
        action="store_true",
        help="perform one tiny Codex CLI agent turn after readiness checks",
    )
    parser.add_argument(
        "--run-codex-app-server",
        action="store_true",
        help="perform one tiny Codex app-server agent turn after readiness checks",
    )
    parser.add_argument(
        "--run-codex-app-stream",
        action="store_true",
        help="perform one tiny Codex app-server streamed turn",
    )
    parser.add_argument(
        "--run-codex-app-skills",
        action="store_true",
        help="perform one tiny Codex app-server run with a folder skill",
    )
    parser.add_argument(
        "--run-codex-app-collab",
        action="store_true",
        help="perform one tiny Codex app-server run that should spawn a subagent",
    )
    parser.add_argument(
        "--run-codex-app-workflow",
        action="store_true",
        help="perform one tiny Codex app-server Workflow with durable replay",
    )
    parser.add_argument(
        "--run-codex-app-request",
        action="store_true",
        help="perform one tiny Codex app-server turn that should request approval",
    )
    parser.add_argument(
        "--run-codex-sdk",
        action="store_true",
        help="perform one tiny Codex Python SDK agent turn after readiness checks",
    )
    parser.add_argument(
        "--run-codex-sdk-stream",
        action="store_true",
        help="perform one tiny Codex Python SDK streamed turn",
    )
    parser.add_argument(
        "--run-claude",
        action="store_true",
        help="perform one tiny Claude Python SDK agent turn after readiness checks",
    )
    parser.add_argument(
        "--run-claude-hooks",
        action="store_true",
        help="perform one tiny Claude run with hook events enabled",
    )
    parser.add_argument(
        "--run-claude-permissions",
        action="store_true",
        help="perform one tiny Claude run with can_use_tool permission callback",
    )
    parser.add_argument(
        "--run-claude-skills",
        action="store_true",
        help="perform one tiny Claude Python SDK run with a folder skill",
    )
    parser.add_argument(
        "--run-claude-subagents",
        action="store_true",
        help="perform one tiny Claude run that should invoke a declared subagent",
    )
    parser.add_argument(
        "--run-claude-workflow",
        action="store_true",
        help="perform one tiny Claude Workflow with durable replay",
    )
    parser.add_argument(
        "--run-codex-app-goal",
        action="store_true",
        help="exercise native Codex app-server goal set/read/clear",
    )
    parser.add_argument(
        "--run-codex-app-goal-loop",
        action="store_true",
        help="exercise Yoke's Codex app-server goal_loop handle",
    )
    parser.add_argument(
        "--run-codex-app-rename",
        action="store_true",
        help="exercise native Codex app-server thread/name/set",
    )
    parser.add_argument(
        "--run-codex-app-fork",
        action="store_true",
        help="exercise native Codex app-server thread/fork",
    )
    parser.add_argument(
        "--run-codex-sdk-fork",
        action="store_true",
        help="exercise native Codex Python SDK thread_fork",
    )
    parser.add_argument(
        "--run-claude-fork",
        action="store_true",
        help="exercise Claude Python SDK resume fork",
    )
    return parser.parse_args()


def smoke_plan_records(checks: tuple[Harness, ...]) -> list[dict[str, str]]:
    """Return the smoke commands that apply to the selected surfaces."""

    records: list[dict[str, str]] = []
    for harness in checks:
        label = harness_label(harness)
        base = f"python scripts/smoke_harnesses.py --surface {label}"
        records.append(
            {
                "kind": "readiness",
                "provider": str(harness.provider),
                "surface": str(harness.surface),
                "channel": str(harness.profile().channel),
                "feature": "readiness, capabilities",
                "safety": "safe",
                "command": f"{base} --json --capabilities",
            }
        )
        for spec in live_smoke_specs(harness):
            records.append(
                {
                    "kind": "live",
                    "provider": str(harness.provider),
                    "surface": str(harness.surface),
                    "channel": str(harness.profile().channel),
                    "feature": spec["feature"],
                    "safety": "opt-in live provider run",
                    "command": f"{base} {spec['flag']}",
                }
            )
    return records


def live_smoke_specs(harness: Harness) -> tuple[dict[str, str], ...]:
    """Return live smoke flag metadata for one harness."""

    match str(harness.surface):
        case "codex_cli":
            return (
                {"feature": "one-shot", "flag": "--run-codex-cli"},
            )
        case "codex_app_server":
            return (
                {"feature": "one-shot", "flag": "--run-codex-app-server"},
                {"feature": "stream", "flag": "--run-codex-app-stream"},
                {"feature": "skills", "flag": "--run-codex-app-skills"},
                {"feature": "collab/subagents", "flag": "--run-codex-app-collab"},
                {"feature": "portable workflow", "flag": "--run-codex-app-workflow"},
                {"feature": "request handler", "flag": "--run-codex-app-request"},
                {"feature": "native goal", "flag": "--run-codex-app-goal"},
                {"feature": "goal loop", "flag": "--run-codex-app-goal-loop"},
                {"feature": "rename", "flag": "--run-codex-app-rename"},
                {"feature": "fork", "flag": "--run-codex-app-fork"},
            )
        case "codex_python_sdk":
            return (
                {"feature": "one-shot", "flag": "--run-codex-sdk"},
                {"feature": "stream", "flag": "--run-codex-sdk-stream"},
                {"feature": "fork", "flag": "--run-codex-sdk-fork"},
            )
        case "claude_python_sdk":
            return (
                {"feature": "one-shot", "flag": "--run-claude"},
                {"feature": "hooks", "flag": "--run-claude-hooks"},
                {"feature": "permissions", "flag": "--run-claude-permissions"},
                {"feature": "skills", "flag": "--run-claude-skills"},
                {"feature": "subagents", "flag": "--run-claude-subagents"},
                {"feature": "portable workflow", "flag": "--run-claude-workflow"},
                {"feature": "fork", "flag": "--run-claude-fork"},
            )
        case _:
            return ()


def print_smoke_plan(records: list[dict[str, str]]) -> None:
    """Print a compact smoke matrix without starting provider runs."""

    print("Smoke plan (provider calls are opt-in):")
    print("\nReadiness:")
    for record in records:
        if record["kind"] != "readiness":
            continue
        print(
            f"  {record['provider']}:{record['surface']} "
            f"[{record['channel']}]: {record['command']}"
        )
    print("\nLive smokes:")
    for record in records:
        if record["kind"] != "live":
            continue
        print(
            f"  {record['provider']}:{record['surface']} "
            f"{record['feature']}: {record['command']}"
        )


def run_skill_smoke(harness: Harness, *, marker: str, label: str) -> int:
    with TemporaryDirectory(prefix="yoke-skill-smoke-") as temp:
        skill = write_smoke_skill(Path(temp), marker)
        skill_name = "yoke-smoke-skill"
        if harness.provider == "claude":
            skill_name = f"/yoke-smoke-plugin:{skill_name}"
        skill_harness = Harness(
            provider=harness.provider,
            surface=harness.surface,
            cwd=harness.cwd,
            agent=Agent(
                instructions=(
                    "You are running a Yoke skill smoke. Use the "
                    "yoke-smoke-skill skill when asked."
                ),
                skills=(Skill.from_path(skill),),
            ),
        )
        result = skill_harness.run_sync(
            f"{skill_name} Reply exactly with its marker.",
            RunOptions(inherit_goal=False, max_turns=6),
        )
    print(f"{label}: {result.status}: output={result.output!r}")
    if not result.ok:
        return 1
    if marker not in (result.output or ""):
        print(f"{label}: missing expected marker {marker!r}")
        return 1
    return 0


def run_workflow_program_smoke(harness: Harness, *, marker: str, label: str) -> int:
    with TemporaryDirectory(prefix="yoke-workflow-smoke-") as temp:
        temp_root = Path(temp)
        workflow_name = "smoke"
        agent_root = write_smoke_workflow_agent(temp_root, workflow_name, marker)
        store = temp_root / "workflow.jsonl"
        workflow_harness = Harness(
            provider=harness.provider,
            surface=harness.surface,
            cwd=harness.cwd,
            agent=Agent.from_folder(agent_root),
        )
        options = WorkflowOptions(
            resume=f"{marker}-run",
            memory=WorkflowStore(store),
            run=RunOptions(inherit_goal=False, max_turns=2),
        )
        first = workflow_harness.workflow_sync(workflow_name, None, options)
        second = workflow_harness.workflow_sync(
            workflow_name,
            None,
            WorkflowOptions(
                resume=f"{marker}-run",
                memory=WorkflowStore(store),
                run=RunOptions(inherit_goal=False, max_turns=2),
            ),
        )
        cached = bool(second.traces and second.traces[0].cached)
        records = store.read_text().count("\n") if store.exists() else 0
    print(
        f"{label}: first={first.status} second={second.status} "
        f"cached={cached} records={records} output={second.output!r}"
    )
    if not first.ok or not second.ok:
        return 1
    if marker not in (second.output or ""):
        print(f"{label}: missing expected marker {marker!r}")
        return 1
    if not cached:
        print(f"{label}: second workflow run was not cached")
        return 1
    if records != 1:
        print(f"{label}: expected one replay record, saw {records}")
        return 1
    return 0


def write_smoke_workflow_agent(root: Path, workflow_name: str, marker: str) -> Path:
    agent = root / "agent"
    workflow = agent / "workflows" / workflow_name
    worker = agent / "subagents" / "worker"
    workflow.mkdir(parents=True)
    worker.mkdir(parents=True)
    (agent / "agent.yaml").write_text(
        "description: Coordinates a folder-first Workflow smoke.\n"
    )
    (agent / "instructions.md").write_text(
        "You coordinate a tiny Yoke Workflow smoke.\n"
    )
    (worker / "agent.yaml").write_text(
        "description: Emits the requested smoke marker.\n"
    )
    (worker / "instructions.md").write_text(
        "Reply only with the requested marker.\n"
    )
    (workflow / "workflow.yaml").write_text(
        "description: Exercise a folder-first Python Workflow program.\n"
        "language: python\n"
        "args:\n"
        f"  marker: {json.dumps(marker)}\n"
    )
    (workflow / "workflow.py").write_text(
        "async def main(ctx):\n"
        "    marker = ctx.args['marker']\n"
        "    run = await ctx.agent('worker', f'Reply exactly: {marker}')\n"
        "    return run.output\n"
    )
    return agent


def write_smoke_skill(root: Path, marker: str) -> Path:
    skill = root / "yoke-smoke-plugin" / "skills" / "yoke-smoke-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\n"
        "name: yoke-smoke-skill\n"
        "description: Use when asked for the Yoke skill smoke marker.\n"
        "---\n"
        f"When this skill is used, reply exactly: {marker}\n"
    )
    return skill


def run_claude_hooks_smoke(harness: Harness) -> int:
    try:
        from claude_agent_sdk import HookMatcher
    except ImportError:
        print(
            "claude_python_sdk hooks: missing claude_agent_sdk; "
            "try `uv run --with claude-agent-sdk ...`"
        )
        return 1

    async def record_hook(input_data, tool_use_id, context):
        return {}

    options = RunOptions(
        inherit_goal=False,
        max_turns=4,
        provider=ProviderOptions(
            claude=ClaudeOptions(
                include_hook_events=True,
                raw={
                    "hooks": {
                        "PreToolUse": [HookMatcher(hooks=[record_hook])],
                        "PostToolUse": [HookMatcher(hooks=[record_hook])],
                    }
                },
            )
        ),
    )
    result = harness.run_sync(
        "Use the Read tool to inspect README.md, then reply exactly: "
        "yoke-claude-hooks-smoke",
        options,
    )
    hooks = [event for event in result.events if event.kind == "hook"]
    tools = [event for event in result.events if event.tool is not None]
    print(
        "claude_python_sdk hooks: "
        f"{result.status}: hooks={len(hooks)} tools={len(tools)} "
        f"output={result.output!r}"
    )
    if not result.ok:
        return 1
    if not hooks:
        print("claude_python_sdk hooks: no hook events observed")
        return 1
    return 0


def run_claude_permission_smoke(harness: Harness) -> int:
    try:
        from claude_agent_sdk import HookMatcher, PermissionResultAllow
    except ImportError:
        print(
            "claude_python_sdk permissions: missing claude_agent_sdk; "
            "try `uv run --with claude-agent-sdk ...`"
        )
        return 1

    permission_allow = PermissionResultAllow
    seen = []
    marker = f"yoke-claude-permission-smoke-{uuid4().hex}"

    async def can_use_tool(tool_name, input_data, context):
        seen.append((tool_name, input_data, context))
        return permission_allow()

    async def keep_control_open(input_data, tool_use_id, context):
        return {}

    with TemporaryDirectory(prefix="yoke-claude-permission-smoke-") as temp:
        smoke_file = Path(temp) / "marker.txt"
        smoke_file.write_text(marker)
        options = RunOptions(
            inherit_goal=False,
            max_turns=4,
            provider=ProviderOptions(
                claude=ClaudeOptions(
                    can_use_tool=can_use_tool,
                    hooks={
                        "PreToolUse": [
                            HookMatcher(hooks=[keep_control_open])
                        ]
                    },
                ),
            ),
        )
        result = harness.run_sync(
            "Use the Read tool to read this file, then reply exactly with "
            f"the file contents and nothing else: {smoke_file}",
            options,
        )
    permission_events = [
        event for event in result.events if event.kind == "permission"
    ]
    print(
        "claude_python_sdk permissions: "
        f"{result.status}: callbacks={len(seen)} "
        f"permission_events={len(permission_events)} "
        f"output={result.output!r}"
    )
    if not result.ok:
        return 1
    if marker not in (result.output or ""):
        print("claude_python_sdk permissions: missing expected output")
        return 1
    if not seen:
        print("claude_python_sdk permissions: can_use_tool was not called")
        return 1
    return 0


def run_claude_subagent_smoke(harness: Harness) -> int:
    subagent_harness = Harness(
        provider=harness.provider,
        surface=harness.surface,
        cwd=harness.cwd,
        agent=Agent(
            instructions=(
                "You are a concise smoke-test coordinator. When asked, delegate "
                "to the named Yoke subagent."
            ),
            subagents={
                "readme-reviewer": Agent(
                    description="Reads README.md and reports one tiny fact.",
                    instructions=(
                        "Read README.md and report one short fact. End your "
                        "answer with yoke-claude-subagent-smoke."
                    ),
                )
            },
        ),
    )
    result = subagent_harness.run_sync(
        "Use the readme-reviewer agent to inspect README.md, then reply with "
        "exactly: yoke-claude-subagent-smoke",
        RunOptions(inherit_goal=False, max_turns=6),
    )
    agent_events = [
        event
        for event in result.events
        if event.agent is not None
        or (event.tool is not None and event.tool.kind is ToolKind.AGENT)
    ]
    print(
        "claude_python_sdk subagents: "
        f"{result.status}: agent_events={len(agent_events)} "
        f"output={result.output!r}"
    )
    if not result.ok:
        return 1
    if "yoke-claude-subagent-smoke" not in (result.output or ""):
        print("claude_python_sdk subagents: missing expected output")
        return 1
    if not agent_events:
        print("claude_python_sdk subagents: no agent events observed")
        return 1
    return 0


def run_codex_app_collab_smoke(harness: Harness) -> int:
    result = harness.run_sync(
        "Spawn one explorer subagent to answer with exactly "
        "yoke-codex-collab-subagent-smoke. Wait for it, then reply exactly: "
        "yoke-codex-collab-subagent-smoke",
        RunOptions(
            inherit_goal=False,
            max_turns=8,
            provider=ProviderOptions(
                codex=CodexOptions(
                    experimental_api=True,
                    collaboration=Collaboration(
                        mode="plan",
                        settings=CollaborationSettings(
                            developer_instructions=None,
                            model="gpt-5.4-mini",
                            reasoning_effort="medium",
                        ),
                    )
                )
            ),
        ),
    )
    agent_events = [
        event
        for event in result.events
        if event.agent is not None
        or (event.tool is not None and event.tool.kind is ToolKind.AGENT)
    ]
    print(
        "codex_app_server collab: "
        f"{result.status}: agent_events={len(agent_events)} "
        f"output={result.output!r}"
    )
    if not result.ok:
        return 1
    if "yoke-codex-collab-subagent-smoke" not in (result.output or ""):
        print("codex_app_server collab: missing expected output")
        return 1
    if not agent_events:
        print("codex_app_server collab: no agent events observed")
        return 1
    return 0


def run_codex_app_request_smoke(harness: Harness) -> int:
    seen = []
    marker = f"yoke-codex-request-smoke-{uuid4().hex}"
    smoke_file = Path(f".yoke-request-smoke-{uuid4().hex}.txt")
    output_file = Path(f".yoke-request-output-{uuid4().hex}.txt")
    smoke_file.write_text(marker)
    output_marker: str | None = None

    def record_request(event, default):
        seen.append((event, default))
        if event.tool and event.tool.kind is ToolKind.SHELL:
            return Response.allow()
        return default

    try:
        result = harness.run_sync(
            "Use the shell tool to run exactly this harmless command: "
            f"`python -c \"from pathlib import Path; "
            f"marker = Path('{smoke_file.as_posix()}').read_text().strip(); "
            f"Path('{output_file.as_posix()}').write_text(marker); "
            f"print(marker)\"`. "
            "Do not answer from memory; the file content is not in this prompt. "
            "Wait for the command output, then reply with exactly the stdout marker.",
            RunOptions(
                inherit_goal=False,
                max_turns=4,
                permissions=Permissions(access=Access.READ, approval=Approval.ASK),
                provider=ProviderOptions(
                    codex=CodexOptions(
                        app_server=CodexAppServerOptions(
                            request_handler=record_request,
                        )
                    )
                ),
            ),
        )
        if output_file.exists():
            output_marker = output_file.read_text().strip()
    finally:
        smoke_file.unlink(missing_ok=True)
        output_file.unlink(missing_ok=True)
    request_events = [
        event
        for event in result.events
        if event.kind
        in {"approval_request", "user_input_request", "tool_request"}
    ]
    print(
        "codex_app_server request: "
        f"{result.status}: requests={len(request_events)} "
        f"handler_calls={len(seen)} output={result.output!r}"
    )
    if not result.ok:
        return 1
    if not request_events:
        print("codex_app_server request: no server request events observed")
        return 1
    if not seen:
        print("codex_app_server request: request_handler was not called")
        return 1
    if marker not in (result.output or ""):
        print("codex_app_server request: missing expected output")
        return 1
    if output_marker != marker:
        print("codex_app_server request: smoke output file was not written")
        return 1
    print("codex_app_server request: approved-smoke-command")
    return 0


def run_codex_app_stream_smoke(harness: Harness) -> int:
    return run_stream_smoke(
        harness,
        marker="yoke-stream-smoke",
        label="codex_app_server stream",
    )


def run_stream_smoke(
    harness: Harness,
    *,
    marker: str,
    label: str,
    completion: str = "done",
    require_provider_session: bool = True,
    require_text: bool = True,
) -> int:
    events = harness.stream_sync(
        f"Reply with exactly: {marker}",
        RunOptions(inherit_goal=False, max_turns=1),
    )
    kinds = [str(event.kind) for event in events]
    messages = [event.message or "" for event in events]
    text = "\n".join(messages)
    completion_seen = completion in kinds or completion in messages
    print(
        f"{label}: "
        f"events={len(events)} kinds={','.join(kinds)} "
        f"contains_smoke={marker in text}"
    )
    if require_provider_session and "provider_session" not in kinds:
        print(f"{label}: missing provider_session event")
        return 1
    if not completion_seen:
        print(f"{label}: missing {completion} event")
        return 1
    if require_text and marker not in text:
        print(f"{label}: missing expected text")
        return 1
    return 0


def run_codex_app_rename_smoke(harness: Harness) -> int:
    title = "Yoke smoke rename"
    session = harness.start_sync(SessionOptions(inherit_goal=False))
    try:
        renamed = session.rename_sync(title)
    finally:
        session.close_sync()
    print(
        "codex_app_server rename: "
        f"session={session.id} title={renamed.title!r}"
    )
    if renamed.title != title:
        return 1
    return 0


def run_codex_app_goal_loop_smoke(harness: Harness) -> int:
    goal = Goal("Verify Yoke goal_loop returns a provider session handle.")
    run = harness.goal_loop_sync(GoalLoopOptions(goal=goal))
    try:
        current = run.session.get_goal_sync()
    finally:
        run.session.close_sync()
    print(
        "codex_app_server goal_loop: "
        f"session={run.session.id} goal={goal_objective(current)!r} "
        f"auto_continues={run.auto_continues}"
    )
    if not run.ok:
        return 1
    if goal_objective(current) != goal.objective:
        return 1
    if not run.auto_continues:
        return 1
    return 0


async def run_claude_fork_smoke(harness: Harness) -> int:
    """Exercise Claude fork inside one event loop.

    ClaudeSDKClient owns asyncio subprocess state, so the live session cannot be
    started, run, forked, and closed through separate asyncio.run() calls.
    """

    session = await harness.start(SessionOptions(inherit_goal=False))
    fork = None
    try:
        source = await session.run(
            "Reply with exactly: yoke-claude-fork-source",
            RunOptions(inherit_goal=False, max_turns=1),
        )
        if not source.ok:
            print(f"claude_python_sdk fork source failed: {source.output}")
            return 1
        source_session = source.session or session
        fork = await source_session.fork()
        print(
            "claude_python_sdk fork: "
            f"source={source_session.provider_session_id} fork={fork.id}"
        )
    finally:
        if fork is not None:
            await fork.close()
        await session.close()
    if fork is None or fork.id == session.id:
        return 1
    return 0


def goal_objective(goal: Goal | None) -> str | None:
    return goal.objective if goal is not None else None


def filter_checks(
    checks: tuple[Harness, ...],
    specs: list[str] | None,
) -> tuple[Harness, ...]:
    if not specs:
        return checks
    requested = {surface_key(spec) for spec in specs}
    selected = tuple(
        harness for harness in checks if harness_key(harness) in requested
    )
    if len(selected) != len(requested):
        available = ", ".join(harness_label(harness) for harness in checks)
        selected_keys = {harness_key(harness) for harness in selected}
        missing = ", ".join(
            f"{provider}:{surface}"
            for provider, surface in sorted(requested - selected_keys)
        )
        raise SystemExit(
            f"unknown smoke surface {missing}; available surfaces: {available}"
        )
    return selected


def filter_channels(
    checks: tuple[Harness, ...],
    channels: list[str] | None,
) -> tuple[Harness, ...]:
    """Return checks whose surface belongs to one of the requested channels."""

    if not channels:
        return checks
    requested = {Channel(channel) for channel in channels}
    selected = tuple(
        harness for harness in checks if harness.profile().channel in requested
    )
    if not selected:
        available = ", ".join(sorted({str(h.profile().channel) for h in checks}))
        requested_text = ", ".join(sorted(str(channel) for channel in requested))
        raise SystemExit(
            f"no smoke surfaces matched channel {requested_text}; "
            f"available channels: {available}"
        )
    return selected


def filter_features(
    checks: tuple[Harness, ...],
    features: list[str] | None,
) -> tuple[Harness, ...]:
    """Return checks whose surface supports every requested feature."""

    if not features:
        return checks
    requested = tuple(Feature(feature) for feature in features)
    selected = tuple(
        harness for harness in checks if harness.profile().supports_all(requested)
    )
    if not selected:
        requested_text = ", ".join(str(feature) for feature in requested)
        considered = "; ".join(feature_fit(harness, requested) for harness in checks)
        considered_text = f" Considered: {considered}." if considered else ""
        raise SystemExit(
            f"no smoke surfaces support features {requested_text}."
            f"{considered_text}"
        )
    return selected


def feature_fit(harness: Harness, features: tuple[Feature, ...]) -> str:
    """Return a compact feature-fit summary for one smoke harness."""

    missing = harness.profile().missing(features)
    if not missing:
        return f"{harness_label(harness)} supports all"
    return (
        f"{harness_label(harness)} missing "
        f"{', '.join(str(feature) for feature in missing)}"
    )


def surface_key(spec: str) -> tuple[str, str]:
    try:
        provider, surface = spec.split(":", 1)
    except ValueError as error:
        raise SystemExit(
            f"surface must look like provider:surface, got {spec!r}"
        ) from error
    harness = Harness(
        provider=provider,
        surface=surface,
        agent=Agent(instructions="Normalize a smoke surface."),
        cwd=Path.cwd(),
    )
    if harness.surface is None:
        raise SystemExit("smoke surface filters must name a concrete surface")
    return harness_key(harness)


def harness_key(harness: Harness) -> tuple[str, str]:
    return str(harness.provider), str(harness.surface)


def harness_label(harness: Harness) -> str:
    provider, surface = harness_key(harness)
    return f"{provider}:{surface}"


def print_readiness(harness: Harness, readiness) -> None:
    status = "ok" if readiness.available else "missing"
    channel = harness.profile().channel
    print(
        f"{harness.provider}:{harness.surface} [{channel}]: "
        f"{status}: {readiness.message}"
    )
    if readiness.fix:
        print(f"  fix: {readiness.fix}")


def print_capabilities(harness: Harness) -> None:
    """Print a compact human capability summary for one surface."""

    report = harness.report()
    print(f"  capabilities: {report.key} [{report.channel}]")
    for feature in report.features:
        if feature.lowering is None:
            continue
        print(f"    {feature.feature}: {feature.support}")
        print(f"      lowering: {feature.lowering}")


def readiness_record(
    harness: Harness,
    readiness,
    *,
    include_capabilities: bool = False,
) -> dict[str, object]:
    record: dict[str, object] = {
        "provider": str(harness.provider),
        "surface": str(harness.surface),
        "channel": str(harness.profile().channel),
        "available": readiness.available,
        "message": readiness.message,
        "fix": readiness.fix,
    }
    if include_capabilities:
        record["capabilities"] = harness.report().model_dump()
    return record


if __name__ == "__main__":
    raise SystemExit(main())
