# Run status is public contract

Date: 2026-07-04

The CodeAlmanac integration prep exposed a Yoke contract gap: `Run` returned provider output and events, but it did not say whether the run succeeded, failed, or was cancelled.

That was too implicit for embedding apps.

Yoke now has:

```python
class RunStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Failure(YokeModel):
    message: str
    code: str | None = None
    fix: str | None = None
    raw: str | None = None


class Run(YokeModel):
    provider: Provider
    status: RunStatus = RunStatus.SUCCEEDED
    output: str | None = None
    events: tuple[Event, ...] = ()
    session: Session | None = None
    usage: Usage | dict[str, Any] | None = None
    failure: Failure | None = None
```

The default is `succeeded` so existing adapters remain compatible while they return normal results.

Adapters may still raise exceptions for startup or programmer errors, but recoverable provider failures should eventually become `Run(status=RunStatus.FAILED, failure=Failure(...))` when the provider has enough structured information to preserve.

This matters for CodeAlmanac because its lifecycle layer already has a `HarnessRunStatus` and `HarnessFailure` contract. A Yoke-backed CodeAlmanac adapter should map Yoke status directly instead of inferring success from final text.

## Provider failure handling

Provider-declared turn failures should be data, not infrastructure exceptions.

Codex CLI `turn.failed` and stream `error` events now return:

```python
Run(
    status=RunStatus.FAILED,
    failure=Failure(message=...),
)
```

Codex app-server `error` notifications and `turn/completed` notifications with a turn error now set `TurnResult.failure`; the app-server adapter maps that to `Run(status=RunStatus.FAILED, failure=...)`.

Transport/setup failures still raise exceptions. A missing executable, a dead app-server process, a JSON-RPC timeout, or an unavailable optional dependency is not a normal provider turn result.
