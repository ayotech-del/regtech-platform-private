# Importing this package registers every model on Base.metadata -- required
# before any flush touches a foreign key pointing at another table (e.g.
# every tenant-scoped table's tenant_id -> tenants.id), since SQLAlchemy
# only knows about a table once its model class has actually been imported
# somewhere. Nothing enforced that for the live app (as opposed to
# migrations/env.py, which already imported everything explicitly, or
# scripts/smoke_test.py, which happens to import what it directly uses) --
# app/main.py imports this package precisely to close that gap.
import app.models.api_key  # noqa: F401
import app.models.case  # noqa: F401
import app.models.case_note  # noqa: F401
import app.models.customer  # noqa: F401
import app.models.identity_verification  # noqa: F401
import app.models.report  # noqa: F401
import app.models.sanctions_screening  # noqa: F401
import app.models.tenant  # noqa: F401
import app.models.transaction  # noqa: F401
import app.models.transaction_alert  # noqa: F401
