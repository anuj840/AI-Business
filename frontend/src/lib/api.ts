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
  notes: string | null;
  submitted_website_url: string | null;
  created_at: string;
  source_name: string | null;
  discovered_at: string | null;
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
  has_contact_channel: boolean;
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

export interface DiscoveryRequest {
  country: string;
  region?: string;
  city?: string;
  industry: string;
  max_results?: number;
}

export interface FindContactResult {
  phone: string | null;
  email: string | null;
  reachable: boolean;
  pages_checked: number;
  updated: boolean;
}

export interface JobStatus {
  id: string;
  job_type: string;
  status: "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED" | "RETRYING" | "CANCELLED";
  business_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
  retry_count: number;
  metadata: Record<string, unknown>;
}

export interface AnalyticsSummary {
  total_businesses: number;
  analyzed: number;
  not_analyzed: number;
  reachable: number;
  website_status_breakdown: Record<string, number>;
  opportunity_breakdown: Record<string, number>;
  priority_tier_breakdown: Record<string, number>;
  source_breakdown: Record<string, number>;
  outreach_drafts_total: number;
  outreach_drafts_approved: number;
  jobs_in_progress: number;
  jobs_failed: number;
}

export interface HotDeal {
  business_id: string;
  name: string;
  city: string | null;
  region: string | null;
  phone: string | null;
  email: string | null;
  lead_score: number;
  priority: "HIGH_PRIORITY" | "GOOD" | "MEDIUM" | "LOW";
  opportunity_type: string;
  recommended_service: string | null;
  has_outreach_draft: boolean;
  outreach_approved: boolean;
}

export interface DiscoveryResult {
  found: number;
  created: number;
  skipped_duplicates: number;
  businesses: Business[];
  source_error: string | null;
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
  findContact: (id: string) =>
    request<FindContactResult>(`/api/businesses/${id}/find-contact`, {
      method: "POST",
    }),
  analyzeBusiness: (id: string) =>
    request<{ job_id: string; status: string }>(`/api/businesses/${id}/analyze`, {
      method: "POST",
    }),
  getAnalysis: (id: string) =>
    request<PipelineResult>(`/api/businesses/${id}/analysis`),
  getJob: (jobId: string) => request<JobStatus>(`/api/jobs/${jobId}`),
  getOutreachDraft: (id: string) =>
    request<OutreachDraftRecord>(`/api/businesses/${id}/outreach-draft`),
  approveOutreachDraft: (id: string) =>
    request<{ id: string; approved: boolean }>(
      `/api/businesses/${id}/outreach-draft/approve`,
      { method: "POST" }
    ),
  runDiscovery: (payload: DiscoveryRequest) =>
    request<DiscoveryResult>("/api/discovery/run", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getAnalyticsSummary: () => request<AnalyticsSummary>("/api/analytics/summary"),
  getHotDeals: (limit = 20) =>
    request<HotDeal[]>(`/api/analytics/hot-deals?limit=${limit}`),
};
