import type { QueryResponse } from "../api/types";
import type { QueryOutcome } from "../api/outcome";

/**
 * [OFFICIAL SOURCE] Displays the backend's OWN status fields
 * (`safety_status`, `grounding_status`, `delivery_status`) verbatim -
 * this component never computes a safety/grounding decision, it only
 * chooses a visual style (color/icon) for an already-decided value.
 */
function describeStatus(response: QueryResponse): { label: string; tone: "safe" | "abstain" | "escalate" | "warn" } {
  if (response.safety_status === "ESCALATE") {
    return { label: "Escalated for human review", tone: "escalate" };
  }
  if (response.safety_status === "ABSTAIN") {
    return { label: "System abstained - not enough validated evidence to answer safely", tone: "abstain" };
  }
  if (response.grounding_status === "GENERATION_FAILED") {
    return { label: "Answer generation failed upstream", tone: "warn" };
  }
  if (response.delivery_status === "TRANSLATION_FAILED") {
    return { label: "Translation to the requested language failed", tone: "warn" };
  }
  if (response.delivery_status === "UNSUPPORTED_LANGUAGE") {
    return { label: "The requested language is not currently supported", tone: "warn" };
  }
  if (response.delivery_status === "UPSTREAM_BLOCKED") {
    return { label: "Upstream response unavailable", tone: "warn" };
  }
  if (response.safety_status === "SAFE_TO_PRESENT" && response.delivery_status === "DELIVERED") {
    return { label: "Safe to present", tone: "safe" };
  }
  return { label: "Status unavailable", tone: "warn" };
}

export function StatusBanner({ response, outcome }: { response: QueryResponse; outcome: QueryOutcome }) {
  const { label, tone } = describeStatus(response);
  return (
    <div className={`status-banner status-${tone}`} role="status" data-outcome={outcome}>
      <span className="status-label">{label}</span>
      <p className="status-explanation">{response.explanation}</p>
      <dl className="status-detail-grid">
        <div>
          <dt>Delivery status</dt>
          <dd>{response.delivery_status}</dd>
        </div>
        <div>
          <dt>Safety status</dt>
          <dd>{response.safety_status ?? "Not available"}</dd>
        </div>
        <div>
          <dt>Grounding status</dt>
          <dd>{response.grounding_status ?? "Not available"}</dd>
        </div>
      </dl>
    </div>
  );
}
