# 0095 - Session fork starts with app-server

Re-read local provider docs and source:

- `../openai-codex/codex-rs/app-server/README.md`
- `../openai-codex/sdk/python/src/openai_codex/async_client.py`
- `../claude-agent-sdk-python/src/claude_agent_sdk/types.py`
- `../claude-agent-sdk-python/src/claude_agent_sdk/_internal/session_mutations.py`

Codex app-server exposes `thread/fork` as a live control-plane operation. It
creates a new thread id from an existing thread and can accept `ephemeral`,
`lastTurnId`, and `excludeTurns`.

Yoke now models this as `Feature.FORK` and exposes:

```python
fork = await session.fork()
fork = await session.fork(ForkOptions(ephemeral=True))
```

Current support:

- Codex app-server: native
- Codex CLI: unsupported
- Codex Python SDK: unknown
- Claude Python SDK: unknown

The unknowns are intentional. Codex Python SDK has `thread_fork`, but Yoke's SDK
adapter stores a runnable thread object, and the fork response ownership model
needs live verification before wiring. Claude SDK has `fork_session` helpers and
`fork_session=True` on resume, but Yoke currently does not capture/persist the
real Claude provider session id in a way that makes forking safe.

The first implementation tried to fork from an independent app-server process.
The live smoke failed with `no rollout found for thread id ...` because the
fresh process did not have the source thread loaded. Forking must happen on the
source session's loaded app-server process.

The app-server adapter now reference-counts shared processes. A forked Yoke
`Session` shares the source process, and closing one branch only terminates the
process after the last branch using it closes.

A second live smoke showed that `thread/fork` also needs a materialized rollout.
A thread created with `thread/start` but no completed turn failed with
`no rollout found for thread id ...`. The manual fork smoke now runs one tiny
source turn before forking.

The corrected live smoke passed:

```text
codex_app_server fork: source=019f2c96-c398-7082-92df-e417542ec6f1 fork=019f2c96-dcbe-7e51-909b-d5aa00496bb3
```
