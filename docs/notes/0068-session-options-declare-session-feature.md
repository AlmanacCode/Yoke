# Session options declare the session feature

Date: 2026-07-04

`SessionOptions` now exposes `features(inherited_goal=None)`.

Starting a session always implies `Feature.SESSION`, so `Harness.start(...)` asks `SessionOptions` for its implied features and passes them through `Harness.require(...)` before invoking an adapter.

Goals on session options remain portable context unless the caller uses native goal state methods. A goal passed to `SessionOptions` does not imply `Feature.READABLE_GOAL` or `Feature.MUTABLE_GOAL`.

This mirrors `RunOptions.features(...)` and keeps option-driven capability requirements owned by the option models instead of scattered through `Harness` methods.
