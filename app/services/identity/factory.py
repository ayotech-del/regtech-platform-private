from __future__ import annotations

from app.config import settings
from app.services.identity.providers.base import IdentityProvider
from app.services.identity.providers.mock import MockIdentityProvider

_PROVIDERS: dict[str, type[IdentityProvider]] = {
    "mock": MockIdentityProvider,
    # A real provider (Smile Identity, Youverify, Prembly, ...) is one new
    # adapter class plus one entry here -- identity_service.py and
    # app/api/routes/identity.py don't change.
}


def get_identity_provider() -> IdentityProvider:
    try:
        return _PROVIDERS[settings.identity_provider]()
    except KeyError:
        raise ValueError(
            f"Unknown identity_provider {settings.identity_provider!r}; expected one of {sorted(_PROVIDERS)}"
        ) from None
