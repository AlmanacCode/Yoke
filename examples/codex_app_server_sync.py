"""Run Codex app-server from synchronous Python."""

from pathlib import Path

from yoke import Agent, Harness, Permissions
from yoke.providers import CodexAppServer


agent = Agent(
    instructions="Reply with exactly: yoke sync works",
    permissions=Permissions(access="read", approval="never", network=False),
)

result = (
    Harness(provider="codex", surface="codex_app_server", agent=agent, cwd=Path.cwd())
    .with_adapter(CodexAppServer())
    .run_sync("Say the required phrase.")
)

print(result.output)
