from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from yoke import (
    Agent,
    Feature,
    Harness,
    Run,
    RunOptions,
    RunStatus,
    Session,
    Step,
    Support,
    Workflow,
    clear_adapters,
    register,
)
from yoke.capabilities import Capabilities
from yoke.providers.claude import collect_messages
from yoke.providers.codex import Codex
from yoke.structured import parse_output, parse_output_data, provider_schema


class Summary(BaseModel):
    summary: str
    changed: bool = False


class Detail(BaseModel):
    label: str


class NestedSummary(BaseModel):
    detail: Detail
    items: list[Detail]


class NestedMappingSummary(BaseModel):
    details: dict[str, Detail]


class ResultMessage:
    structured_output = {"summary": "ok", "changed": False}
    result = None


class SystemMessage:
    subtype = "init"
    data = {"session_id": "provider-session"}


class FakeStructuredAdapter:
    provider = "claude"
    surface = "fake-structured"
    capabilities = Capabilities.from_map({Feature.WORKFLOW: Support.EMULATED})

    async def check(self, harness):  # pragma: no cover - unused
        raise NotImplementedError

    async def run(self, harness, prompt, options):
        return Run(
            provider="claude",
            output='{"summary": "ok"}',
            data={"summary": "ok"},
        )

    async def models(self, harness):  # pragma: no cover - unused
        raise NotImplementedError

    async def start(self, harness, options):  # pragma: no cover - unused
        raise NotImplementedError

    async def send(self, session, turn, options):  # pragma: no cover - unused
        raise NotImplementedError

    async def stream(self, session, turn, options):  # pragma: no cover - unused
        if False:
            yield None

    async def get_goal(self, session):  # pragma: no cover - unused
        return None

    async def set_goal(self, session, goal):  # pragma: no cover - unused
        return session

    async def clear_goal(self, session):  # pragma: no cover - unused
        return session

    async def close(self, session):  # pragma: no cover - unused
        return None


class FakeCodexCli:
    async def run(self, **kwargs):
        self.kwargs = kwargs
        yield {"type": "thread.started", "thread_id": "thread-1"}
        yield {
            "type": "item.completed",
            "item": {
                "type": "agent_message",
                "text": '{"changed": true}',
            },
        }
        yield {"type": "turn.completed", "usage": {}}


async def messages():
    yield ResultMessage()


@pytest.mark.asyncio
async def test_claude_one_shot_timeout_returns_partial_typed_failure() -> None:
    async def slow_messages():
        yield type(
            "AssistantMessage",
            (),
            {"content": [type("TextBlock", (), {"text": "partial"})()]},
        )()
        await asyncio.sleep(1)

    result = await collect_messages(
        "claude",
        slow_messages(),
        timeout_seconds=0.01,
    )

    assert result.status is RunStatus.FAILED
    assert result.output == "partial"
    assert result.failure is not None
    assert result.failure.code == "timeout"


async def session_messages():
    yield SystemMessage()
    yield ResultMessage()


def test_parse_output_data_only_when_schema_requested() -> None:
    schema: dict[str, Any] = {"type": "object"}

    assert parse_output_data('{"summary": "ok"}', schema) == {"summary": "ok"}
    assert parse_output_data("not json", schema) is None
    assert parse_output_data('{"summary": "ok"}', None) is None


def test_pydantic_output_schema_validates_data() -> None:
    data = parse_output_data('{"summary": "ok", "changed": true}', Summary)

    assert isinstance(data, Summary)
    assert data.summary == "ok"
    assert data.changed is True
    assert provider_schema(Summary)["properties"]["summary"]["type"] == "string"


def test_pydantic_output_schema_is_recursively_strict_for_providers() -> None:
    schema = provider_schema(NestedSummary)

    assert schema is not None
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["detail", "items"]
    assert schema["$defs"]["Detail"]["additionalProperties"] is False
    assert schema["$defs"]["Detail"]["required"] == ["label"]


def test_provider_schema_rejects_nested_mapping_instead_of_changing_meaning() -> None:
    with pytest.raises(
        ValueError,
        match="strict structured output cannot represent mapping objects",
    ):
        provider_schema(NestedMappingSummary)


def test_provider_schema_rejects_explicit_additional_properties_schema() -> None:
    with pytest.raises(ValueError, match="cannot represent mapping objects"):
        provider_schema(
            {
                "type": "object",
                "properties": {
                    "labels": {
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                    }
                },
            }
        )


def test_pydantic_output_schema_validation_failure_is_typed() -> None:
    parsed = parse_output('{"changed": true}', Summary)

    assert parsed.data is None
    assert parsed.failure is not None
    assert parsed.failure.code == "invalid_structured_output"


def test_codex_structured_validation_failure_returns_failed_run() -> None:
    asyncio.run(run_codex_structured_failure_check())


def test_raw_json_schema_is_validated() -> None:
    schema = {
        "type": "object",
        "properties": {"count": {"type": "integer"}},
        "required": ["count"],
        "additionalProperties": False,
    }

    valid = parse_output('{"count": 2}', schema)
    invalid = parse_output('{"count": "two"}', schema)

    assert valid.data == {"count": 2}
    assert invalid.failure is not None
    assert invalid.failure.code == "invalid_structured_output"


async def run_codex_structured_failure_check() -> None:
    adapter = Codex()
    adapter.cli = FakeCodexCli()
    harness = Harness(
        provider="codex",
        surface="codex_cli",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    result = await adapter.run(
        harness,
        "return structured output",
        RunOptions(output_schema=Summary),
    )

    assert result.status is RunStatus.FAILED
    assert result.failure is not None
    assert result.failure.code == "invalid_structured_output"


def test_codex_cli_run_model_override_is_forwarded() -> None:
    asyncio.run(run_codex_model_override_check())


async def run_codex_model_override_check() -> None:
    adapter = Codex()
    adapter.cli = FakeCodexCli()
    harness = Harness(
        provider="codex",
        surface="codex_cli",
        agent=Agent(instructions="test", model="agent-model"),
        cwd=Path.cwd(),
    )

    await adapter.run(harness, "test", RunOptions(model="run-model"))

    assert adapter.cli.kwargs["model"] == "run-model"


def test_claude_native_structured_output_sets_run_data() -> None:
    result = asyncio.run(
        collect_messages(
            "claude",
            messages(),
            output_schema=Summary,
            requested_model="sonnet",
        )
    )

    assert result.data == Summary(summary="ok", changed=False)
    assert result.output == "{'summary': 'ok', 'changed': False}"
    assert result.requested_model == "sonnet"


def test_claude_collect_messages_preserves_provider_session_id() -> None:
    session = Session(
        provider="claude",
        surface="claude_python_sdk",
        id="local-session",
    )

    result = asyncio.run(collect_messages("claude", session_messages(), session))

    assert result.session is not None
    assert result.session.id == "local-session"
    assert result.session.provider_session_id == "provider-session"
    assert result.events[0].kind == "provider_session"


def test_claude_collect_messages_deduplicates_final_result_text() -> None:
    class TextBlock:
        text = "finished"

    class AssistantMessage:
        content = [TextBlock()]

    class ResultMessage:
        result = "finished"
        structured_output = None
        is_error = False
        subtype = "success"

    async def duplicate_messages():
        yield AssistantMessage()
        yield ResultMessage()

    result = asyncio.run(collect_messages("claude", duplicate_messages()))

    assert [event.message for event in result.events if event.kind == "text"] == [
        "finished"
    ]
    assert result.output == "finished"


def test_claude_waits_for_native_background_task_and_final_parent_result() -> None:
    class TextBlock:
        def __init__(self, text: str) -> None:
            self.text = text

    class AssistantMessage:
        def __init__(self, text: str) -> None:
            self.content = [TextBlock(text)]

    class TaskStartedMessage:
        task_id = "task-1"
        description = "Review changes"
        task_type = "local_agent"

    class TaskNotificationMessage:
        task_id = "task-1"
        status = "completed"
        output_file = "/tmp/task.md"
        summary = "Review complete"

    class ResultMessage:
        structured_output = None
        is_error = False
        subtype = "success"

        def __init__(self, result: str) -> None:
            self.result = result

    async def background_messages():
        yield TaskStartedMessage()
        yield AssistantMessage("I will relay the review.")
        yield ResultMessage("I will relay the review.")
        yield TaskNotificationMessage()
        yield AssistantMessage("Final parent answer.")
        yield ResultMessage("Final parent answer.")
        raise AssertionError("collector read beyond the terminal parent result")

    result = asyncio.run(
        collect_messages(
            "claude",
            background_messages(),
            stop_when_settled=True,
        )
    )

    assert result.output == "Final parent answer."
    assert any(event.message == "Review complete" for event in result.events)


def test_claude_same_text_in_intermediate_and_final_phases_is_not_duplicated() -> None:
    class TextBlock:
        def __init__(self, text: str) -> None:
            self.text = text

    class AssistantMessage:
        def __init__(self, text: str) -> None:
            self.content = [TextBlock(text)]

    class TaskStartedMessage:
        task_id = "task-1"
        description = "Check"
        task_type = "local_agent"

    class TaskUpdatedMessage:
        task_id = "task-1"
        status = "running"
        patch = {"status": "running"}

    class TaskNotificationMessage:
        task_id = "task-1"
        status = "completed"
        output_file = "/tmp/task.md"
        summary = "done"

    class ResultMessage:
        result = "CLAUDE_OK"
        structured_output = None
        is_error = False
        subtype = "success"

    async def repeated_phase_messages():
        yield TaskStartedMessage()
        yield AssistantMessage("CLAUDE_OK")
        yield ResultMessage()
        yield TaskUpdatedMessage()
        yield TaskNotificationMessage()
        yield AssistantMessage("CLAUDE_OK\n")
        yield ResultMessage()

    result = asyncio.run(
        collect_messages(
            "claude",
            repeated_phase_messages(),
            stop_when_settled=True,
        )
    )

    assert result.output == "CLAUDE_OK"
    assistant_text = [
        event
        for event in result.events
        if event.kind == "text" and type(event.raw).__name__ == "AssistantMessage"
    ]
    assert len(assistant_text) == 2


def test_claude_one_shot_collector_exhausts_provider_iterator() -> None:
    class ResultMessage:
        result = "done"
        structured_output = None
        is_error = False
        subtype = "success"

    exhausted: list[bool] = []

    async def one_shot_messages():
        yield ResultMessage()
        exhausted.append(True)

    result = asyncio.run(collect_messages("claude", one_shot_messages()))

    assert result.output == "done"
    assert exhausted == [True]


def test_claude_one_shot_returns_only_last_completed_response_segment() -> None:
    class TextBlock:
        def __init__(self, text: str) -> None:
            self.text = text

    class AssistantMessage:
        def __init__(self, text: str) -> None:
            self.content = [TextBlock(text)]

    class TaskStartedMessage:
        task_id = "task-1"
        description = "Review"
        task_type = "local_agent"

    class TaskNotificationMessage:
        task_id = "task-1"
        status = "completed"
        output_file = "/tmp/review.md"
        summary = "done"

    class ResultMessage:
        structured_output = None
        is_error = False
        subtype = "success"

        def __init__(self, result: str) -> None:
            self.result = result

    exhausted: list[bool] = []

    async def one_shot_background_messages():
        yield TaskStartedMessage()
        yield AssistantMessage("I've asked the reviewer.")
        yield ResultMessage("I've asked the reviewer.")
        yield TaskNotificationMessage()
        yield AssistantMessage("ONESHOT_OK")
        yield AssistantMessage("The reviewer returned successfully.")
        yield ResultMessage("ONESHOT_OK\nThe reviewer returned successfully.")
        exhausted.append(True)

    result = asyncio.run(
        collect_messages("claude", one_shot_background_messages())
    )

    assert result.output == "ONESHOT_OK\nThe reviewer returned successfully."
    assert exhausted == [True]
    assert any(
        event.message == "I've asked the reviewer." for event in result.events
    )


def test_claude_collect_messages_delivers_each_returned_event_once() -> None:
    class TextBlock:
        text = "finished"

    class AssistantMessage:
        content = [TextBlock()]

    class ResultMessage:
        result = "finished"
        structured_output = None
        is_error = False
        subtype = "success"

    observed = []

    async def callback_messages():
        yield AssistantMessage()
        assert [event.message for event in observed] == ["finished"]
        yield ResultMessage()

    result = asyncio.run(
        collect_messages(
            "claude",
            callback_messages(),
            surface="claude_python_sdk",
            on_event=observed.append,
        )
    )

    assert tuple(observed) == result.events
    assert [event.message for event in observed if event.kind == "text"] == [
        "finished"
    ]


def test_claude_collect_messages_deduplicates_fragmented_final_result_text() -> None:
    class TextBlock:
        def __init__(self, text: str) -> None:
            self.text = text

    class AssistantMessage:
        content = [TextBlock("finished"), TextBlock(" cleanly")]

    class ResultMessage:
        result = "finished cleanly"
        structured_output = None
        is_error = False
        subtype = "success"

    async def fragmented_messages():
        yield AssistantMessage()
        yield ResultMessage()

    result = asyncio.run(collect_messages("claude", fragmented_messages()))

    assert [event.message for event in result.events if event.kind == "text"] == [
        "finished",
        " cleanly",
    ]
    assert result.output == "finished\n cleanly"


def test_claude_collect_messages_uses_provider_error_status() -> None:
    class ResultMessage:
        result = "request failed"
        structured_output = None
        is_error = True
        subtype = "error_during_execution"
        errors = ["provider failed"]

    async def failed_messages():
        yield ResultMessage()

    result = asyncio.run(collect_messages("claude", failed_messages()))

    assert not result.ok
    assert result.failure is not None
    assert result.failure.code == "error_during_execution"
    assert result.failure.message == "provider failed"


def test_claude_collect_messages_fails_on_terminal_provider_evidence() -> None:
    class ResultMessage:
        result = "request failed"
        structured_output = None
        is_error = False
        subtype = "success"
        errors = ["upstream unavailable"]
        api_error_status = 503

    async def failed_messages():
        yield ResultMessage()

    result = asyncio.run(collect_messages("claude", failed_messages()))

    assert not result.ok
    assert result.failure is not None
    assert result.failure.code == "provider_error"
    assert result.failure.message == "upstream unavailable"


def test_claude_collect_messages_fails_on_permission_denials() -> None:
    class ResultMessage:
        result = "operation denied"
        structured_output = None
        is_error = False
        subtype = "success"
        errors = None
        api_error_status = None
        permission_denials = [{"tool": "Bash", "reason": "not allowed"}]

    async def denied_messages():
        yield ResultMessage()

    result = asyncio.run(collect_messages("claude", denied_messages()))

    assert not result.ok
    assert result.failure is not None
    assert result.failure.code == "permission_denied"
    assert result.failure.message == "Claude denied 1 tool request"


def test_claude_native_structured_validation_failure_returns_failed_run() -> None:
    class ResultMessage:
        structured_output = {"summary": 42, "changed": False}
        result = None
        is_error = False

    async def invalid_messages():
        yield ResultMessage()

    result = asyncio.run(
        collect_messages("claude", invalid_messages(), output_schema=Summary)
    )

    assert not result.ok
    assert result.data is None
    assert result.failure is not None
    assert result.failure.code == "invalid_structured_output"
    assert result.failure.message == "provider structured output did not match schema"


def test_claude_result_text_only_deduplicates_immediate_terminal_copy() -> None:
    class TextBlock:
        def __init__(self, text: str) -> None:
            self.text = text

    class AssistantMessage:
        def __init__(self, text: str) -> None:
            self.content = [TextBlock(text)]

    class ResultMessage:
        result = "repeated"
        structured_output = None
        is_error = False
        subtype = "success"

    async def messages_with_unrelated_repeat():
        yield AssistantMessage("repeated")
        yield AssistantMessage("different")
        yield ResultMessage()

    result = asyncio.run(
        collect_messages("claude", messages_with_unrelated_repeat())
    )

    assert [event.message for event in result.events if event.kind == "text"] == [
        "repeated",
        "different",
        "repeated",
    ]


def test_workflow_output_includes_final_step_data() -> None:
    asyncio.run(run_workflow_data_check())


async def run_workflow_data_check() -> None:
    clear_adapters()
    register(FakeStructuredAdapter())
    harness = Harness(
        provider="claude",
        surface="fake-structured",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    result = await harness.workflow(
        Workflow(
            name="structured",
            steps=(Step(name="final", agent="main", prompt="{input}"),),
        ),
        "summarize",
    )

    assert result.data == {"summary": "ok"}
