# Collaboration mode is not assumed experimental

Codex app-server has explicit stable and experimental protocol surfaces. `collaborationMode/list` is documented as experimental, and app-server rejects experimental methods or fields unless the client initialized with `capabilities.experimentalApi = true`.

Yoke should not infer that every collaboration-related field is experimental. The README documents `collaborationMode` as a typed Codex app-server turn option and keeps `CodexOptions(experimental_api=True)` separate.

Design rule: if a future app-server field or method is protocol-marked experimental, the Yoke option for that field should imply `Feature.EXPERIMENTAL_API`. Until the specific protocol evidence exists, do not force collaboration mode to imply experimental API.

This keeps Yoke honest in both directions: it does not silently opt into experimental protocol, and it does not over-restrict stable app-server fields.
