from __future__ import annotations

import hashlib
import random

from app.services.identity.providers.base import IdentityProvider, ProviderResult

_NO_MATCH = "00000000000"
_PROVIDER_ERROR = "99999999999"
_FIRST_NAMES = ["Ada", "Chinedu", "Fatima", "Emeka", "Ngozi", "Tunde", "Amaka", "Ibrahim", "Chiamaka", "Yusuf"]
_LAST_NAMES = ["Okafor", "Balogun", "Abubakar", "Eze", "Okonkwo", "Adeyemi", "Musa", "Nwosu", "Bello", "Chukwu"]


class MockIdentityProvider(IdentityProvider):
    """No real credentials needed. Deterministic by reserved test values so
    all three response paths are exercisable in tests/demos: 11 zeros ->
    no_match, 11 nines -> simulated provider error, anything else
    well-formed -> verified with a fake profile derived deterministically
    from the input (same identifier always returns the same fake identity).
    """

    def verify_bvn(self, bvn: str) -> ProviderResult:
        return self._verify(bvn, "BVN")

    def verify_nin(self, nin: str) -> ProviderResult:
        return self._verify(nin, "NIN")

    def _verify(self, value: str, identifier_type: str) -> ProviderResult:
        if not (value.isdigit() and len(value) == 11):
            raise ValueError(f"{identifier_type} must be exactly 11 digits")

        reference = f"MOCK-{identifier_type}-{hashlib.sha1(value.encode()).hexdigest()[:10].upper()}"

        if value == _PROVIDER_ERROR:
            return ProviderResult(
                matched=False,
                status="error",
                provider_reference=None,
                profile={},
                error_detail="Simulated provider error: upstream service unavailable",
            )
        if value == _NO_MATCH:
            return ProviderResult(matched=False, status="no_match", provider_reference=reference, profile={})

        rng = random.Random(int(hashlib.sha256(f"{identifier_type}:{value}".encode()).hexdigest(), 16))
        profile = {
            "full_name": f"{rng.choice(_FIRST_NAMES)} {rng.choice(_LAST_NAMES)}",
            "date_of_birth": f"{rng.randint(1960, 2003)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
            "phone_number": f"080{rng.randint(10000000, 99999999)}",
        }
        return ProviderResult(matched=True, status="verified", provider_reference=reference, profile=profile)
