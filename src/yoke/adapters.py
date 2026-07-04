"""Adapter registry."""

from __future__ import annotations

from yoke.errors import AdapterNotFound
from yoke.models import Provider
from yoke.ports import ProviderAdapter

_default_adapters: dict[Provider, ProviderAdapter] = {}
_surface_adapters: dict[tuple[Provider, str], ProviderAdapter] = {}


def register(adapter: ProviderAdapter) -> ProviderAdapter:
    """Register a provider adapter."""

    _default_adapters[adapter.provider] = adapter
    surface = getattr(adapter, "surface", None)
    if surface:
        _surface_adapters[(adapter.provider, str(surface))] = adapter
    return adapter


def adapter_for(provider: Provider, surface: str | None = None) -> ProviderAdapter:
    """Return the registered adapter for a provider."""

    if surface is not None:
        adapter = _surface_adapters.get((provider, surface))
        if adapter is not None:
            return adapter
        return register(default_adapter(provider, surface))
    try:
        return _default_adapters[provider]
    except KeyError:
        return register(default_adapter(provider, surface))


def default_adapter(provider: Provider, surface: str | None = None) -> ProviderAdapter:
    """Construct the built-in adapter for a provider surface."""

    if provider == "claude":
        if surface not in (None, "claude_python_sdk"):
            raise AdapterNotFound(
                f"no built-in Yoke adapter for provider {provider!r} surface {surface!r}"
            )
        from yoke.providers.claude import Claude

        return Claude()
    if provider == "codex":
        if surface == "codex_app_server":
            from yoke.providers.codex_app_server import CodexAppServer

            return CodexAppServer()
        if surface in (None, "codex_cli"):
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
