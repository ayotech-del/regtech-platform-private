from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings
from app.db.base import Base
import app.models.tenant  # noqa: F401 -- register models on Base.metadata
import app.models.customer  # noqa: F401
import app.models.transaction  # noqa: F401
import app.models.identity_verification  # noqa: F401
import app.models.sanctions_screening  # noqa: F401
import app.models.transaction_alert  # noqa: F401
import app.models.case  # noqa: F401
import app.models.case_note  # noqa: F401
import app.models.report  # noqa: F401
import app.models.api_key  # noqa: F401
import app.db.audit  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Migrations always run as the superuser/owner role, never as app_user.
config.set_main_option("sqlalchemy.url", settings.database_url_migrations)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
