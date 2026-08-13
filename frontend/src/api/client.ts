import type {
  CaseNoteCreate,
  CaseNoteRead,
  CaseRead,
  CaseUpdate,
  CustomerRead,
  ReportCreate,
  ReportRead,
  SanctionsScreeningRead,
  TransactionAlertRead,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const STORAGE_KEY = "regtech_api_key";

export function getStoredApiKey(): string | null {
  return localStorage.getItem(STORAGE_KEY);
}

export function setStoredApiKey(key: string): void {
  localStorage.setItem(STORAGE_KEY, key);
}

export function clearStoredApiKey(): void {
  localStorage.removeItem(STORAGE_KEY);
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  apiKeyOverride?: string; // used only by the connect screen, to validate a key before it's stored
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const apiKey = options.apiKeyOverride ?? getStoredApiKey();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (apiKey) headers.Authorization = `Bearer ${apiKey}`;

  const res = await fetch(`${BASE_URL}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  if (!res.ok) {
    // FastAPI's HTTPException shape is {"detail": "..."}; validation errors
    // (422) instead carry {"detail": [{"msg": "...", ...}, ...]}.
    const body = await res.json().catch(() => null);
    const detail = body?.detail;
    const message = Array.isArray(detail)
      ? detail.map((d: { msg?: string }) => d.msg).join("; ")
      : (detail ?? res.statusText);
    throw new ApiError(res.status, message);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

function query(params: Record<string, string | undefined>): string {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== "");
  if (entries.length === 0) return "";
  return `?${new URLSearchParams(entries as [string, string][]).toString()}`;
}

export const api = {
  listCases: (filters: { status?: string; customer_id?: string } = {}) =>
    request<CaseRead[]>(`/cases${query(filters)}`),
  getCase: (caseId: string) => request<CaseRead>(`/cases/${caseId}`),
  updateCase: (caseId: string, payload: CaseUpdate) =>
    request<CaseRead>(`/cases/${caseId}`, { method: "PATCH", body: payload }),

  listCaseNotes: (caseId: string) => request<CaseNoteRead[]>(`/cases/${caseId}/notes`),
  addCaseNote: (caseId: string, payload: CaseNoteCreate) =>
    request<CaseNoteRead>(`/cases/${caseId}/notes`, { method: "POST", body: payload }),

  listReports: (caseId: string) => request<ReportRead[]>(`/cases/${caseId}/reports`),
  generateReport: (caseId: string, payload: ReportCreate = {}) =>
    request<ReportRead>(`/cases/${caseId}/reports`, { method: "POST", body: payload }),

  getCustomer: (customerId: string) => request<CustomerRead>(`/customers/${customerId}`),

  listSanctionsScreenings: (customerId: string) =>
    request<SanctionsScreeningRead[]>(`/customers/${customerId}/sanctions-screenings`),
  listTransactionAlerts: (customerId: string) =>
    request<TransactionAlertRead[]>(`/customers/${customerId}/transaction-alerts`),

  // Used only to validate a freshly-entered key before storing it.
  validateApiKey: (apiKey: string) => request<CaseRead[]>("/cases", { apiKeyOverride: apiKey }),
};
