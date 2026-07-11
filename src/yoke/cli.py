"""Command line interface for Yoke."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from yoke.models import (
    Collection,
    Harness,
    normalize_provider_surface,
    split_provider_surface,
)
from yoke.options import WorkflowOptions
from yoke.store import RUN_EVENTS_FILE, RUN_RECORD_FILE, RunStore


def main(argv: list[str] | None = None) -> int:
    """Run the Yoke CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except KeyboardInterrupt:
        return 130


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""

    parser = argparse.ArgumentParser(prog="yoke")
    subcommands = parser.add_subparsers(dest="command", required=True)

    run = subcommands.add_parser("run", help="Run a named agent from a collection")
    run.add_argument("collection", help="Agent collection folder, usually agents")
    run.add_argument("agent", help="Agent name from yoke.yaml")
    run.add_argument("prompt", help="Prompt to run")
    run.add_argument("--provider", help="Provider surface, such as codex:app")
    run.add_argument("--cwd", default=".", help="Working directory for the harness")
    run.add_argument("--store", default=".yoke", help="Yoke store root")
    run.set_defaults(handler=run_command)

    workflow = subcommands.add_parser(
        "workflow",
        help="Run a named workflow from a collection agent",
    )
    workflow.add_argument("collection", help="Agent collection folder, usually agents")
    workflow.add_argument("agent", help="Agent name from yoke.yaml")
    workflow.add_argument("workflow", help="Workflow name from the agent folder")
    workflow.add_argument("prompt", nargs="?", default=None, help="Workflow input")
    workflow.add_argument("--provider", help="Provider surface, such as codex:app")
    workflow.add_argument(
        "--cwd",
        default=".",
        help="Working directory for the harness",
    )
    workflow.add_argument("--store", default=".yoke", help="Yoke store root")
    workflow.add_argument("--native", action="store_true", help="Use native workflow")
    workflow.add_argument("--resume", help="Resume/replay workflow run id")
    workflow.add_argument("--concurrency", type=int, help="Workflow concurrency")
    workflow.add_argument("--channel", help="Provider channel for this workflow")
    workflow.add_argument("--args", help="Structured workflow input as JSON")
    workflow.add_argument(
        "--fail-fast",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Stop after the first failed step",
    )
    workflow.set_defaults(handler=workflow_command)

    explain = subcommands.add_parser(
        "explain",
        help="Explain how a named agent maps to a provider surface",
    )
    explain.add_argument("collection", help="Agent collection folder, usually agents")
    explain.add_argument("agent", help="Agent name from yoke.yaml")
    explain.add_argument("--provider", help="Provider surface, such as codex:app")
    explain.add_argument("--cwd", default=".", help="Working directory for the harness")
    explain.add_argument(
        "--feature",
        action="append",
        default=[],
        help="Additional feature to require in the explanation",
    )
    explain.set_defaults(handler=explain_command)

    status = subcommands.add_parser(
        "status",
        help="Check readiness and capability semantics for a named agent",
    )
    status.add_argument("collection", help="Agent collection folder, usually agents")
    status.add_argument("agent", help="Agent name from yoke.yaml")
    status.add_argument("--provider", help="Provider surface, such as codex:app")
    status.add_argument("--cwd", default=".", help="Working directory for the harness")
    status.set_defaults(handler=status_command)

    install = subcommands.add_parser(
        "install",
        help="Write provider-native files for a named collection agent",
    )
    install.add_argument("collection", help="Agent collection folder, usually agents")
    install.add_argument("agent", help="Agent name from yoke.yaml")
    install.add_argument("--provider", help="Provider surface, such as codex:cli")
    install.add_argument("--surface", help="Provider surface, such as codex_cli")
    install.add_argument("--target", default=".", help="Directory to write into")
    install.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing provider files",
    )
    install.set_defaults(handler=install_command)

    runs = subcommands.add_parser("runs", help="List stored Yoke runs")
    runs.add_argument("--store", default=".yoke", help="Yoke store root")
    runs.set_defaults(handler=runs_command)

    show = subcommands.add_parser("show", help="Show one stored Yoke run record")
    show.add_argument("id", help="Run id")
    show.add_argument("--store", default=".yoke", help="Yoke store root")
    show.set_defaults(handler=show_command)

    events = subcommands.add_parser("events", help="Print stored Yoke run events")
    events.add_argument("id", help="Run id")
    events.add_argument("--store", default=".yoke", help="Yoke store root")
    events.set_defaults(handler=events_command)

    return parser


def run_command(args: argparse.Namespace) -> int:
    """Run one collection agent and store the result."""

    return asyncio.run(run_command_async(args))


async def run_command_async(args: argparse.Namespace) -> int:
    """Async implementation for `yoke run`."""

    harness = harness_from_collection_args(args)
    result = await harness.run(args.prompt)
    record = RunStore.at(args.store).record(
        result,
        agent=args.agent,
        collection=args.collection,
        cwd=harness.cwd,
    )
    print(record.id)
    if result.output:
        print(result.output)
    return 0


def workflow_command(args: argparse.Namespace) -> int:
    """Run one named workflow and store the result."""

    return asyncio.run(workflow_command_async(args))


async def workflow_command_async(args: argparse.Namespace) -> int:
    """Async implementation for `yoke workflow`."""

    harness = harness_from_collection_args(args)
    options = workflow_options_from_args(args)
    prompt = workflow_prompt_from_args(args)
    result = await harness.workflow(args.workflow, prompt, options)
    record = RunStore.at(args.store).record(
        result,
        agent=args.agent,
        collection=args.collection,
        cwd=harness.cwd,
    )
    print(record.id)
    if result.output:
        print(result.output)
    return 0


def explain_command(args: argparse.Namespace) -> int:
    """Explain selected-surface lowering for a collection agent."""

    harness = harness_from_collection_args(args)
    explanation = harness.explain(features=tuple(args.feature))
    print(json.dumps(explanation.model_dump(mode="json"), indent=2, sort_keys=True))
    return 0


def status_command(args: argparse.Namespace) -> int:
    """Check readiness and capability semantics for a collection agent."""

    return asyncio.run(status_command_async(args))


async def status_command_async(args: argparse.Namespace) -> int:
    """Async implementation for `yoke status`."""

    harness = harness_from_collection_args(args)
    status = await harness.status()
    print(json.dumps(status_json(status), indent=2, sort_keys=True))
    return 0


def install_command(args: argparse.Namespace) -> int:
    """Write provider-native bundle files for a collection agent."""

    collection = Collection.from_folder(args.collection)
    provider = args.provider or collection.default_provider
    if provider is None:
        raise SystemExit(
            "provider is required: pass --provider or set default_provider "
            "in agents/yoke.yaml"
        )
    provider_part, surface_part = split_provider_surface(provider, args.surface)
    surface = normalize_provider_surface(provider_part, surface_part)
    agent = collection.agent(args.agent)
    bundle = agent.bundle(provider=provider_part, surface=surface)
    written = bundle.write(args.target, overwrite=args.overwrite)
    if not written:
        print("no artifacts")
        return 0
    for path in written:
        print(path)
    return 0


def runs_command(args: argparse.Namespace) -> int:
    """List stored run records."""

    for record in RunStore.at(args.store).list():
        surface = f":{record.surface}" if record.surface else ""
        agent = f" agent={record.agent}" if record.agent else ""
        print(f"{record.id} {record.provider}{surface} {record.status}{agent}")
    return 0


def show_command(args: argparse.Namespace) -> int:
    """Print one run record as JSON."""

    record = RunStore.at(args.store).load(args.id)
    print(json.dumps(record.model_dump(mode="json"), indent=2, sort_keys=True))
    return 0


def events_command(args: argparse.Namespace) -> int:
    """Print one run's event JSONL."""

    store = RunStore.at(args.store)
    record = store.load(args.id)
    path = record.events_path or record.run_dir / RUN_EVENTS_FILE
    if not path.exists():
        return 0
    print(path.read_text(), end="")
    return 0


def load_record_json(store: RunStore, run_id: str) -> dict[str, Any]:
    """Load a raw record JSON object."""

    path = store.runs_dir / run_id / RUN_RECORD_FILE
    return json.loads(path.read_text())


def harness_from_collection_args(args: argparse.Namespace) -> Harness:
    """Load a named collection agent and bind it to a harness."""

    collection = Collection.from_folder(args.collection)
    provider = args.provider or collection.default_provider
    if provider is None:
        raise SystemExit(
            "provider is required: pass --provider or set default_provider "
            "in agents/yoke.yaml"
        )
    return Harness(
        provider,
        agent=collection.agent(args.agent),
        cwd=Path(args.cwd),
    )


def status_json(status: Any) -> dict[str, Any]:
    """Return the full JSON-friendly status payload users need to inspect."""

    return {
        "readiness": status.readiness.model_dump(mode="json"),
        "report": status.report.model_dump(mode="json"),
        "goal": status.goal.model_dump(mode="json"),
        "workflow": status.workflow.model_dump(mode="json"),
        "subagents": status.subagents.model_dump(mode="json"),
        "skills": status.skills.model_dump(mode="json"),
        "control": status.control.model_dump(mode="json"),
        "permissions": status.permissions.model_dump(mode="json"),
        "history": status.history.model_dump(mode="json"),
        "exposure": status.exposure.model_dump(mode="json"),
    }


def workflow_options_from_args(args: argparse.Namespace) -> WorkflowOptions:
    """Return workflow options represented by CLI flags."""

    data: dict[str, Any] = {}
    if args.native:
        data["native"] = True
    if args.resume:
        data["resume"] = args.resume
    if args.concurrency is not None:
        data["concurrency"] = args.concurrency
    if args.channel is not None:
        data["channel"] = args.channel
    if args.fail_fast is not None:
        data["fail_fast"] = args.fail_fast
    return WorkflowOptions.model_validate(data)


def workflow_prompt_from_args(args: argparse.Namespace) -> Any:
    """Return the workflow input represented by positional prompt or --args."""

    if args.args is not None and args.prompt is not None:
        raise SystemExit("workflow accepts either prompt or --args, not both")
    if args.args is None:
        return args.prompt or ""
    try:
        return json.loads(args.args)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"workflow --args must be valid JSON: {exc}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
