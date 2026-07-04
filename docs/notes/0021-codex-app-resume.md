# Codex app-server resume

Codex app-server supports `thread/resume`.

The protocol says there are three resume modes:

- by `threadId`
- by in-memory history
- by rollout path

Yoke uses `threadId` because it is the stable public session handle Yoke can expose as `Session.id`.

Yoke now supports:

```python
session = await harness.start(SessionOptions(resume=thread_id))
```

The adapter flow is:

1. Start a fresh `codex app-server --listen stdio://` process.
2. Call `initialize`.
3. Configure Yoke folder skill roots with `skills/extraRoots/set`.
4. Call `thread/resume` with `threadId` and the same core overrides used for `thread/start`.
5. Store the returned live thread handle in the adapter.

After that, `Session.run(...)` and `Session.stream(...)` append turns to the resumed thread.

Important boundary:

`thread/read` is different. It reads stored history without loading or subscribing to a thread. Yoke has not exposed that yet because the public model for "inspect a stored session without running it" should be separate from `Harness.start(...)`.

Resume only works for app-server threads that Codex can load. A Yoke app-server session created with the adapter default may be ephemeral. To create a thread intended for later resume, construct the adapter with:

```python
CodexAppServer(ephemeral=False)
```

or attach a native app-server `Goal`, which already forces a persistent thread because Codex rejects goals on ephemeral threads.

