from __future__ import annotations

import hashlib
import json
from typing import Any

from app.services.regulatory.providers.base import RegulatorProvider, SubmissionResult

# Reserved sentinel, same idiom as MockWatchlistProvider's _ERROR_TRIGGER --
# generate_report takes no free-text input of its own (everything comes
# from the case), so this keys off the case's own resolution_notes instead.
_ERROR_TRIGGER = "trigger regulator provider error"


class MockRegulatorProvider(RegulatorProvider):
    """No real credentials/API needed. Deterministic: the same payload
    always yields the same reference, derived from a hash of its canonical
    JSON form -- mirrors the reference-generation idiom in
    MockIdentityProvider, just keyed on the whole payload instead of a
    single identifier.
    """

    def submit(self, payload: dict[str, Any]) -> SubmissionResult:
        notes = (payload.get("resolution_notes") or "").strip().casefold()
        if notes == _ERROR_TRIGGER:
            return SubmissionResult(
                status="error",
                provider_reference=None,
                error_detail="Simulated provider error: regulator submission portal unavailable",
            )

        canonical = json.dumps(payload, sort_keys=True, default=str)
        reference = f"MOCK-STR-{hashlib.sha1(canonical.encode()).hexdigest()[:10].upper()}"
        return SubmissionResult(status="submitted", provider_reference=reference)
