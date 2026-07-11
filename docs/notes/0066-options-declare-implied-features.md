# Options declare implied features

Date: 2026-07-04

`RunOptions` exposes `features(inherited_goal=None)`.

The model owns option-driven provider requirements. Today:

- `output_schema` implies `Feature.STRUCTURED_OUTPUT`.
- normal run goals do not imply `Feature.GOAL`.

A goal attached to an agent or run is portable context. Adapters can compile it into prompt/developer instructions. Native readable/mutable goal state is a separate surface feature and is guarded by session goal methods.

`Harness` and `Session` ask the options object for implied features and pass each feature through `require(...)`. Future option fields can add their own feature requirements in one place instead of teaching every call site about every option.
