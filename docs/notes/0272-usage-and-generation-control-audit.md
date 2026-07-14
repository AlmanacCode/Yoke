# Usage and generation-control audit

Authenticated probes and provider-source inspection were completed on
2026-07-13 for Yoke's default surfaces.

## Usage contract

Codex app-server emits both `last` and `total` token usage. Yoke maps the
provider's last-call breakdown to input, cached input, output, reasoning
output, and `total_tokens`; it maps the thread's cumulative total to
`total_processed_tokens`. Cached input is a subset of input and reasoning
output is a subset of output.

Claude Agent SDK emits ordinary input, cache-creation input, cache-read input,
and output as disjoint categories. Yoke previously omitted cache creation and
therefore understated totals. Yoke now preserves cache creation separately and
sums all four categories. A final `ResultMessage` is the SDK query aggregate,
so its total is also `total_processed_tokens`. Claude does not expose a
separate reasoning-output count.

Claude subscription authentication is not a separate event surface. It uses
the same Claude Agent SDK message contract after Claude Code performs external
authentication.

Patched authenticated one-turn probes returned:

- Codex app-server: input 20,655; cached input 9,984; output 7; reasoning
  output 0; total and processed total 20,662.
- Claude Python SDK through Claude subscription auth: ordinary input 2; cache
  creation 7,611; cache read 0; output 78; total and processed total 7,691.

These values are evidence of shape and arithmetic, not stable token-count
expectations. Provider prompts and tool definitions make even a tiny agent turn
substantially larger than its visible user prompt.

## Temperature and model-output limits

| Surface | Temperature | Per-run model output-token limit | Evidence |
| --- | --- | --- | --- |
| `codex_app_server` | Unsupported | Unsupported | `ThreadStartParams` and `TurnStartParams` expose model, effort, service tier, and output schema, but neither control. |
| `codex_python_sdk` | Unsupported | Unsupported | The public SDK wraps the same app-server thread/turn contract. |
| `codex_cli` | Unsupported | Unsupported | Codex CLI/run configuration does not expose either control. Codex `max_output_tokens` fields found in tool handlers limit captured shell/tool output, not model generation. |
| `claude_python_sdk` | Unsupported | Unsupported | `ClaudeAgentOptions` exposes model, max turns, budget, effort, and tools, but neither control. |

Yoke therefore does not add `RunOptions.temperature` or
`RunOptions.max_output_tokens`. Accepting either today would imply enforcement
that no current runnable surface can provide. Callers should attest these
controls as unsupported rather than unenforced or best-effort.

Primary evidence:

- https://github.com/openai/codex/blob/main/codex-rs/app-server-protocol/src/protocol/v2/thread.rs
- https://github.com/openai/codex/blob/main/codex-rs/app-server-protocol/src/protocol/v2/turn.rs
- https://github.com/anthropics/claude-agent-sdk-python/blob/main/src/claude_agent_sdk/types.py
- https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching
