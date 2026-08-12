from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Superuser/owner connection: migrations + tenant provisioning only. The
    # running API must never use this — it can bypass RLS.
    database_url_migrations: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5434/regtech"
    )

    # app_user connection: NOSUPERUSER NOBYPASSRLS. The only role the FastAPI
    # app (and its request-scoped sessions) ever connects as.
    database_url_app: str = (
        "postgresql+psycopg://app_user:app_user_dev_password@localhost:5434/regtech"
    )

    app_db_password: str = "app_user_dev_password"

    # Identity & Verification module (BVN/NIN). "mock" needs no credentials;
    # a real provider is a new adapter class in app/services/identity/providers/
    # plus one entry in app/services/identity/factory.py -- nothing else changes.
    identity_provider: str = "mock"

    # HMAC key for IdentityVerification.identifier_hash (see
    # app/services/identity_service.py:hash_identifier). This is what stops
    # the hash column from being brute-forceable from a DB/audit_log dump --
    # MUST be overridden via env var outside local dev.
    identity_hash_pepper: str = "dev-only-change-me-in-prod"

    # Sanctions & Watchlist Screening module. "mock" needs no credentials; a
    # real provider (ComplyAdvantage, Refinitiv World-Check, Dow Jones,
    # LSEG) is a new adapter class in app/services/watchlist/providers/ plus
    # one entry in app/services/watchlist/factory.py -- nothing else changes.
    watchlist_provider: str = "mock"

    # Minimum similarity score (0-100) for a candidate to count as a hit.
    # 70 is a conservative default for name-fuzzy-matching: same-length
    # names differing only by a transliteration/spelling variant or an
    # inserted middle name typically score well above 70, while unrelated
    # names of similar length rarely clear it (see MockWatchlistProvider).
    # This is illustrative for the mock adapter, not a regulatory-grade
    # threshold -- override via env var, and expect a real provider
    # integration to use its own vendor-defined confidence bands instead.
    sanctions_match_threshold: float = 70.0

    # Transaction Monitoring module. Pure in-house rule engine -- no external
    # provider to swap, unlike identity/sanctions. Defaults below are
    # illustrative starting points for a mock dataset (NGN-denominated, like
    # the rest of this app's dev defaults), not calibrated against real
    # transaction volumes or CBN/NFIU large-transaction/STR thresholds --
    # override via env var per deployment.
    monitoring_large_amount_threshold: float = 5_000_000.0
    monitoring_velocity_window_hours: int = 24
    monitoring_velocity_amount_threshold: float = 3_000_000.0
    # Minimum transaction count within the window before this rule can fire --
    # structuring is inherently about *multiple* transactions, not one.
    monitoring_velocity_min_transactions: int = 3
    monitoring_round_amount_modulus: float = 100_000.0
    monitoring_round_amount_minimum: float = 1_000_000.0

    # Case Management module. Severity floor below which a transaction alert
    # does not automatically open a case (still reachable via manual case
    # creation) -- keeps the review queue from being flooded by weak,
    # high-false-positive signals like ROUND_AMOUNT on their own. Sanctions
    # potential_match hits are unconditional -- unlike a rule-engine heuristic,
    # a watchlist hit always warrants review regardless of score.
    case_auto_open_min_severity: str = "medium"  # "low" | "medium" | "high"


settings = Settings()
