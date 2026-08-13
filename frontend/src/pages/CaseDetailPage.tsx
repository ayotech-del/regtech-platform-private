import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, api } from "../api/client";
import { Badge } from "../components/Badge";
import type {
  CaseNoteRead,
  CaseRead,
  CaseResolution,
  CaseStatus,
  CustomerRead,
  ReportRead,
  SanctionsScreeningRead,
  TransactionAlertRead,
} from "../api/types";

type SourceRecord = SanctionsScreeningRead | TransactionAlertRead;

export function CaseDetailPage() {
  const { caseId } = useParams<{ caseId: string }>();

  const [caseData, setCaseData] = useState<CaseRead | null>(null);
  const [customer, setCustomer] = useState<CustomerRead | null>(null);
  const [sourceRecord, setSourceRecord] = useState<SourceRecord | null>(null);
  const [notes, setNotes] = useState<CaseNoteRead[]>([]);
  const [reports, setReports] = useState<ReportRead[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [resolveForm, setResolveForm] = useState<{
    status: CaseStatus;
    resolution: CaseResolution | "";
    resolutionNotes: string;
    assignedTo: string;
  }>({ status: "open", resolution: "", resolutionNotes: "", assignedTo: "" });
  const [resolveError, setResolveError] = useState<string | null>(null);
  const [resolving, setResolving] = useState(false);

  const [noteAuthor, setNoteAuthor] = useState("");
  const [noteBody, setNoteBody] = useState("");
  const [noteError, setNoteError] = useState<string | null>(null);
  const [addingNote, setAddingNote] = useState(false);

  const [reportError, setReportError] = useState<string | null>(null);
  const [generatingReport, setGeneratingReport] = useState(false);

  const load = useCallback(async () => {
    if (!caseId) return;
    try {
      const c = await api.getCase(caseId);
      setCaseData(c);
      setResolveForm({
        status: c.status,
        resolution: c.resolution ?? "",
        resolutionNotes: c.resolution_notes ?? "",
        assignedTo: c.assigned_to ?? "",
      });

      const [customerResult, notesResult, reportsResult, sourceList] = await Promise.all([
        api.getCustomer(c.customer_id),
        api.listCaseNotes(c.id),
        api.listReports(c.id),
        c.source_type === "sanctions_screening"
          ? api.listSanctionsScreenings(c.customer_id)
          : api.listTransactionAlerts(c.customer_id),
      ]);
      setCustomer(customerResult);
      setNotes(notesResult);
      setReports(reportsResult);
      setSourceRecord(sourceList.find((item) => item.id === c.source_id) ?? null);
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : "Failed to load case.");
    }
  }, [caseId]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleResolveSubmit(e: FormEvent) {
    e.preventDefault();
    if (!caseData) return;
    setResolving(true);
    setResolveError(null);
    try {
      await api.updateCase(caseData.id, {
        status: resolveForm.status,
        resolution: resolveForm.resolution || undefined,
        resolution_notes: resolveForm.resolutionNotes || undefined,
        assigned_to: resolveForm.assignedTo || undefined,
      });
      await load();
    } catch (err) {
      setResolveError(err instanceof ApiError ? err.message : "Failed to update case.");
    } finally {
      setResolving(false);
    }
  }

  async function handleAddNote(e: FormEvent) {
    e.preventDefault();
    if (!caseData) return;
    setAddingNote(true);
    setNoteError(null);
    try {
      await api.addCaseNote(caseData.id, { author: noteAuthor, body: noteBody });
      setNoteBody("");
      await load();
    } catch (err) {
      setNoteError(err instanceof ApiError ? err.message : "Failed to add note.");
    } finally {
      setAddingNote(false);
    }
  }

  async function handleGenerateReport() {
    if (!caseData) return;
    setGeneratingReport(true);
    setReportError(null);
    try {
      await api.generateReport(caseData.id, { report_type: "STR" });
      await load();
    } catch (err) {
      setReportError(err instanceof ApiError ? err.message : "Failed to generate report.");
    } finally {
      setGeneratingReport(false);
    }
  }

  if (loadError) return <p className="error-text">{loadError}</p>;
  if (!caseData) return <p>Loading…</p>;

  const canGenerateReport = caseData.status === "resolved" && caseData.resolution === "confirmed";

  return (
    <div>
      <p>
        <Link to="/cases">&larr; Back to case queue</Link>
      </p>
      <h1>Case {caseData.id}</h1>

      <section className="detail-grid">
        <div>
          <h2>Overview</h2>
          <dl className="field-list">
            <dt>Priority</dt>
            <dd>
              <Badge value={caseData.priority} />
            </dd>
            <dt>Status</dt>
            <dd>
              <Badge value={caseData.status} />
            </dd>
            <dt>Resolution</dt>
            <dd>
              <Badge value={caseData.resolution} />
            </dd>
            <dt>Customer</dt>
            <dd>{customer ? `${customer.full_name} (${customer.email})` : caseData.customer_id}</dd>
            <dt>Source</dt>
            <dd>{caseData.source_type.replace("_", " ")}</dd>
            <dt>Opened</dt>
            <dd>{new Date(caseData.opened_at).toLocaleString()}</dd>
            <dt>Resolved</dt>
            <dd>{caseData.resolved_at ? new Date(caseData.resolved_at).toLocaleString() : "—"}</dd>
            <dt>Assigned to</dt>
            <dd>{caseData.assigned_to ?? "—"}</dd>
          </dl>
        </div>

        <div>
          <h2>Triggering record</h2>
          {sourceRecord ? <SourceRecordDetail caseType={caseData.source_type} record={sourceRecord} /> : <p>—</p>}
        </div>
      </section>

      <section>
        <h2>Resolve</h2>
        <form className="resolve-form" onSubmit={handleResolveSubmit}>
          <label>
            Status
            <select
              value={resolveForm.status}
              onChange={(e) => setResolveForm({ ...resolveForm, status: e.target.value as CaseStatus })}
            >
              <option value="open">Open</option>
              <option value="in_review">In review</option>
              <option value="resolved">Resolved</option>
            </select>
          </label>
          <label>
            Resolution
            <select
              value={resolveForm.resolution}
              onChange={(e) =>
                setResolveForm({ ...resolveForm, resolution: e.target.value as CaseResolution | "" })
              }
            >
              <option value="">—</option>
              <option value="confirmed">Confirmed</option>
              <option value="false_positive">False positive</option>
              <option value="escalated">Escalated</option>
            </select>
          </label>
          <label>
            Assigned to
            <input
              type="text"
              value={resolveForm.assignedTo}
              onChange={(e) => setResolveForm({ ...resolveForm, assignedTo: e.target.value })}
            />
          </label>
          <label>
            Resolution notes
            <textarea
              value={resolveForm.resolutionNotes}
              onChange={(e) => setResolveForm({ ...resolveForm, resolutionNotes: e.target.value })}
              rows={3}
            />
          </label>
          {resolveError && <p className="error-text">{resolveError}</p>}
          <button type="submit" disabled={resolving}>
            {resolving ? "Saving…" : "Save"}
          </button>
        </form>
      </section>

      <section>
        <h2>Notes</h2>
        <ul className="note-list">
          {notes.map((n) => (
            <li key={n.id}>
              <div className="note-meta">
                <strong>{n.author}</strong> — {new Date(n.created_at).toLocaleString()}
              </div>
              <div>{n.body}</div>
            </li>
          ))}
          {notes.length === 0 && <li className="empty-state">No notes yet.</li>}
        </ul>
        <form className="note-form" onSubmit={handleAddNote}>
          <input
            type="text"
            placeholder="Author"
            value={noteAuthor}
            onChange={(e) => setNoteAuthor(e.target.value)}
            required
          />
          <textarea
            placeholder="Add a note…"
            value={noteBody}
            onChange={(e) => setNoteBody(e.target.value)}
            rows={2}
            required
          />
          {noteError && <p className="error-text">{noteError}</p>}
          <button type="submit" disabled={addingNote}>
            {addingNote ? "Adding…" : "Add note"}
          </button>
        </form>
      </section>

      <section>
        <h2>Regulatory reports</h2>
        <ul className="report-list">
          {reports.map((r) => (
            <li key={r.id}>
              <Badge value={r.status} /> {r.report_type} — {r.provider_reference ?? r.error_detail} (
              {new Date(r.submitted_at).toLocaleString()})
            </li>
          ))}
          {reports.length === 0 && <li className="empty-state">No reports filed yet.</li>}
        </ul>
        {reportError && <p className="error-text">{reportError}</p>}
        <button onClick={handleGenerateReport} disabled={!canGenerateReport || generatingReport}>
          {generatingReport ? "Generating…" : "Generate Report"}
        </button>
        {!canGenerateReport && (
          <p className="hint">Case must be resolved with resolution "confirmed" before a report can be filed.</p>
        )}
      </section>
    </div>
  );
}

function SourceRecordDetail({
  caseType,
  record,
}: {
  caseType: "sanctions_screening" | "transaction_alert";
  record: SourceRecord;
}) {
  if (caseType === "sanctions_screening") {
    const screening = record as SanctionsScreeningRead;
    return (
      <dl className="field-list">
        <dt>Screened name</dt>
        <dd>{screening.screened_name}</dd>
        <dt>Status</dt>
        <dd>
          <Badge value={screening.status} />
        </dd>
        <dt>Highest score</dt>
        <dd>{screening.highest_score ?? "—"}</dd>
        <dt>Hits</dt>
        <dd>
          {screening.hits.length === 0
            ? "—"
            : screening.hits.map((h) => `${h.matched_name} (${h.list_name}, ${h.score})`).join("; ")}
        </dd>
      </dl>
    );
  }

  const alert = record as TransactionAlertRead;
  return (
    <dl className="field-list">
      <dt>Rule</dt>
      <dd>{alert.rule_code}</dd>
      <dt>Severity</dt>
      <dd>
        <Badge value={alert.severity} />
      </dd>
      <dt>Detail</dt>
      <dd className="mono">{JSON.stringify(alert.detail)}</dd>
    </dl>
  );
}
