# README embedding boundary

The README now states the intended app integration boundary: product code owns product verbs, jobs, retries, safety checks, and persistence; Yoke owns provider-neutral agent, session, workflow, goal, event, and option values; provider adapters own Claude and Codex protocol details.

This matches the CodeAlmanac integration direction. CodeAlmanac keeps init, ingest, garden, job logging, changed-file validation, and reindexing in lifecycle workflows, while the Yoke-backed harness adapter maps provider-neutral request fields such as model, effort, output schema, goal, and session persistence into Yoke options.

The README also clarifies that Yoke workflows are agent-turn orchestration, not an app's durable product workflow runtime. An embedding app should not pass arbitrary Yoke workflow objects through its product boundary unless that boundary explicitly models multi-turn agent orchestration.

The README structured-output example now imports `RunOptions`, and the app-embedding example uses the explicit `Tools` model rather than relying on Pydantic dict coercion.
