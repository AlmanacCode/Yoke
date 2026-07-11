from __future__ import annotations

from yoke import (
    CodexApprovalDecision,
    CodexRequestPolicy,
    Event,
    EventKind,
    Request,
    RequestKind,
    RequestPolicy,
    Tool,
    ToolKind,
)
from yoke.providers.codex_app.rpc import ServerResponse


def approval_event(
    *,
    method: str = "item/commandExecution/requestApproval",
    kind: ToolKind = ToolKind.SHELL,
) -> Event:
    tool = Tool(kind=kind, title="approval")
    return Event(
        kind=EventKind.APPROVAL_REQUEST,
        tool_name=method,
        tool=tool,
        request=Request(
            kind=RequestKind.APPROVAL,
            method=method,
            tool=tool,
            input={},
        ),
    )


def user_input_event() -> Event:
    return Event(
        kind=EventKind.USER_INPUT_REQUEST,
        tool_name="AskUserQuestion",
        request=Request(
            kind=RequestKind.USER_INPUT,
            method="AskUserQuestion",
            input={"questions": []},
        ),
    )


def test_accept_all_accepts_modern_codex_app_server_approval_requests() -> None:
    policy = CodexRequestPolicy.accept_all()

    assert policy(approval_event(), ServerResponse(result={"decision": "decline"})) == {
        "decision": "accept"
    }


def test_accept_for_session_uses_codex_app_server_session_decision() -> None:
    policy = CodexRequestPolicy.accept_for_session()

    assert policy(approval_event(), None) == {"decision": "acceptForSession"}


def test_decline_all_is_explicit_for_modern_requests() -> None:
    policy = CodexRequestPolicy.decline_all()

    assert policy(approval_event(), None) == {"decision": "decline"}


def test_accept_tools_filters_by_normalized_tool_kind() -> None:
    policy = CodexRequestPolicy.accept_tools(ToolKind.SHELL)
    default = ServerResponse(result={"decision": "decline"})

    assert policy(approval_event(kind=ToolKind.SHELL), default) == {
        "decision": "accept"
    }
    assert policy(approval_event(kind=ToolKind.EDIT), default) is default


def test_non_approval_request_falls_back_to_yoke_default() -> None:
    policy = CodexRequestPolicy.accept_all()

    assert (
        policy(Event(kind=EventKind.TOOL_REQUEST, tool_name="item/tool/call"), None)
        is None
    )


def test_legacy_or_unknown_approval_methods_fall_back_to_yoke_default() -> None:
    policy = CodexRequestPolicy.accept_all()
    default = ServerResponse(result={"decision": "denied"})

    assert policy(approval_event(method="execCommandApproval"), default) is default


def test_decision_enum_is_public_and_string_like() -> None:
    assert str(CodexApprovalDecision.ACCEPT_FOR_SESSION) == "acceptForSession"


def test_request_policy_allows_matching_tool_kind() -> None:
    policy = RequestPolicy.allow_tools(ToolKind.SHELL)

    assert policy(approval_event(kind=ToolKind.SHELL)).decision == "allow"
    assert policy(approval_event(kind=ToolKind.EDIT)) is None


def test_request_policy_filters_by_request_kind() -> None:
    policy = RequestPolicy(
        response=RequestPolicy.allow_all().response,
        request_kinds=(RequestKind.USER_INPUT,),
    )

    assert policy(approval_event()) is None
    assert policy(user_input_event()).decision == "allow"
