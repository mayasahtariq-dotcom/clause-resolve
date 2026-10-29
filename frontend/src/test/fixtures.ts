import type { ComparisonReport, Evidence, Investigation, InvestigationEvent, Meta } from "../api/types";

export const meta: Meta = {
  demo_mode: true,
  demo_vendors: [
    { name: "StudyNest", domain: "studynest.example" },
    { name: "CourseCove", domain: "coursecove.example" },
    { name: "SkillForge", domain: "skillforge.example" },
  ],
  providers: {},
  max_vendors: 5,
  fields: [
    { key: "refund_window", label: "Refund window", kind: "duration", description: "" },
    { key: "cancellation_fee", label: "Cancellation fee", kind: "fee", description: "" },
  ],
  criteria: [
    { key: "longest_refund_window", label: "Longest refund window", default_weight: 3 },
    { key: "lowest_cancellation_fee", label: "Lowest cancellation fee", default_weight: 2 },
    { key: "easiest_cancellation", label: "Easiest cancellation", default_weight: 2 },
    { key: "longest_trial", label: "Longest free trial", default_weight: 1 },
  ],
};

const A = "11111111-1111-1111-1111-111111111111";
const B = "22222222-2222-2222-2222-222222222222";

export const report: ComparisonReport = {
  id: "rep-1",
  investigation_id: "inv-1",
  created_at: "2026-10-28T10:00:00Z",
  vendors: [
    { id: A, name: "Alpha", domain: "alpha.example" },
    { id: B, name: "Beta", domain: "beta.example" },
  ],
  priorities: [{ criterion: "longest_refund_window", weight: 1 }],
  cells: [
    { vendor_id: A, field: "refund_window", status: "found", display: "30 days", normalized: { days: 30 }, evidence_ids: ["ev-1"], is_best: true },
    { vendor_id: B, field: "refund_window", status: "contradictory", display: "Conflicting: 14 days vs 30 days", normalized: {}, evidence_ids: ["ev-2", "ev-3"], is_best: false },
    { vendor_id: A, field: "cancellation_fee", status: "found", display: "No fee (stated)", normalized: { fee_is_zero: true }, evidence_ids: ["ev-4"], is_best: false },
    { vendor_id: B, field: "cancellation_fee", status: "not_found", display: "Not stated", normalized: {}, evidence_ids: [], is_best: false },
  ],
  criteria: [{ criterion: "longest_refund_window", weight: 1, scores: { [A]: 1, [B]: null }, explanation: "Longest refund window (weight 1)." }],
  recommendation: {
    vendor_id: A,
    headline: "Alpha best matches your priorities based on verified policy text.",
    rationale: ["Longest refund window: only Alpha has verified data."],
    confidence: "medium",
    coverage: { [A]: 1, [B]: 0 },
    totals: { [A]: 1, [B]: 0 },
  },
  contradictions: ["Beta: Refund window: Conflicting: 14 days vs 30 days."],
  missing: ["Beta: Cancellation fee is not stated in the retrieved pages."],
  explanation: null,
  explanation_status: "rejected",
  scoring_policy: {},
  snapshot_ids: [],
  risks: [
    {
      vendor_id: A, vendor_name: "Alpha", status: "completed", chunks_analyzed: 2, chunks_total: 2, warnings: [],
      provider: "openrouter", model: "google/gemini-2.5-flash", error: null,
      clauses: [
        {
          clause: "Automatic annual renewal", risk_level: "high", category: "Renewal",
          explanation: "Your plan renews every year unless you cancel.", reason: "You can be charged without a reminder.",
          evidence: { quote: "Plans renew automatically each year.", source_key: "S1", source_url: "https://alpha.example/terms",
            source_title: "Terms", retrieved_at: "2026-10-28T09:00:00Z", verification: "verified", match_method: "exact" },
        },
        {
          clause: "Short refund window", risk_level: "medium", category: "Refunds",
          explanation: "Refunds only within 7 days.", reason: "Easy to miss.",
          evidence: { quote: "Refunds within 7 days.", source_key: "S1", source_url: "https://alpha.example/terms",
            source_title: "Terms", retrieved_at: null, verification: "not_in_source", match_method: null },
        },
      ],
    },
    {
      vendor_id: B, vendor_name: "Beta", status: "failed", chunks_analyzed: 0, chunks_total: 1,
      warnings: ["Section S1#1 could not be analysed: rate limited"], provider: "openrouter", model: "m",
      error: "The AI provider could not analyse this vendor's pages.", clauses: [],
    },
  ],
  is_demo: false,
  disclaimer: "Not legal advice.",
};

export const evidence: Evidence[] = [
  {
    id: "ev-2", field: "refund_window", source_key: "S1", source_url: "https://beta.example/refunds",
    quote: "Refunds within 14 days of purchase.", retrieved_at: "2026-10-28T09:00:00Z", verification: "verified",
    match_method: "exact", extraction: { provider: "ollama", model: "gpt-oss:120b" }, vendor_id: B, vendor_name: "Beta", source_title: "Refunds",
  },
  {
    id: "ev-3", field: "refund_window", source_key: "S2", source_url: "https://beta.example/faq",
    quote: "We refund for 30 days.", retrieved_at: "2026-10-28T09:00:00Z", verification: "not_in_source",
    match_method: null, extraction: {}, vendor_id: B, vendor_name: "Beta", source_title: null,
  },
];

export function investigation(overrides: Partial<Investigation> = {}): Investigation {
  return {
    id: "inv-1", status: "extracting", is_terminal: false, created_at: "2026-10-28T10:00:00Z", updated_at: "2026-10-28T10:00:05Z",
    is_demo: false, providers: {}, priorities: [], error: null, report_id: null,
    vendors: [
      { id: A, name: "Alpha", domain: "alpha.example", status: "extracting", error: null, domain_source: "user", source_count: 2 },
      { id: B, name: "Beta", domain: null, status: "failed", error: { message: "No policy pages could be retrieved for this vendor", category: "not_found" }, domain_source: null, source_count: 0 },
    ],
    sources: [],
    ...overrides,
  };
}

export const events: InvestigationEvent[] = [
  { seq: 1, created_at: "2026-10-28T10:00:00Z", stage: "queued", level: "info", message: "Investigation queued", vendor_name: null, data: {} },
  { seq: 2, created_at: "2026-10-28T10:00:01Z", stage: "research", level: "error", message: "Research failed: blocked", vendor_name: "Beta", data: {} },
];
