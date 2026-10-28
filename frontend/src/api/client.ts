import type {
  ComparisonReport,
  Evidence,
  Investigation,
  InvestigationEvent,
  InvestigationSummary,
  Meta,
  Page,
  Priority,
  VendorInput,
} from "./types";

export const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError("Cannot reach the ClauseLens API. Check your connection and try again.", 0, "network");
  }
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    let code = "error";
    try {
      const body = (await response.json()) as { error?: { message?: string; code?: string } };
      message = body.error?.message ?? message;
      code = body.error?.code ?? code;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(message, response.status, code);
  }
  return (await response.json()) as T;
}

export const api = {
  meta: () => request<Meta>("/api/meta"),
  createInvestigation: (vendors: VendorInput[], priorities: Priority[], idempotencyKey: string) =>
    request<Investigation>("/api/investigations", {
      method: "POST",
      body: JSON.stringify({ vendors, priorities }),
      headers: { "Idempotency-Key": idempotencyKey },
    }),
  investigation: (id: string) => request<Investigation>(`/api/investigations/${id}`),
  investigations: (limit = 6) => request<Page<InvestigationSummary>>(`/api/investigations?limit=${limit}`),
  events: (id: string, after = 0) =>
    request<InvestigationEvent[]>(`/api/investigations/${id}/events?stream=false&after=${after}`),
  eventsUrl: (id: string) => `${API_BASE}/api/investigations/${id}/events`,
  report: (id: string) => request<ComparisonReport>(`/api/reports/${id}`),
  evidence: (id: string) => request<{ report_id: string; items: Evidence[] }>(`/api/reports/${id}/evidence`),
  recompare: (vendorIds: string[], priorities: Priority[]) =>
    request<ComparisonReport>("/api/comparisons", {
      method: "POST",
      body: JSON.stringify({ vendor_ids: vendorIds, priorities }),
    }),
};
