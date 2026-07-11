# README positioning: surfaces and folders

The README now leads with two product truths that should guide future API work.

First, Yoke is provider-neutral but not provider-flattening. It must name concrete surfaces because `codex_cli`, `codex_python_sdk`, `codex_app_server`, `claude_cli`, and Claude SDK surfaces do not expose the same features. Capability checks belong to `(provider, surface)`, not provider alone.

Second, a Yoke folder is source. `Agent.save(...)` and `Agent.from_folder(...)` are the native authoring loop. Provider files are compiled artifacts, written only through `agent.bundle(...).write(...)`.

That gives Yoke a clean mental model:

- author with Python objects or folders
- choose a provider surface at runtime
- inspect surface capabilities honestly
- compile provider-native files explicitly when a project wants them

This should keep the framework readable while still supporting rich provider-specific behavior.
