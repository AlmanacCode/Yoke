# Live conformance worklog

## 2026-07-10

- Three cold-user labs understood Yoke's purpose and basic syntax.
- Claude reused OAuth and native subagents worked, but declared write access lowered to `dontAsk`, blocked file work, and still returned success.
- Codex app-server runs, streaming, skills, files, sessions, and models worked.
- Normal Pydantic schemas failed Codex strict-schema validation.
- Codex Python SDK model listing returned empty and run overrides were dropped.
- Both workflow labs became opaque and exceeded reasonable task time.
- Lab evidence remains under `/tmp/yoke-user-labs/{claude,codex-app,sdk-ux}`.
- After access-aware Claude permission lowering, the original cold-user ordinary
  run succeeded live with existing Claude OAuth and created
  `workspace/notes/hello.txt` containing exactly `hello from yoke`, plus the
  skill-required `notes/README.md`.

### Post-fix live evidence

- Codex Python SDK readiness completed against `openai_codex 0.1.0b2` and
  `codex-cli 0.141.0`; model listing returned `gpt-5.5`, `gpt-5.4`,
  `gpt-5.4-mini`, and `gpt-5.3-codex-spark`.
- A live Python SDK run explicitly requesting `gpt-5.4-mini` accepted a nested
  strict Pydantic schema, succeeded, and returned an `Assessment` instance.
- A live app-server run on 2026-07-10 used an agent default of `gpt-5.5` and a
  run override of `gpt-5.4-mini`. The normalized run and session both retained
  `gpt-5.4-mini` as the requested model; nested strict structured output
  succeeded and returned an `Assessment` instance. This proves request
  forwarding and typed output, not provider-reported effective-model identity.
- A live Claude Python SDK run on 2026-07-10 requested `sonnet` with the same
  recursively closed nested Pydantic schema. It succeeded and returned an
  `Assessment` instance with nested `Detail` data. This confirms the shared
  provider-compatible schema normalization is accepted by both Claude and
  Codex; provider-specific schema lowering is not currently necessary.

### Bounded workflow observability

- Portable workflows now have overall and per-step deadlines, ordered
  `step_started`, `step_completed`, `step_failed`, and `step_timed_out`
  callbacks, typed partial failure evidence, and drained sibling cancellation.
  Failed results name `interrupted_steps` (not active tasks), because Yoke
  cancels and drains those tasks before returning control to the caller.
- Adapter exceptions are normalized into failed step runs while retaining
  completed siblings and traces. Observer exceptions add an `observer_failed`
  trace and do not erase or stop the workflow.
- A live two-step Codex app-server workflow completed in 26 seconds. It created
  `draft.txt`, independently reviewed it, created `review.txt` with `PASS`, and
  emitted the expected four lifecycle callbacks in dependency order.
- The same Claude Python SDK workflow completed in 27 seconds and emitted the
  same callback sequence. The provider reported both runs as successful, but
  the requested artifacts were absent, so artifact success is unverified.
  Repeating with write/never and write/auto permission policies produced the
  same result. Yoke does not infer side-effect success from provider status.
- Live probes used an 80-second workflow deadline and 38-second step deadline;
  no provider call was left unbounded.

### SDK authentication and discovery

- Runtime credentials are explicit, redacted, excluded from serialization, and
  validation errors hide their inputs. Claude lowers API keys and OAuth tokens
  into the SDK subprocess environment without mutating the parent process.
- Codex Python SDK login methods are intentionally explicit and documented as
  provider-persisted. Yoke rejects Codex runtime credentials before opening a
  client rather than quietly changing `CODEX_HOME` authentication state.
- Authentication inspection separates installed, authenticated, compatible,
  ready, and live-tested evidence. Unknown evidence remains `None`; safe local
  discovery never upgrades it to a claim.
- `discover()` probes authentication once per unique runnable surface, derives
  readiness from that result, and only constructs harnesses on discovered-ready
  surfaces satisfying the requested capability set.
- Live discovery with no agent now succeeds without opening a paid turn. It
  found Claude SDK plus Codex CLI, Python SDK, and app-server through existing
  OAuth; both model-capable Codex surfaces returned four models. Constructing a
  runnable harness still requires the caller to provide an agent.
- Final review caught and fixed a Claude fork regression, validation of raw
  dictionary JSON Schemas, misleading installed-vs-logged-out Codex status,
  and serialization/repr exposure of interactive login handles.
- Final repository gate on 2026-07-10: Ruff clean, 440 tests passed, source and
  wheel distributions built, and `git diff --check` passed.
- A final fresh-user pass understood the product and composed agents, folders,
  skills, subagents, discovery, runs, and workflows without reading internals.
  It exposed documentation gaps around standalone discovery, surface selection,
  the reserved `main` workflow agent, time bounds, and SDK run persistence; the
  README now addresses each. Its own live command stalled outside observable
  script execution and was stopped, so it is UX evidence rather than an extra
  provider-success claim.
