from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProviderResult:
    """Provider-agnostic shape every adapter normalizes into. Nothing above
    this layer (identity_service, routes) ever sees a provider's native
    response -- swapping providers later never touches orchestration code.
    """

    matched: bool
    status: str  # "verified" | "no_match" | "error"
    provider_reference: str | None
    profile: dict[str, Any] = field(default_factory=dict)
    error_detail: str | None = None


class IdentityProvider(ABC):
    @abstractmethod
    def verify_bvn(self, bvn: str) -> ProviderResult: ...

    @abstractmethod
    def verify_nin(self, nin: str) -> ProviderResult: ...
