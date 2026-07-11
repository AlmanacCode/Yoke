# Run goals are not native goal requirements

Date: 2026-07-04

Yoke distinguishes normal run goals from native provider goal state.

A `Goal` attached to `Agent` or `RunOptions` is not a surface-selection requirement. Adapters can lower it into prompt/developer instructions or provider options for ordinary runs. If Yoke treated every run goal as `Feature.GOAL`, Codex one-shot runs would tend to select `codex_app_server` because it has native goal support, even though `codex_cli` and Claude can still receive compiled goals.

Native goal state remains capability-gated through session methods:

- `Session.get_goal(...)` requires `Feature.READABLE_GOAL`.
- `Session.set_goal(...)` requires `Feature.MUTABLE_GOAL`.
- `Session.clear_goal(...)` requires `Feature.MUTABLE_GOAL`.

So the rule is:

- run goals are portable context;
- readable/mutable goal state is a provider-surface feature.
