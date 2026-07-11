# Feature recipes

Yoke capability reports now carry `recipes` on each `FeatureReport`. A recipe is
a short Yoke entrypoint string such as `goal = await session.get_goal()` or
`async for event in session.stream(prompt): ...`.

This is deliberately separate from `lowering` and `evidence`:

- `support` says whether the surface supports the feature.
- `lowering` says how Yoke maps the feature onto the provider.
- `recipes` say what SDK call a user should make.
- `evidence` says which provider docs or source material justify the claim.

The distinction matters for Codex especially. Codex CLI, Codex Python SDK, and
Codex app-server all support some form of sessions or streaming, but the natural
Yoke entrypoints differ by surface. App-server also owns native goal methods,
model listing, collaboration-agent events, interruption, and fork behavior.

The recipes are not executable snippets. They are compact guide strings for
README tables, generated docs, capability UIs, and CodeAlmanac planning logic.
