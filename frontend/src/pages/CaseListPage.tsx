import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ApiError, api } from "../api/client";
import { Badge } from "../components/Badge";
import type { CaseRead } from "../api/types";

export function CaseListPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const status = searchParams.get("status") ?? "";
  const customerId = searchParams.get("customer_id") ?? "";

  const [cases, setCases] = useState<CaseRead[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    api
      .listCases({ status: status || undefined, customer_id: customerId || undefined })
      .then((result) => {
        if (!cancelled) setCases(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Failed to load cases.");
      });
    return () => {
      cancelled = true;
    };
  }, [status, customerId]);

  function updateFilter(key: string, value: string) {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    setSearchParams(next);
  }

  return (
    <div>
      <h1>Case Queue</h1>

      <div className="filters">
        <label>
          Status
          <select value={status} onChange={(e) => updateFilter("status", e.target.value)}>
            <option value="">All</option>
            <option value="open">Open</option>
            <option value="in_review">In review</option>
            <option value="resolved">Resolved</option>
          </select>
        </label>
        <label>
          Customer ID
          <input
            type="text"
            placeholder="filter by customer_id"
            value={customerId}
            onChange={(e) => updateFilter("customer_id", e.target.value)}
          />
        </label>
      </div>

      {error && <p className="error-text">{error}</p>}

      {cases === null && !error && <p>Loading…</p>}

      {cases !== null && cases.length === 0 && <p className="empty-state">No cases match these filters.</p>}

      {cases !== null && cases.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Priority</th>
              <th>Status</th>
              <th>Source</th>
              <th>Customer</th>
              <th>Opened</th>
            </tr>
          </thead>
          <tbody>
            {cases.map((c) => (
              <tr key={c.id} className="clickable-row" onClick={() => navigate(`/cases/${c.id}`)}>
                <td>
                  <Badge value={c.priority} />
                </td>
                <td>
                  <Badge value={c.status} />
                </td>
                <td>{c.source_type.replace("_", " ")}</td>
                <td className="mono">{c.customer_id}</td>
                <td>{new Date(c.opened_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
