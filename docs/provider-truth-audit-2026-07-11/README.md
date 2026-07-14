# Yoke Provider Truth Audit

Goal: audit Yoke's Codex and Claude mappings so native provider behavior is
separated from direct SDK mapping, filesystem materialization, prompt
compilation, Yoke orchestration, emulation, and unsupported behavior.

The browsable report starts at [`html/index.html`](html/index.html).

Core conclusion: CodeAlmanac's canonical definitions belong in its packaged
`src/codealmanac/agents/` collection. Claude SDK can consume declared
subagents programmatically. Codex app-server cannot currently consume the same
declared map as named custom agents through Yoke; Yoke prompt-compiles it and
spawns generic native children. True Codex custom-agent parity requires the
generated `.codex/agents/*.toml` files to be visible in the repository used as
the Codex thread `cwd`, or a future app-server configuration injection surface.

