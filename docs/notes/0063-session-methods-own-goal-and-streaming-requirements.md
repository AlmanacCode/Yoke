# Session methods own goal and streaming requirements

Date: 2026-07-04

Yoke sessions now have `Session.require(...)`, mirroring `Harness.require(...)`.

Session methods with obvious provider requirements validate those requirements before calling adapters:

- `Session.stream(...)` requires `Feature.STREAMING`.
- `Session.get_goal(...)` requires `Feature.READABLE_GOAL`.
- `Session.set_goal(...)` requires `Feature.MUTABLE_GOAL`.
- `Session.clear_goal(...)` requires `Feature.MUTABLE_GOAL`.

This matters because session IDs are provider-surface artifacts. A Codex CLI resumable exec thread is not the same thing as a Codex app-server live thread with native readable/mutable goal state. Yoke should fail before adapter invocation when a session surface cannot support the operation.

Plain `Session.run(...)` intentionally remains unguarded by richer features. Sending a turn is the basic session operation; callers opt into stronger behavior by using `stream(...)` or goal methods.
