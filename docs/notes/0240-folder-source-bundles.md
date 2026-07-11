# Folder source bundles

A folder-loaded Yoke agent now remains bundleable without losing skill content.

The previous artifact collector only bundled skills with `instructions` and no `path`. That worked for SDK-authored inline skills, but a skill loaded from a Yoke folder has both:

- `path`: where the skill came from inside the folder
- `instructions`: the loaded `SKILL.md` body

That meant `Agent.save(...)` followed by `Agent.from_folder(...)` could preserve the skill for runtime use, but `loaded.bundle(provider=...)` would omit the skill artifact. This weakened the selling point that the folder and SDK object are equivalent authoring surfaces.

The artifact collector now treats any skill with loaded instructions as bundleable. Pure external `Skill.from_path(...)` values still have no instructions and remain references.

A new folder-first test proves one recursive folder can carry:

- root goal
- root skill
- subagent with provider naming options
- subagent skill
- portable step workflow
- provider-native script workflow
- Codex project agent settings

The test saves the agent, reloads it from disk, bundles it for Codex and Claude, and asserts the expected provider files.

Verification:

- `PYTHONPATH=src uv run pytest tests/test_folders.py tests/test_artifacts.py`
- `PYTHONPATH=src uv run ruff check src/yoke/artifacts.py tests/test_folders.py tests/test_artifacts.py`
