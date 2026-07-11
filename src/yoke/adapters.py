"""Adapter registry."""

from __future__ import annotations

from yoke.errors import AdapterNotFound
from yoke.models import Provider
from yoke.ports import ProviderAdapter

ProviderKey = str

_default_adapters: dict[ProviderKey, ProviderAdapter] = {}
_surface_adapters: dict[tuple[ProviderKey, str], ProviderAdapter] = {}
_builtin_surfaces: dict[ProviderKey, set[str]] = {
    "claude": {"claude_python_sdk"},
    "codex": {"codex_cli", "codex_python_sdk", "codex_app_server"},
}


def register(adapter: ProviderAdapter) -> ProviderAdapter:
    """Register a provider adapter."""

    provider = str(adapter.provider)
    _default_adapters[provider] = adapter
    surface = getattr(adapter, "surface", None)
    if surface:
        _surface_adapters[(provider, str(surface))] = adapter
    return adapter


def adapter_for(provider: Provider, surface: str | None = None) -> ProviderAdapter:
    """Return the registered adapter for a provider."""

    provider_key = str(provider)
    if surface is not None:
        adapter = _surface_adapters.get((provider_key, str(surface)))
        if adapter is not None:
            return adapter
        return register(default_adapter(provider, surface))
    try:
        return _default_adapters[provider_key]
    except KeyError:
        return register(default_adapter(provider, surface))


def has_adapter(provider: Provider | str, surface: str | None = None) -> bool:
    """Return whether Yoke has an adapter path for a provider surface."""

    provider_key = str(provider)
    if surface is None:
        return provider_key in _default_adapters or provider_key in _builtin_surfaces
    surface_key = str(surface)
    if (provider_key, surface_key) in _surface_adapters:
        return True
    return surface_key in _builtin_surfaces.get(provider_key, set())


def registered_capabilities(provider: Provider | str, surface: str | None = None):
    """Return capabilities declared by a registered adapter, if present."""

    provider_key = str(provider)
    adapter: ProviderAdapter | None = None
    if surface is not None:
        adapter = _surface_adapters.get((provider_key, str(surface)))
    if adapter is None and surface is None:
        adapter = _default_adapters.get(provider_key)
    if adapter is None:
        return None
    return getattr(adapter, "capabilities", None)


def default_adapter(provider: Provider, surface: str | None = None) -> ProviderAdapter:
    """Construct the built-in adapter for a provider surface."""

    provider_key = str(provider)
    surface_key = str(surface) if surface is not None else None
    if provider_key == "claude":
        if surface_key not in (None, "claude_python_sdk"):
            raise AdapterNotFound(
                "no built-in Yoke adapter for provider "
                f"{provider!r} surface {surface!r}"
            )
        from yoke.providers.claude import Claude

        return Claude()
    if provider_key == "codex":
        if surface_key is None:
            from yoke.providers.codex_app_server import CodexAppServer

            return CodexAppServer()
        if surface_key == "codex_app_server":
            from yoke.providers.codex_app_server import CodexAppServer

            return CodexAppServer()
        if surface_key == "codex_python_sdk":
            from yoke.providers.codex_sdk import CodexPythonSdk

            return CodexPythonSdk()
        if surface_key == "codex_cli":
            from yoke.providers.codex import Codex

            return Codex()
        raise AdapterNotFound(
            f"no built-in Yoke adapter for provider {provider!r} surface {surface!r}"
        )
    raise AdapterNotFound(f"no built-in Yoke adapter for provider {provider!r}")


def clear_adapters() -> None:
    """Clear registered adapters.

    This is mainly useful for tests and embedded applications that own adapter
    lifecycle explicitly.
    """

    _default_adapters.clear()
    _surface_adapters.clear()
