import type { QueryResponse } from "../api/types";

/** [OFFICIAL SOURCE] Multilingual preservation fields, rendered verbatim (Phase 14's own contract). */
export function QueryMetaPanel({ response }: { response: QueryResponse }) {
  return (
    <section className="panel query-meta-panel" aria-labelledby="query-meta-heading">
      <h2 id="query-meta-heading">Query Details</h2>
      <dl>
        <div>
          <dt>Original query</dt>
          <dd lang={undefined}>{response.original_query}</dd>
        </div>
        <div>
          <dt>Canonical query</dt>
          <dd>{response.canonical_query}</dd>
        </div>
        <div>
          <dt>Detected script</dt>
          <dd>{response.detected_script}</dd>
        </div>
        <div>
          <dt>Requested language</dt>
          <dd>{response.requested_language ?? "Not specified"}</dd>
        </div>
      </dl>
    </section>
  );
}
