const TONE_BY_VALUE: Record<string, "neutral" | "info" | "warning" | "danger" | "success"> = {
  // priority / severity
  low: "neutral",
  medium: "warning",
  high: "danger",
  // case status
  open: "warning",
  in_review: "info",
  resolved: "success",
  // resolution
  confirmed: "danger",
  false_positive: "neutral",
  escalated: "danger",
  // screening / report / alert status
  clear: "success",
  potential_match: "danger",
  error: "danger",
  submitted: "success",
};

export function Badge({ value }: { value: string | null | undefined }) {
  if (!value) return <span className="badge badge-neutral">—</span>;
  const tone = TONE_BY_VALUE[value] ?? "neutral";
  return <span className={`badge badge-${tone}`}>{value.replace(/_/g, " ")}</span>;
}
