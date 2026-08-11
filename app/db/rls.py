def rls_policy_statements(table_name: str) -> list[str]:
    """Shared RLS policy pattern for every tenant-scoped table. Called from
    each migration that creates such a table so the policy SQL never drifts
    between tables.

    Fail-closed by construction: current_setting(..., true) returns NULL if
    app.current_tenant was never set, and `tenant_id = NULL` is never true,
    so a code path that forgets to set the tenant GUC sees zero rows rather
    than every tenant's rows.
    """
    policy_name = f"tenant_isolation_{table_name}"
    return [
        f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY",
        f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY",
        f"""
        CREATE POLICY {policy_name} ON {table_name}
          USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
          WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)
        """,
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table_name} TO app_user",
    ]


def drop_rls_policy_statements(table_name: str) -> list[str]:
    policy_name = f"tenant_isolation_{table_name}"
    return [
        f"REVOKE SELECT, INSERT, UPDATE, DELETE ON {table_name} FROM app_user",
        f"DROP POLICY IF EXISTS {policy_name} ON {table_name}",
    ]
