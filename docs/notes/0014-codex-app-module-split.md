# Codex app-server module split

The first `CodexAppServer` implementation proved the surface against real Codex, but `src/yoke/providers/codex_app_server.py` had grown into a mixed transport, RPC, policy, prompt, goal, and event-mapping file. That shape was useful while discovering the protocol, but it was not good enough for a reusable package.

The public import remains stable:

```python
from yoke.providers import CodexAppServer
```

Internal app-server code now lives under `src/yoke/providers/codex_app/`:

- `process.py`: subprocess ownership, JSONL reading, process-group termination.
- `rpc.py`: client request/response flow and noninteractive server-request responses.
- `events.py`: app-server notification mapping into Yoke `Event`, `Tool`, and `Usage`.
- `policy.py`: Yoke `Permissions` to Codex approval/sandbox settings.
- `prompts.py`: Yoke agent instructions and compiled local skills to developer instructions.
- `goals.py`: Yoke `Goal` to Codex app-server goal payloads and back.
- `fields.py`: typed JSON field helpers used at the protocol edge.

This follows the CodeAlmanac rule that raw external shapes stop at the normalization boundary. Provider JSON is decoded by small edge helpers, then projected into Yoke models. It also keeps the package future-proof for CodeAlmanac integration: CodeAlmanac can import `CodexAppServer` as a provider adapter dependency without inheriting a monolithic protocol file.

Real smokes after the split:

- async app-server one-shot returned `yoke app server works`,
- sync app-server one-shot returned `yoke sync works`,
- tool/usage event smoke returned project name `yoke`, with at least one structured `Tool` and non-null `Usage`.
