# Source Map

## Yoke

- `src/yoke/loader.py`: Yoke folder parsing.
- `src/yoke/folders.py`: Yoke folder serialization.
- `src/yoke/artifacts.py`: explicit `.codex` and `.claude` bundle generation.
- `src/yoke/providers/codex_app/prompts.py`: Codex subagent prompt compilation.
- `src/yoke/providers/codex_app/skills.py`: Codex native skill roots.
- `src/yoke/providers/codex_app_server.py`: app-server JSON-RPC lowering.
- `src/yoke/providers/claude.py`: Claude SDK options and agent definitions.
- `src/yoke/providers/claude_plugins.py`: Claude local plugin roots.
- `src/yoke/surfaces.py`: declared capability matrix.
- `src/yoke/status.py`: user-facing semantic reports.
- `src/yoke/store.py`: optional normalized result and event persistence.

## CodeAlmanac

- `src/codealmanac/agents/yoke.yaml`: collection manifest.
- `src/codealmanac/agents/{build,ingest,garden}/`: canonical definitions.
- `src/codealmanac/agents/catalog.py`: collection loader.
- `src/codealmanac/integrations/harnesses/yoke.py`: provider boundary.

## Provider sources

- <https://code.claude.com/docs/en/agent-sdk/subagents>
- <https://code.claude.com/docs/en/agent-sdk/skills>
- <https://code.claude.com/docs/en/agent-sdk/plugins>
- <https://code.claude.com/docs/en/agent-sdk/sessions>
- <https://code.claude.com/docs/en/agent-sdk/hooks>
- <https://code.claude.com/docs/en/agent-sdk/mcp>
- <https://code.claude.com/docs/en/agent-sdk/permissions>
- <https://developers.openai.com/codex/app-server>
- <https://developers.openai.com/codex/subagents>
- <https://developers.openai.com/codex/skills>
- <https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md>
- Local checkout: `/Users/rohan/Desktop/Projects/openai-codex`
