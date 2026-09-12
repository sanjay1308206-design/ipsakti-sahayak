/**
 * Presentation-only outcome bucketing (docs/PHASE_18_FRONTEND_PRODUCTIZATION.md
 * Section "State Management").
 *
 * [ENGINEERING RECOMMENDATION] This function reads ALREADY-DECIDED backend
 * fields (`safety_status`, `delivery_status`) and buckets them into one of
 * a small set of UI layout categories. It NEVER computes, infers, or
 * overrides a domain decision - `SAFE_TO_PRESENT`/`ABSTAIN`/`ESCALATE`
 * were decided by Phase 13 before this response ever reached the browser.
 * This is the ONLY place in the frontend that branches on a domain field
 * value, and it exists purely to answer "which panel emphasis should the
 * UI use," never "is this answer correct/safe."
 */

import type { QueryResponse } from "./types";

export type QueryOutcome = "SUCCESS" | "ABSTAINED" | "ESCALATED";

export function classifyOutcome(response: QueryResponse): QueryOutcome {
  if (response.safety_status === "ESCALATE") {
    return "ESCALATED";
  }
  if (response.delivery_status === "DELIVERED" && response.safety_status === "SAFE_TO_PRESENT") {
    return "SUCCESS";
  }
  // Covers ABSTAIN, UPSTREAM_BLOCKED, TRANSLATION_FAILED,
  // UNSUPPORTED_LANGUAGE, GENERATION_FAILED, and a missing/null status -
  // all deliberately grouped as "no normal grounded answer was
  // delivered," never silently treated as SUCCESS.
  return "ABSTAINED";
}
