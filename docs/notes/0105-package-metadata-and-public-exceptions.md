# Package metadata and public exceptions

Yoke now exports `YokeError`, `UnsupportedFeature`, and `AdapterNotFound` from the top-level `yoke` package.

Embedded callers such as CodeAlmanac should not have to import from `yoke.errors` to catch SDK-level failures. The internal module remains, but the public package namespace now carries the normal exception surface.

`pyproject.toml` also declares `Typing :: Typed`, an `all` extra for installing both provider SDKs, and an explicit Hatch wheel package target for `src/yoke`. The repository already had `src/yoke/py.typed`; the metadata now reflects that public contract.
