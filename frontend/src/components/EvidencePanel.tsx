import type { QueryResponse } from "../api/types";

/**
 * [ENGINEERING RECOMMENDATION] / [DEFERRED]
 *
 * The current Phase 17 response contract exposes only evidence
 * IDENTIFIERS (`cited_evidence_ids`) - it does not return evidence text,
 * source family, jurisdiction tag, or document/chunk/page/block
 * provenance for each item (verified directly against
 * `src/api/schemas.py`/`application/models.py` - no such fields exist).
 *
 * This is a genuine, disclosed backend-contract gap (docs
 * "Known Limitations"/"Deferred Items") - per explicit instruction, the
 * frontend does NOT fabricate evidence text, a source family, a
 * jurisdiction tag, or provenance to fill this gap. It shows exactly
 * what is available (the evidence identifier) and states plainly that
 * further detail is not currently exposed.
 */
export function EvidencePanel({ response }: { response: QueryResponse }) {
  const evidenceIds = response.cited_evidence_ids;

  return (
    <section className="panel evidence-panel" aria-labelledby="evidence-heading">
      <h2 id="evidence-heading">Evidence</h2>
      {evidenceIds.length === 0 ? (
        <p className="evidence-empty">No evidence is associated with this response.</p>
      ) : (
        <>
          <p className="evidence-gap-notice" role="note">
            The current API exposes evidence identifiers only. Evidence text, source family, jurisdiction tag,
            and document/page/block provenance are not yet returned by the backend for display here (see Known
            Limitations in the Phase 18 documentation) - nothing below is invented to compensate.
          </p>
          <ul className="evidence-list">
            {evidenceIds.map((id) => (
              <li key={id} className="evidence-card">
                <span className="evidence-card-label">Evidence ID</span>
                <code className="evidence-id">{id}</code>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
