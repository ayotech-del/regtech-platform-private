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


settings = Settings()
