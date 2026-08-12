from __future__ import annotations

from app.config import settings
from app.services.regulatory.providers.base import RegulatorProvider
from app.services.regulatory.providers.mock import MockRegulatorProvider

_PROVIDERS: dict[str, type[RegulatorProvider]] = {
    "mock": MockRegulatorProvider,
    # A real provider (NFIU goAML, or another FIU's equivalent submission
    # channel) is one new adapter class plus one entry here --
    # report_service.py and app/api/routes/reports.py don't change.
}


def get_regulator_provider() -> RegulatorProvider:
    try:
        return _PROVIDERS[settings.regulator_provider]()
    except KeyError:
        raise ValueError(
            f"Unknown regulator_provider {settings.regulator_provider!r}; expected one of {sorted(_PROVIDERS)}"
        ) from None
