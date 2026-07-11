# Folder form is the SDK form

Yoke now treats the folder form and the SDK form as peers.

The SDK object:

```python
agent = Agent(
    instructions="You are a careful maintainer.",
    goal=Goal("Finish safely."),
)
```

can be saved as a Yoke-native folder:

```python
agent.save("agents/maintainer")
```

and loaded back:

```python
agent = Agent.from_folder("agents/maintainer")
```

The native Yoke folder is intentionally not provider-specific. It uses:

- `agent.yaml` for structured agent metadata
- `instructions.md` for the main prompt
- `skills/` for reusable skills
- `subagents/` for nested agents
- `workflows/` for workflow recipes

Provider-native files remain a separate explicit step:

```python
agent.bundle(provider="codex", surface="codex_cli").write(repo)
agent.bundle(provider="claude", surface="claude_python_sdk").write(repo)
```

This split keeps the mental model clean:

- `save` writes Yoke source.
- `from_folder` reads Yoke source.
- `bundle` compiles Yoke source to provider artifacts.
- `Bundle.write` installs those compiled artifacts explicitly.

The design avoids hidden provider installation during ordinary SDK use. It also lets a project keep agents as readable folders while still choosing the best provider surface at runtime.
