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
        try:
            return _surface_adapters[(provider, surface)]
        except KeyError as exc:
            raise AdapterNotFound(
                f"no Yoke adapter registered for provider {provider!r} surface {surface!r}"
            ) from exc
    try:
        return _default_adapters[provider]
    except KeyError as exc:
        raise AdapterNotFound(f"no Yoke adapter registered for provider {provider!r}") from exc


def clear_adapters() -> None:
    """Clear registered adapters.

    This is mainly useful for tests and embedded applications that own adapter
    lifecycle explicitly.
    """

    _default_adapters.clear()
    _surface_adapters.clear()
