"""Concise SDK discovery across provider surfaces."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field

from yoke.capabilities import Feature
from yoke.errors import UnsupportedFeature
from yoke.models import (
    Agent,
    Authentication,
    Credentials,
    Harness,
    Model,
    Provider,
    Readiness,
    Surface,
    YokeModel,
)
from yoke.surfaces import profiles_for


class SurfaceDiscovery(YokeModel):
    """Safe, non-turn discovery for one runnable surface."""

    surface: Surface | str
    readiness: Readiness
    authentication: Authentication
    models: tuple[Model, ...] = ()
    models_error: str | None = None


class Discovery(YokeModel):
    """Provider discovery result that can construct a requirement-fit harness."""

    provider: Provider
    cwd: Path
    agent: Agent | None = None
    credentials: Credentials = Field(
        default_factory=Credentials.auto, exclude=True, repr=False
    )
    surfaces: tuple[SurfaceDiscovery, ...]

    def harness(self, *features: Feature | str) -> Harness:
        """Construct a harness on a discovered ready, requirement-fit surface."""

        if self.agent is None:
            raise ValueError(
                "Discovery has no agent; pass agent=... to discover() before "
                "constructing a harness"
            )
        for item in self.surfaces:
            if not item.authentication.ready:
                continue
            candidate = Harness(
                provider=self.provider,
                surface=item.surface,
                agent=self.agent,
                cwd=self.cwd,
                credentials=self.credentials,
            )
            try:
                return candidate.require(*features)
            except UnsupportedFeature:
                continue
        names = ", ".join(str(feature) for feature in features) or "none"
        raise UnsupportedFeature(
            f"no discovered ready {self.provider} surface supports: {names}"
        )


async def discover(
    provider: Provider | str,
    cwd: str | Path,
    agent: Agent | None = None,
    *,
    credentials: Credentials | None = None,
) -> Discovery:
    """Discover safe readiness, authentication, and models without a paid turn."""

    provider_value = Provider(provider)
    credentials_value = credentials or Credentials.auto()
    found: list[SurfaceDiscovery] = []
    seen: set[Surface | str] = set()
    for profile in profiles_for(provider_value, runnable=True):
        if profile.surface in seen:
            continue
        seen.add(profile.surface)
        harness = Harness(
            provider=provider_value,
            surface=profile.surface,
            # Harness validation requires an agent even though safe discovery
            # never starts a turn. Keep this placeholder out of the result.
            agent=agent or Agent(instructions="Discovery probe only."),
            cwd=Path(cwd),
            credentials=credentials_value,
        )
        authentication = await harness.auth_status()
        readiness = readiness_from_authentication(authentication)
        models: tuple[Model, ...] = ()
        models_error = None
        if profile.supports(Feature.MODELS) and readiness.available:
            try:
                models = await harness.models()
            except Exception as exc:
                # Discovery stays useful when account-scoped model listing fails.
                models_error = type(exc).__name__
        found.append(
            SurfaceDiscovery(
                surface=profile.surface,
                readiness=readiness,
                authentication=authentication,
                models=models,
                models_error=models_error,
            )
        )
    return Discovery(
        provider=provider_value,
        cwd=Path(cwd),
        agent=agent,
        credentials=credentials_value,
        surfaces=tuple(found),
    )


def readiness_from_authentication(status: Authentication) -> Readiness:
    """Project non-secret auth discovery into the established readiness value."""

    return Readiness(
        provider=status.provider,
        surface=status.surface,
        available=status.ready,
        message=status.message,
    )
