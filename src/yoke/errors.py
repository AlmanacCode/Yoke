"""Yoke exceptions."""


class YokeError(Exception):
    """Base error for Yoke."""


class AdapterNotFound(YokeError):
    """Raised when no adapter is registered for a provider."""


class UnsupportedFeature(YokeError):
    """Raised when a provider cannot satisfy a requested feature."""
