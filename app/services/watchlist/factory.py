from __future__ import annotations

from app.config import settings
from app.services.watchlist.providers.base import WatchlistProvider
from app.services.watchlist.providers.mock import MockWatchlistProvider

_PROVIDERS: dict[str, type[WatchlistProvider]] = {
    "mock": MockWatchlistProvider,
    # A real provider (ComplyAdvantage, Refinitiv World-Check, Dow Jones,
    # LSEG, ...) is one new adapter class plus one entry here --
    # sanctions_service.py and app/api/routes/sanctions.py don't change.
}


def get_watchlist_provider() -> WatchlistProvider:
    try:
        return _PROVIDERS[settings.watchlist_provider]()
    except KeyError:
        raise ValueError(
            f"Unknown watchlist_provider {settings.watchlist_provider!r}; expected one of {sorted(_PROVIDERS)}"
        ) from None
