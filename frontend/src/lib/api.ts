/**
 * Thin client for the FastAPI backend. Keeps fetch/error-handling logic in
 * one place so pages don't repeat it.
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // response wasn't JSON; keep statusText
    }
    throw new ApiError(detail, res.status);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// --- Types (mirroring backend/app/schemas) ---

export interface Business {
  id: string;
  name: string;
  country: string | null;
  region: string | null;
  city: string | null;
  industry: string | null;
  phone: string | null;
  email: string | null;
  submitted_website_url: string | null;
  created_at: string;
}

export interface BusinessCreate {
  name: string;
  website_url?: string;
  country?: string;
  region?: string;
  city?: string;
  industry?: string;
  phone?: string;
  email?: string;
  notes?: string;
}

export type AuditItemKind = "FACT" | "AI_INFERENCE" | "RECOMMENDATION";

export interface AuditItem {
  kind: AuditItemKind;
  label: string;
  value: unknown;
}

export interface Audit {
  summary: string;
  website_score: number;
  category_scores: Record<string, number>;
  opportunity: {
    type: string;
    confidence: number;
    reasons: string[];
    recommended_service: string | null;
  };
  items: AuditItem[];
  priority_next_steps: string[];
  ai_generation_succeeded: boolean;
  ai_model: string;
}

export interface OutreachDraft {
  subject: string;
  body: string;
  ai_generation_succeeded: boolean;
  ai_model: string;
  requires_human_approval: boolean;
}

export interface PipelineResult {
  business: Business;
  website_status: string;
  pages_crawled: number;
  facts: Record<string, unknown>;
  quality_score: {
    overall: number;
    categories: Record<string, number>;
    reasons: { label: string; points: number }[];
  };
  opportunity: {
    type: string;
    confidence: number;
    reasons: string[];
    recommended_service: string | null;
  };
  lead_score: {
    overall: number;
    reasons: { label: string; points: number }[];
  };
  audit: Audit;
  outreach_draft: OutreachDraft | null;
}

export interface OutreachDraftRecord {
  id: string;
  subject: string;
  body: string;
  approved: boolean;
  ai_model: string;
}

// --- API calls ---

export const api = {
  listBusinesses: () => request<Business[]>("/api/businesses"),
  getBusiness: (id: string) => request<Business>(`/api/businesses/${id}`),
  createBusiness: (payload: BusinessCreate) =>
    request<Business>("/api/businesses", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  analyzeBusiness: (id: string) =>
    request<PipelineResult>(`/api/businesses/${id}/analyze`, {
      method: "POST",
    }),
  getAnalysis: (id: string) =>
    request<PipelineResult>(`/api/businesses/${id}/analysis`),
  getOutreachDraft: (id: string) =>
    request<OutreachDraftRecord>(`/api/businesses/${id}/outreach-draft`),
  approveOutreachDraft: (id: string) =>
    request<{ id: string; approved: boolean }>(
      `/api/businesses/${id}/outreach-draft/approve`,
      { method: "POST" }
    ),
};
