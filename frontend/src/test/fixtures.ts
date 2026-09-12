/**
 * Deterministic test fixtures shaped exactly like real Phase 17 backend
 * responses (docs/PHASE_18_FRONTEND_PRODUCTIZATION.md Section "Testing").
 * These mirror the same synthetic scenarios the Python test suite already
 * exercises against the real backend (e.g. tests/test_phase_17_api.py) -
 * never a live Gemini/Qwen/Bhashini call, never real regulatory corpus
 * data.
 */

import type { QueryResponse } from "../api/types";

export function makeSafeResponse(overrides: Partial<QueryResponse> = {}): QueryResponse {
  return {
    request_id: "a".repeat(64),
    delivery_status: "DELIVERED",
    reason_code: "TRANSLATION_SUCCEEDED",
    explanation: "Delivered: translated to 'hi' via 'fake-translation-provider'.",
    answer_text: "Ayurveda formulation registration follows AYUSH ministry compliance rules. [[CITE:" + "e".repeat(64) + "]]",
    answer_language: "en",
    translation_applied: false,
    provider_name: "fake-provider",
    original_query: "Tell me about Ministry of Ayush policy in India.",
    canonical_query: "Tell me about Ministry of Ayush policy in India.",
    detected_script: "LATIN",
    requested_language: null,
    classification: {
      classification_state: "KNOWN",
      user_intent: "GENERAL_INFORMATION_REQUEST",
      regulatory_track: "UNDETERMINED",
      requires_evidence: false,
      requires_escalation: false,
    },
    jurisdiction: {
      state: "KNOWN",
      normalized_jurisdiction: "INDIA",
      requires_escalation: false,
    },
    grounding_status: "GROUNDED",
    safety_status: "SAFE_TO_PRESENT",
    cited_evidence_ids: ["e".repeat(64)],
    citation_summary: {
      total_references: 1,
      valid_count: 1,
      invalid_count: 0,
      unresolved_count: 0,
      citation_integrity_validation_rate: 1.0,
    },
    review: null,
    evidence_preservation_status: "PRESERVED",
    synthetic: true,
    ...overrides,
  };
}

export function makeAbstainResponse(overrides: Partial<QueryResponse> = {}): QueryResponse {
  return {
    request_id: "b".repeat(64),
    delivery_status: "UPSTREAM_BLOCKED",
    reason_code: "SAFETY_NOT_SAFE_TO_PRESENT",
    explanation: "Blocked: Phase 13 did not mark this response SAFE_TO_PRESENT.",
    answer_text: null,
    answer_language: null,
    translation_applied: false,
    provider_name: null,
    original_query: "What license do I need?",
    canonical_query: "What license do I need?",
    detected_script: "LATIN",
    requested_language: null,
    classification: {
      classification_state: "KNOWN",
      user_intent: "GENERAL_INFORMATION_REQUEST",
      regulatory_track: "UNDETERMINED",
      requires_evidence: false,
      requires_escalation: false,
    },
    jurisdiction: {
      state: "KNOWN",
      normalized_jurisdiction: "INDIA",
      requires_escalation: false,
    },
    grounding_status: "ABSTAINED",
    safety_status: "ABSTAIN",
    cited_evidence_ids: [],
    citation_summary: {
      total_references: 0,
      valid_count: 0,
      invalid_count: 0,
      unresolved_count: 0,
      citation_integrity_validation_rate: 0.0,
    },
    review: {
      review_request_id: "c".repeat(64),
      trigger_reasons: ["SAFETY_ABSTAIN", "GROUNDING_FAILURE"],
      priority: "HIGH",
      review_status: "PENDING",
    },
    evidence_preservation_status: "PRESERVED",
    synthetic: null,
    ...overrides,
  };
}

export function makeEscalateResponse(overrides: Partial<QueryResponse> = {}): QueryResponse {
  return {
    request_id: "d".repeat(64),
    delivery_status: "UPSTREAM_BLOCKED",
    reason_code: "SAFETY_NOT_SAFE_TO_PRESENT",
    explanation: "Blocked: Phase 13 did not mark this response SAFE_TO_PRESENT.",
    answer_text: null,
    answer_language: null,
    translation_applied: false,
    provider_name: null,
    original_query: "how can i protect this and what compliance requirement applies in India",
    canonical_query: "how can i protect this and what compliance requirement applies in India",
    detected_script: "LATIN",
    requested_language: null,
    classification: {
      classification_state: "AMBIGUOUS",
      user_intent: "AMBIGUOUS_INTENT",
      regulatory_track: "UNDETERMINED",
      requires_evidence: false,
      requires_escalation: true,
    },
    jurisdiction: null,
    grounding_status: null,
    safety_status: "ESCALATE",
    cited_evidence_ids: [],
    citation_summary: null,
    review: {
      review_request_id: "f".repeat(64),
      trigger_reasons: ["SAFETY_ESCALATE", "CLASSIFICATION_AMBIGUOUS"],
      priority: "CRITICAL",
      review_status: "PENDING",
    },
    evidence_preservation_status: "PRESERVED",
    synthetic: null,
    ...overrides,
  };
}

export function makeUnresolvedCitationResponse(overrides: Partial<QueryResponse> = {}): QueryResponse {
  return makeSafeResponse({
    citation_summary: {
      total_references: 3,
      valid_count: 1,
      invalid_count: 1,
      unresolved_count: 1,
      citation_integrity_validation_rate: 1 / 3,
    },
    ...overrides,
  });
}
