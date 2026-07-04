"""Goal translation for Codex app-server."""

from __future__ import annotations

from pydantic import JsonValue

from yoke.models import Goal, GoalStatus
from yoke.providers.codex_app.fields import number_field, string_field


def app_goal_status(status: GoalStatus) -> str:
    mapping = {
        GoalStatus.ACTIVE: "active",
        GoalStatus.PAUSED: "paused",
        GoalStatus.BLOCKED: "blocked",
        GoalStatus.USAGE_LIMITED: "usageLimited",
        GoalStatus.BUDGET_LIMITED: "budgetLimited",
        GoalStatus.COMPLETE: "complete",
    }
    return mapping[status]


def yoke_goal(value: dict[str, JsonValue]) -> Goal | None:
    objective = string_field(value, "objective")
    if objective is None:
        return None
    return Goal(
        objective,
        status=yoke_goal_status(string_field(value, "status")),
        token_budget=number_field(value, "tokenBudget"),
        tokens_used=number_field(value, "tokensUsed"),
        time_used_seconds=number_field(value, "timeUsedSeconds"),
    )


def yoke_goal_status(value: str | None) -> GoalStatus:
    mapping = {
        "active": GoalStatus.ACTIVE,
        "paused": GoalStatus.PAUSED,
        "blocked": GoalStatus.BLOCKED,
        "usageLimited": GoalStatus.USAGE_LIMITED,
        "budgetLimited": GoalStatus.BUDGET_LIMITED,
        "complete": GoalStatus.COMPLETE,
    }
    return mapping.get(value or "", GoalStatus.ACTIVE)
