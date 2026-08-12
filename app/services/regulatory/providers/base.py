from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class SubmissionResult:
    """Provider-agnostic shape every adapter normalizes into, same rationale
    as ProviderResult (identity) / WatchlistScreeningResult (sanctions):
    nothing above this layer ever sees a provider's native response.
    """

    status: str  # "submitted" | "error"
    provider_reference: str | None
    error_detail: str | None = None


class RegulatorProvider(ABC):
    @abstractmethod
    def submit(self, payload: dict[str, Any]) -> SubmissionResult: ...
