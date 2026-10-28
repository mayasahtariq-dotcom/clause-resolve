// Mirrors the backend HTTP contract (clauselens/api/schemas.py + domain models).

export type InvestigationStatus =
  | "queued"
  | "running"
  | "extracting"
  | "validating"
  | "comparing"
  | "completed"
  | "partial"
  | "failed";

export type VendorRunStatus = "pending" | "researching" | "extracting" | "completed" | "failed";
export type FieldStatus = "found" | "unverified" | "ambiguous" | "contradictory" | "not_found" | "unknown";
export type Verification = "verified" | "not_in_source" | "source_missing";
export type Confidence = "high" | "medium" | "low" | "insufficient";

export interface Priority {
  criterion: string;
  weight: number;
}

export interface ApiErrorInfo {
  message: string | null;
  category: string | null;
  provider?: string | null;
  stage?: string | null;
}

export interface VendorStatus {
  id: string;
  name: string;
  domain: string | null;
  status: VendorRunStatus;
  error: ApiErrorInfo | null;
  domain_source: string | null;
  source_count: number;
}

export interface SourceView {
  id: string;
  vendor_id: string;
  source_key: string;
  url: string;
  final_url: string | null;
  title: string | null;
  retrieved_at: string;
  provider: string;
  content_length: number;
  injection_suspected: boolean;
}

export interface Investigation {
  id: string;
  status: InvestigationStatus;
  is_terminal: boolean;
  created_at: string;
  updated_at: string;
  is_demo: boolean;
  providers: Record<string, string>;
  priorities: Priority[];
  error: ApiErrorInfo | null;
  report_id: string | null;
  vendors: VendorStatus[];
  sources: SourceView[];
}

export interface InvestigationSummary {
  id: string;
  status: InvestigationStatus;
  created_at: string;
  vendor_names: string[];
  report_id: string | null;
  is_demo: boolean;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface InvestigationEvent {
  seq: number;
  created_at: string;
  stage: string;
  level: "info" | "warning" | "error";
  message: string;
  vendor_name: string | null;
  data: Record<string, unknown>;
}

export interface Vendor {
  id: string;
  name: string;
  domain: string | null;
}

export interface ComparisonCell {
  vendor_id: string;
  field: string;
  status: FieldStatus;
  display: string;
  normalized: Record<string, unknown>;
  evidence_ids: string[];
  is_best: boolean;
}

export interface CriterionScore {
  criterion: string;
  weight: number;
  scores: Record<string, number | null>;
  explanation: string;
}

export interface Recommendation {
  vendor_id: string | null;
  headline: string;
  rationale: string[];
  confidence: Confidence;
  coverage: Record<string, number>;
  totals: Record<string, number>;
}

export interface ComparisonReport {
  id: string;
  investigation_id: string | null;
  created_at: string;
  vendors: Vendor[];
  priorities: Priority[];
  cells: ComparisonCell[];
  criteria: CriterionScore[];
  recommendation: Recommendation;
  contradictions: string[];
  missing: string[];
  explanation: string | null;
  explanation_status: "generated" | "rejected" | "failed" | "not_requested";
  scoring_policy: Record<string, number>;
  snapshot_ids: string[];
  is_demo: boolean;
  disclaimer: string;
}

export interface Evidence {
  id: string;
  field: string;
  source_key: string;
  source_url: string | null;
  quote: string;
  retrieved_at: string | null;
  verification: Verification;
  match_method: string | null;
  extraction: Record<string, string>;
  vendor_id: string;
  vendor_name: string;
  source_title: string | null;
}

export interface FieldMeta {
  key: string;
  label: string;
  kind: string;
  description: string;
}

export interface CriterionMeta {
  key: string;
  label: string;
  default_weight: number;
}

export interface Meta {
  demo_mode: boolean;
  demo_vendors: { name: string; domain: string }[];
  providers: Record<string, string | boolean>;
  max_vendors: number;
  fields: FieldMeta[];
  criteria: CriterionMeta[];
}

export interface VendorInput {
  name: string;
  domain?: string;
}
