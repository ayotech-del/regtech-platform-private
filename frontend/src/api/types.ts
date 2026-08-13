// Hand-written mirrors of app/schemas/{case,report,customer,sanctions_screening,transaction}.py.
// Deliberately not generated from the OpenAPI schema -- the surface is
// small and stable enough that keeping this in sync by hand is simpler
// than adding a codegen step and dependency for seven shapes.

export type CaseStatus = "open" | "in_review" | "resolved";
export type CaseResolution = "confirmed" | "false_positive" | "escalated";
export type CasePriority = "low" | "medium" | "high";
export type SourceType = "sanctions_screening" | "transaction_alert";

export interface CaseRead {
  id: string;
  tenant_id: string;
  customer_id: string;
  source_type: SourceType;
  source_id: string;
  priority: CasePriority;
  status: CaseStatus;
  resolution: CaseResolution | null;
  resolution_notes: string | null;
  assigned_to: string | null;
  opened_at: string;
  resolved_at: string | null;
  created_at: string;
}

export interface CaseUpdate {
  status?: CaseStatus;
  resolution?: CaseResolution;
  resolution_notes?: string;
  assigned_to?: string;
}

export interface CaseNoteRead {
  id: string;
  tenant_id: string;
  case_id: string;
  author: string;
  body: string;
  created_at: string;
}

export interface CaseNoteCreate {
  author: string;
  body: string;
}

export interface ReportRead {
  id: string;
  tenant_id: string;
  case_id: string;
  customer_id: string;
  report_type: "STR" | "SAR";
  provider_name: string;
  status: "submitted" | "error";
  provider_reference: string | null;
  payload: Record<string, unknown>;
  error_detail: string | null;
  submitted_at: string;
  created_at: string;
}

export interface ReportCreate {
  report_type?: "STR" | "SAR";
}

export interface CustomerRead {
  id: string;
  tenant_id: string;
  full_name: string;
  email: string;
}

export interface WatchlistHitRead {
  matched_name: string;
  list_name: string;
  score: number;
}

export interface SanctionsScreeningRead {
  id: string;
  tenant_id: string;
  customer_id: string;
  screened_name: string;
  provider_name: string;
  status: "clear" | "potential_match" | "error";
  highest_score: number | null;
  match_threshold: number;
  hits: WatchlistHitRead[];
  error_detail: string | null;
  screened_at: string;
  created_at: string;
}

export interface TransactionAlertRead {
  id: string;
  tenant_id: string;
  transaction_id: string;
  customer_id: string;
  rule_code: string;
  severity: "low" | "medium" | "high";
  detail: Record<string, unknown>;
  status: string;
  evaluated_at: string;
  created_at: string;
}
