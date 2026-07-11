from __future__ import annotations

import json
from pathlib import Path

import yoke.cli as cli
from yoke import (
    Agent,
    Readiness,
    Run,
    Status,
    WorkflowRun,
    report_for,
)
from yoke import (
    Harness as RealHarness,
)


class FakeHarness:
    """Small stand-in for CLI contract tests."""

    calls: list[FakeHarness] = []

    def __init__(self, provider: str, *, agent: Agent, cwd: Path):
        self.provider = provider
        self.agent = agent
        self.cwd = cwd
        self.prompt: str | None = None
        FakeHarness.calls.append(self)

    async def run(self, prompt: str) -> Run:
        self.prompt = prompt
        return Run(provider="codex", surface="codex_app_server", output="done")

    async def workflow(self, workflow: str, prompt=None, options=None) -> WorkflowRun:
        self.workflow_name = workflow
        self.workflow_prompt = prompt
        self.workflow_options = options
        return WorkflowRun(
            workflow=workflow,
            provider="codex",
            surface="codex_app_server",
            output="workflow done",
        )

    def explain(self, options=None, *, features=(), channel=None, runnable=True):
        return RealHarness(
            self.provider,
            agent=self.agent,
            cwd=self.cwd,
        ).explain(
            options,
            features=features,
            channel=channel,
            runnable=runnable,
        )

    async def status(self) -> Status:
        return Status(
            readiness=Readiness(
                provider="codex",
                surface="codex_app_server",
                available=True,
                message="fake ready",
            ),
            report=report_for("codex", "codex_app_server"),
        )


def write_collection(root: Path) -> None:
    agents = root / "agents"
    reviewer = agents / "codealmanac"
    reviewer.mkdir(parents=True)
    (agents / "yoke.yaml").write_text(
        "default_provider: codex:app\n"
        "agents:\n"
        "  codealmanac: codealmanac\n"
    )
    (reviewer / "agent.yaml").write_text("description: Maintains CodeAlmanac.\n")
    (reviewer / "instructions.md").write_text("Be careful.\n")


def write_install_collection(root: Path) -> None:
    agents = root / "agents"
    reviewer = agents / "codealmanac"
    subagent = reviewer / "subagents" / "reviewer"
    skill = reviewer / "skills" / "research"
    subagent.mkdir(parents=True)
    skill.mkdir(parents=True)
    (agents / "yoke.yaml").write_text(
        "default_provider: codex:cli\n"
        "agents:\n"
        "  codealmanac: codealmanac\n"
    )
    (reviewer / "agent.yaml").write_text("description: Maintains CodeAlmanac.\n")
    (reviewer / "instructions.md").write_text("Coordinate work.\n")
    (subagent / "agent.yaml").write_text("description: Reviews patches.\n")
    (subagent / "instructions.md").write_text("Find correctness bugs.\n")
    (skill / "SKILL.md").write_text(
        "---\n"
        "name: research\n"
        "description: Use primary sources.\n"
        "---\n"
        "Research from docs.\n"
    )


def write_workflow_collection(root: Path) -> None:
    agents = root / "agents"
    reviewer = agents / "codealmanac"
    workflow = reviewer / "workflows" / "review"
    workflow.mkdir(parents=True)
    (agents / "yoke.yaml").write_text(
        "default_provider: codex:app\n"
        "agents:\n"
        "  codealmanac: codealmanac\n"
    )
    (reviewer / "agent.yaml").write_text("description: Maintains CodeAlmanac.\n")
    (reviewer / "instructions.md").write_text("Coordinate work.\n")
    (workflow / "draft.md").write_text("Draft for {input}.\n")


def test_cli_run_loads_collection_runs_agent_and_records_result(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    write_collection(tmp_path)
    monkeypatch.setattr(cli, "Harness", FakeHarness)

    exit_code = cli.main(
        [
            "run",
            str(tmp_path / "agents"),
            "codealmanac",
            "Review this repo",
            "--cwd",
            str(tmp_path),
            "--store",
            str(tmp_path / ".yoke"),
        ]
    )

    output = capsys.readouterr().out
    record_id = output.splitlines()[0]
    record = json.loads(
        (tmp_path / ".yoke" / "runs" / record_id / "record.json").read_text()
    )

    assert exit_code == 0
    assert "done" in output
    assert FakeHarness.calls[-1].provider == "codex:app"
    assert FakeHarness.calls[-1].prompt == "Review this repo"
    assert record["agent"] == "codealmanac"
    assert record["collection"] == str(tmp_path / "agents")
    assert record["cwd"] == str(tmp_path)


def test_cli_run_accepts_provider_override(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_collection(tmp_path)
    monkeypatch.setattr(cli, "Harness", FakeHarness)

    cli.main(
        [
            "run",
            str(tmp_path / "agents"),
            "codealmanac",
            "Review this repo",
            "--provider",
            "claude:sdk",
            "--store",
            str(tmp_path / ".yoke"),
        ]
    )

    assert FakeHarness.calls[-1].provider == "claude:sdk"


def test_cli_workflow_loads_collection_runs_workflow_and_records_result(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    write_workflow_collection(tmp_path)
    monkeypatch.setattr(cli, "Harness", FakeHarness)

    exit_code = cli.main(
        [
            "workflow",
            str(tmp_path / "agents"),
            "codealmanac",
            "review",
            "Bundle loader",
            "--store",
            str(tmp_path / ".yoke"),
            "--concurrency",
            "2",
            "--no-fail-fast",
            "--channel",
            "app_server",
        ]
    )

    output = capsys.readouterr().out
    record_id = output.splitlines()[0]
    record = json.loads(
        (tmp_path / ".yoke" / "runs" / record_id / "record.json").read_text()
    )
    result = json.loads(
        (tmp_path / ".yoke" / "runs" / record_id / "result.json").read_text()
    )

    assert exit_code == 0
    assert "workflow done" in output
    assert FakeHarness.calls[-1].workflow_name == "review"
    assert FakeHarness.calls[-1].workflow_prompt == "Bundle loader"
    assert FakeHarness.calls[-1].workflow_options.concurrency == 2
    assert FakeHarness.calls[-1].workflow_options.channel == "app_server"
    assert FakeHarness.calls[-1].workflow_options.fail_fast is False
    assert record["kind"] == "workflow"
    assert record["agent"] == "codealmanac"
    assert result["workflow"] == "review"


def test_cli_workflow_accepts_structured_args(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_workflow_collection(tmp_path)
    monkeypatch.setattr(cli, "Harness", FakeHarness)

    assert (
        cli.main(
            [
                "workflow",
                str(tmp_path / "agents"),
                "codealmanac",
                "review",
                "--args",
                '{"scope":"routes"}',
                "--store",
                str(tmp_path / ".yoke"),
            ]
        )
        == 0
    )

    assert FakeHarness.calls[-1].workflow_prompt == {"scope": "routes"}


def test_cli_workflow_rejects_prompt_and_structured_args(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_workflow_collection(tmp_path)
    monkeypatch.setattr(cli, "Harness", FakeHarness)

    try:
        cli.main(
            [
                "workflow",
                str(tmp_path / "agents"),
                "codealmanac",
                "review",
                "Bundle loader",
                "--args",
                '{"scope":"routes"}',
            ]
        )
    except SystemExit as error:
        assert "either prompt or --args" in str(error)
    else:
        raise AssertionError("expected SystemExit")


def test_cli_runs_show_and_events_read_store(tmp_path: Path, capsys) -> None:
    store = tmp_path / ".yoke"
    record = cli.RunStore.at(store).record(
        Run(provider="codex", surface="codex_app_server", output="done"),
        id="run_demo",
        agent="codealmanac",
        collection="agents",
        cwd=tmp_path,
    )

    assert cli.main(["runs", "--store", str(store)]) == 0
    runs_output = capsys.readouterr().out
    assert "run_demo codex:codex_app_server succeeded agent=codealmanac" in runs_output

    assert cli.main(["show", "run_demo", "--store", str(store)]) == 0
    show_output = capsys.readouterr().out
    assert json.loads(show_output)["id"] == "run_demo"

    assert cli.main(["events", "run_demo", "--store", str(store)]) == 0
    assert capsys.readouterr().out == ""
    assert record.event_count == 0


def test_cli_explain_loads_collection_and_prints_feature_plan(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    write_collection(tmp_path)
    monkeypatch.setattr(cli, "Harness", FakeHarness)

    assert (
        cli.main(
            [
                "explain",
                str(tmp_path / "agents"),
                "codealmanac",
                "--feature",
                "goal_loop",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["provider"] == "codex"
    assert payload["surface"] == "codex_app_server"
    assert "goal_loop" in payload["features"]


def test_cli_status_prints_readiness_and_semantic_reports(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    write_collection(tmp_path)
    monkeypatch.setattr(cli, "Harness", FakeHarness)

    assert cli.main(["status", str(tmp_path / "agents"), "codealmanac"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["readiness"]["available"] is True
    assert payload["readiness"]["message"] == "fake ready"
    assert payload["goal"]["mode"] == "native_thread"
    assert payload["workflow"]["mode"] == "yoke_portable"
    assert payload["subagents"]["mode"] == "provider_native"
    assert payload["skills"]["mcp"] == "native"


def test_cli_install_writes_provider_bundle_from_collection(tmp_path: Path) -> None:
    write_install_collection(tmp_path)
    target = tmp_path / "repo"

    assert (
        cli.main(
            [
                "install",
                str(tmp_path / "agents"),
                "codealmanac",
                "--target",
                str(target),
            ]
        )
        == 0
    )

    assert (target / ".codex" / "agents" / "reviewer.toml").exists()
    assert (target / ".agents" / "skills" / "research" / "SKILL.md").exists()


def test_cli_install_accepts_provider_surface_override(tmp_path: Path) -> None:
    write_install_collection(tmp_path)
    target = tmp_path / "repo"

    assert (
        cli.main(
            [
                "install",
                str(tmp_path / "agents"),
                "codealmanac",
                "--provider",
                "claude:sdk",
                "--target",
                str(target),
            ]
        )
        == 0
    )

    assert (target / ".claude" / "agents" / "reviewer.md").exists()
    assert (target / ".claude" / "skills" / "research" / "SKILL.md").exists()
