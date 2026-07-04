"""Adapter registry."""

from __future__ import annotations

from yoke.errors import AdapterNotFound
from yoke.models import Provider
from yoke.ports import ProviderAdapter

_adapters: dict[Provider, ProviderAdapter] = {}


def register(adapter: ProviderAdapter) -> ProviderAdapter:
    """Register a provider adapter."""

    _adapters[adapter.provider] = adapter
    return adapter


def adapter_for(provider: Provider) -> ProviderAdapter:
    """Return the registered adapter for a provider."""

    try:
        return _adapters[provider]
    except KeyError as exc:
        raise AdapterNotFound(f"no Yoke adapter registered for provider {provider!r}") from exc


def clear_adapters() -> None:
    """Clear registered adapters.

    This is mainly useful for tests and embedded applications that own adapter
    lifecycle explicitly.
    """

    _adapters.clear()
