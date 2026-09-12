import type { QueryResponse } from "../api/types";

/**
 * [OFFICIAL SOURCE] Rendered only when the backend's `review` object is
 * present (Phase 15's own `build_review_request` actually fired) - never
 * fabricated when absent. This panel is READ-ONLY: there is no reviewer
 * workflow, authentication, or action button here (Phase 15's
 * `review.workflow.apply_action` is not exposed by any Phase 17
 * endpoint, so there is nothing for the frontend to call).
 */
export function ReviewPanel({ response }: { response: QueryResponse }) {
  if (!response.review) {
    return null;
  }
  const { review } = response;
  return (
    <section className="panel review-panel" aria-labelledby="review-heading">
      <h2 id="review-heading">Human Review</h2>
      <p>
        This case has been flagged for human review (priority: <strong>{review.priority}</strong>, status:{" "}
        <strong>{review.review_status}</strong>).
      </p>
      <p className="review-reasons-label">Reasons:</p>
      <ul className="review-reasons">
        {review.trigger_reasons.map((reason) => (
          <li key={reason}>{reason}</li>
        ))}
      </ul>
      <p className="review-request-id">
        Review reference: <code>{review.review_request_id}</code>
      </p>
    </section>
  );
}
