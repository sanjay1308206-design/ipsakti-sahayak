import type { QueryResponse } from "../api/types";

/**
 * [OFFICIAL SOURCE] Citation identifiers are backend-owned
 * (`cited_evidence_ids`, Phase 9/10's own already-validated list) - this
 * component never generates, guesses, or fabricates one. `citation_summary`
 * (Phase 9's own `CitationCoverageMetrics`, reused verbatim) is rendered
 * as-is; the "unresolved/invalid" count is shown honestly WITHOUT
 * inventing the specific identifiers involved, since the current backend
 * contract does not return them (docs "Known Limitations").
 */
export function CitationsPanel({ response }: { response: QueryResponse }) {
  const summary = response.citation_summary;
  const citedIds = response.cited_evidence_ids;

  return (
    <section className="panel citations-panel" aria-labelledby="citations-heading">
      <h2 id="citations-heading">Citations</h2>

      {summary && (
        <dl className="citation-summary-grid">
          <div>
            <dt>Citation attempts</dt>
            <dd>{summary.total_references}</dd>
          </div>
          <div>
            <dt>Valid</dt>
            <dd>{summary.valid_count}</dd>
          </div>
          <div>
            <dt>Integrity rate</dt>
            <dd>{(summary.citation_integrity_validation_rate * 100).toFixed(0)}%</dd>
          </div>
        </dl>
      )}

      {summary && (summary.invalid_count > 0 || summary.unresolved_count > 0) && (
        <p className="citation-unresolved-notice" role="note">
          {summary.invalid_count + summary.unresolved_count} citation attempt(s) could not be resolved to valid
          evidence and are not included in the answer or evidence list below. The specific unresolved reference is
          not exposed by the current API - it is intentionally not guessed or reconstructed here.
        </p>
      )}

      {citedIds.length > 0 ? (
        <ul className="citation-list">
          {citedIds.map((id) => (
            <li key={id}>
              <code className="evidence-id">{id}</code>
            </li>
          ))}
        </ul>
      ) : (
        <p className="citation-empty">No validated citations are associated with this response.</p>
      )}
    </section>
  );
}
