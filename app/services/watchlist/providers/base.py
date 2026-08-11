from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class WatchlistHit:
    """One candidate above threshold. Provider-agnostic shape a future
    case-management review queue consumes directly -- no redesign needed
    when a real provider (ComplyAdvantage, Refinitiv World-Check, Dow
    Jones, LSEG) is swapped in, since it normalizes into the same fields.
    """

    matched_name: str
    list_name: str  # e.g. "OFAC-SDN", "UN-CONSOLIDATED", "PEP", "EU-CONSOLIDATED"
    score: float  # 0-100


@dataclass
class WatchlistScreeningResult:
    status: str  # "clear" | "potential_match" | "error"
    hits: list[WatchlistHit] = field(default_factory=list)
    highest_score: float | None = None
    # Best score observed across the *entire* candidate set, not just hits
    # above threshold -- lets a future review queue sort/filter "near
    # misses" that fell just under the line, not only confirmed hits.
    error_detail: str | None = None


class WatchlistProvider(ABC):
    @abstractmethod
    def screen(self, name: str, threshold: float) -> WatchlistScreeningResult: ...
