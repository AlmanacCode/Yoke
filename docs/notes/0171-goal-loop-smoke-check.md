# Goal-loop smoke check

Date: 2026-07-04

`scripts/smoke_harnesses.py` now includes `--run-codex-app-goal-loop`.

This smoke check exercises the public Yoke API rather than the lower-level goal state methods:

```bash
PYTHONPATH=src python scripts/smoke_harnesses.py --run-codex-app-goal-loop
```

It calls `Harness.goal_loop_sync(GoalLoopOptions(...))`, reads the accepted provider goal back through the returned session, and closes the session handle.

This sits beside `--run-codex-app-goal`, which still checks direct app-server `set_goal`, `get_goal`, and `clear_goal` behavior. The two checks answer different questions:

- `--run-codex-app-goal` verifies the mutable/readable goal API.
- `--run-codex-app-goal-loop` verifies the SDK-level provider-owned loop handle.

Neither command turns Yoke into a durable job system. They only prove that Yoke can reach the provider surface and return the correct handle.

Live result on 2026-07-04:

```text
PYTHONPATH=src python scripts/smoke_harnesses.py --surface codex:app --run-codex-app-goal-loop
codex:codex_app_server [app_server]: ok: Logged in using ChatGPT
codex_app_server goal_loop: session=019f2dae-8cf7-7901-8545-e4b40a2017d4 goal='Verify Yoke goal_loop returns a provider session handle.' auto_continues=True
```

This proves the local Codex app-server surface can accept the Yoke `goal_loop()` call and expose the goal through the returned session handle in this environment.
