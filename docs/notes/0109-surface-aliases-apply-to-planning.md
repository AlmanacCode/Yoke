# Surface aliases apply to planning

Surface aliases now apply to planning helpers as well as runtime handles.

`profile_for("codex", "app")` resolves to the same exact surface as `Harness(provider="codex", surface="app", ...)`: `codex_app_server`.

This matters because planning and execution should not have two dialects. A caller should be able to inspect a surface, require features, and then construct a harness using the same words.

Aliases remain input-only. `Profile.surface`, `Fit.profile.surface`, `Plan.surface`, readiness values, events, sessions, and runs should report exact surface names so logs and capability diagnostics stay precise.
