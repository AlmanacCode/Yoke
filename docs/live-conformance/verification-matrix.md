# Live conformance verification matrix

| Requirement | Current evidence | Completion evidence needed |
| --- | --- | --- |
| Codex app runs and files | Live pass | Preserve after changes |
| Codex strict structured output | Live pass on Python SDK and app-server with nested Pydantic `Assessment` | Preserve after changes |
| Codex SDK models | Live pass; same four-model account catalog as app-server | Preserve after changes |
| Codex model override | Live pass for explicit `gpt-5.4-mini`; requested model retained on run/session | Provider-reported effective model remains unavailable and must not be invented |
| Claude OAuth reuse | Live pass | Preserve after changes |
| Claude native subagents | Live pass | Preserve model/effort behavior |
| Claude noninteractive writes | Live pass: original lab created `notes/hello.txt` after permission fix | Preserve in final lab rerun |
| Typed structured data | Live pass on Claude SDK and Codex SDK/app-server; nested `Assessment` instances returned | Preserve after changes |
| Workflow bounds/progress | Tests prove typed overall/step timeouts, partial results, lifecycle callbacks, adapter-exception normalization, observer-failure evidence, and drained fail-fast sibling cancellation via `interrupted_steps`. Live Codex app created and reviewed files within 27s. Claude emitted ordered events within 27s and reported success, but artifact creation remains unverified because neither requested file existed. | Preserve local contract and Codex live pass; separately resolve Claude artifact verification |
| Full local quality | Fresh final gate: Ruff clean, 440 tests passed, sdist and wheel built, `git diff --check` clean | Preserve before integration |
