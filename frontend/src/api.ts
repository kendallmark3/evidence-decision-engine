export type Decision = "READY" | "NOT_READY" | "NEEDS_REVIEW";

export interface Finding {
  policy_id: string;
  title: string;
  evidence_ref: string;
  observed?: unknown;
  remediation?: string;
}

export interface Evaluation {
  evaluation_id: string;
  status: "awaiting_review" | "complete" | "running";
  model_provider: string;
  iteration: number;
  request: { application: string; use_case?: string; owner?: string };
  findings: { passed: Finding[]; violations: Finding[]; missing: Finding[]; not_applicable: Finding[] };
  assessment: {
    decision?: Decision;
    rationale?: string;
    cited_evidence?: string[];
    contradictions?: { claim: string; evidence_ref: string; explanation: string }[];
    remediation?: string[];
    error?: string;
  };
  gate: { decision: Decision; reasons: string[]; overrode_model: boolean; invented_citations: string[]; model_recommendation?: string };
  approval?: { status: string; reviewer?: string; comment?: string };
  review_request?: { reasons: string[]; note: string } | null;
  trace: { node: string; at: string; summary: string }[];
  report?: Record<string, any> & { decision: Decision; recommended_remediation: string[] };
}

export interface Sample { id: string; title: string; expected: string; why: string }

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...init });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.detail ? (typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail)) : r.statusText);
  return body as T;
}

export const api = {
  health: () => req<{ model_provider: string; policy_set: string }>("/api/health"),
  samples: () => req<Sample[]>("/api/samples"),
  sample: (id: string) => req<Record<string, unknown>>(`/api/samples/${id}`),
  evaluate: (config: unknown) => req<Evaluation>("/api/evaluations", { method: "POST", body: JSON.stringify({ config }) }),
  review: (id: string, body: { action: string; reviewer: string; comment: string; evidence?: Record<string, unknown> }) =>
    req<Evaluation>(`/api/evaluations/${id}/review`, { method: "POST", body: JSON.stringify(body) }),
  reportUrl: (id: string) => `/api/evaluations/${id}/report`,
};
