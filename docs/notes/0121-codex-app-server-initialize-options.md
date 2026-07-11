# Codex app-server initialize options

Yoke now has typed Codex app-server connection options under `CodexOptions.app_server`.

The first modeled fields are app-server `initialize.params.capabilities` values documented by Codex:

- `experimentalApi`, still controlled by `CodexOptions.experimental_api`
- `optOutNotificationMethods`, exposed as `CodexAppServerOptions.opt_out_notification_methods`
- `mcpServerOpenaiFormElicitation`, exposed as `CodexAppServerOptions.mcp_server_openai_form_elicitation`

Example:

```python
ProviderOptions(
    codex=CodexOptions(
        experimental_api=True,
        app_server=CodexAppServerOptions(
            opt_out_notification_methods=("thread/started",),
            mcp_server_openai_form_elicitation=True,
        ),
    )
)
```

The adapter still accepts camelCase and raw dictionary forms. This preserves escape-hatch compatibility while giving the common app-server initialize capabilities a typed, discoverable home.

Yoke keeps `clientInfo` adapter-owned. Codex app-server uses client identity for compliance/logging, so it should come from the adapter/application configuration rather than per-run provider options.
