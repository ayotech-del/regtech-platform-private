from __future__ import annotations

import re
from difflib import SequenceMatcher

from app.services.watchlist.providers.base import WatchlistHit, WatchlistProvider, WatchlistScreeningResult

# Deliberately fictional / composited names -- NOT sourced from any real
# OFAC/UN/EU sanctions list or real PEP register. This is a stand-in for a
# real provider's list content; it exists only to prove the matching and
# status-derivation pattern end to end.
_WATCHLIST: list[tuple[str, str]] = [
    ("Viktor Aleksandrovich Petrenko", "OFAC-SDN"),
    ("Dmitri Sergeyevich Volkov", "OFAC-SDN"),
    ("Farhan Al-Mansoori", "OFAC-SDN"),
    ("Ravi Chandrasekhar Menon", "OFAC-SDN"),
    ("Boris Yevgenyevich Volkov", "OFAC-SDN"),
    ("Oleksandr Ivanovich Karpenko", "UN-CONSOLIDATED"),
    ("Ibrahim Al-Bashir", "UN-CONSOLIDATED"),
    ("Nadia Petrovna Sokolova", "UN-CONSOLIDATED"),
    ("Layla Al-Rashid", "UN-CONSOLIDATED"),
    ("Sergei Anatolyevich Kuznetsov", "EU-CONSOLIDATED"),
    ("Henrik Lindqvist Bergstrom", "EU-CONSOLIDATED"),
    ("General Kwame Osei-Mensah", "PEP"),
    ("Senator Adaeze Nwachukwu", "PEP"),
    ("Minister Chidi Obiora", "PEP"),
    ("Governor Tunji Aderibigbe", "PEP"),
]

_ERROR_TRIGGER = "trigger sanctions provider error"
_PUNCT_RE = re.compile(r"[^a-z0-9\s]")
_WS_RE = re.compile(r"\s+")


def _normalize(name: str) -> str:
    s = name.casefold().strip()
    s = _PUNCT_RE.sub("", s)
    return _WS_RE.sub(" ", s)


def _token_sort(s: str) -> str:
    return " ".join(sorted(s.split()))


def _score(a: str, b: str) -> float:
    a_n, b_n = _normalize(a), _normalize(b)
    direct = SequenceMatcher(None, a_n, b_n).ratio()
    token_sorted = SequenceMatcher(None, _token_sort(a_n), _token_sort(b_n)).ratio()
    return round(max(direct, token_sorted) * 100, 1)


class MockWatchlistProvider(WatchlistProvider):
    """No real credentials/API needed. Deterministic: same name always
    yields the same scores against the same embedded list. Matching is
    illustrative only -- difflib ratio (+ a token-sort variant for word-
    order variants) is not a real entity-resolution algorithm; a real
    provider adapter will use whatever matching its API already performs,
    and this class's scoring logic is not meant to be reused there.
    """

    def screen(self, name: str, threshold: float) -> WatchlistScreeningResult:
        if not name or not name.strip():
            raise ValueError("name must not be blank")

        if name.strip().casefold() == _ERROR_TRIGGER:
            return WatchlistScreeningResult(
                status="error",
                error_detail="Simulated provider error: upstream watchlist service unavailable",
            )

        scored = [
            WatchlistHit(matched_name=entry_name, list_name=list_name, score=_score(name, entry_name))
            for entry_name, list_name in _WATCHLIST
        ]
        highest_score = max((h.score for h in scored), default=None)
        hits = sorted((h for h in scored if h.score >= threshold), key=lambda h: h.score, reverse=True)
        status = "potential_match" if hits else "clear"
        return WatchlistScreeningResult(status=status, hits=hits, highest_score=highest_score)
