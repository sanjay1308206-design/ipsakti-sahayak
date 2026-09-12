/**
 * TypeScript mirror of the Phase 17 backend wire contract
 * (src/api/schemas.py, config/backend_contract.yaml,
 * docs/PHASE_17_BACKEND_PRODUCTIZATION.md Sections K/L).
 *
 * [OFFICIAL SOURCE] Every field name/shape here was copied from the
 * ACTUAL, live-inspected Phase 17 Pydantic models - never guessed or
 * assumed from memory. This file is hand-written rather than generated
 * from the OpenAPI schema (`[ENGINEERING RECOMMENDATION]` - avoids an
 * extra codegen devDependency for a schema this small and this stable
 * within one phase; see docs/PHASE_18_FRONTEND_PRODUCTIZATION.md Section
 * "Known Limitations" for the trade-off this implies).
 *
 * The frontend NEVER re-derives, widens, or narrows any of these closed
 * vocabularies - every status string is treated as an opaque value
 * received from the backend and displayed/branched on for PRESENTATION
 * only (which panel to show), never re-decided.
 */

export interface QueryRequest {
  query: string;
  requested_language?: string | null;
  jurisdiction?: string | null;
  formulation_description?: string | null;
  source_language?: string | null;
}

export interface ClassificationSummary {
  classification_state: string;
  user_intent: string;
  regulatory_track: string;
  requires_evidence: boolean;
  requires_escalation: boolean;
}

export interface JurisdictionSummary {
  state: string;
  normalized_jurisdiction: string | null;
  requires_escalation: boolean;
}

export interface CitationSummary {
  total_references: number;
  valid_count: number;
  invalid_count: number;
  unresolved_count: number;
  citation_integrity_validation_rate: number;
}

export interface ReviewSummary {
  review_request_id: string;
  trigger_reasons: string[];
  priority: string;
  review_status: string;
}

/** Mirrors api.schemas.QueryResponse exactly - field-for-field, nothing added, nothing omitted. */
export interface QueryResponse {
  request_id: string;
  delivery_status: string;
  reason_code: string;
  explanation: string;
  answer_text: string | null;
  answer_language: string | null;
  translation_applied: boolean;
  provider_name: string | null;
  original_query: string;
  canonical_query: string;
  detected_script: string;
  requested_language: string | null;
  classification: ClassificationSummary | null;
  jurisdiction: JurisdictionSummary | null;
  grounding_status: string | null;
  safety_status: string | null;
  cited_evidence_ids: string[];
  citation_summary: CitationSummary | null;
  review: ReviewSummary | null;
  evidence_preservation_status: string;
  synthetic: boolean | null;
}

export interface HealthResponse {
  status: string;
  api_version: string;
  corpus_status: string;
  generation_provider_configured: boolean;
  translation_provider_configured: boolean;
}

/** Mirrors api.schemas.ErrorResponse - the ONLY error shape the backend ever returns. */
export interface ApiErrorBody {
  detail: string;
  error_type: string;
}
