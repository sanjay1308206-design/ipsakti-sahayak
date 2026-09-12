import type { QueryResponse } from "../api/types";

/**
 * [OFFICIAL SOURCE] Only ever renders `classification`/`jurisdiction` when
 * the backend actually included them - never inferred or filled in on
 * the frontend (docs "Classification area" / "Jurisdiction area": "Only
 * display... that the backend actually exposes... Never infer
 * jurisdiction in React").
 */
export function ClassificationJurisdictionPanel({ response }: { response: QueryResponse }) {
  if (!response.classification && !response.jurisdiction) {
    return null;
  }
  return (
    <section className="panel classification-panel" aria-labelledby="classification-heading">
      <h2 id="classification-heading">Classification &amp; Jurisdiction</h2>
      <div className="two-column">
        {response.classification && (
          <div>
            <h3>Formulation classification</h3>
            <dl>
              <div>
                <dt>State</dt>
                <dd>{response.classification.classification_state}</dd>
              </div>
              <div>
                <dt>User intent</dt>
                <dd>{response.classification.user_intent}</dd>
              </div>
              <div>
                <dt>Regulatory track</dt>
                <dd>{response.classification.regulatory_track}</dd>
              </div>
              <div>
                <dt>Requires more evidence</dt>
                <dd>{response.classification.requires_evidence ? "Yes" : "No"}</dd>
              </div>
              <div>
                <dt>Requires escalation</dt>
                <dd>{response.classification.requires_escalation ? "Yes" : "No"}</dd>
              </div>
            </dl>
          </div>
        )}
        {response.jurisdiction && (
          <div>
            <h3>Jurisdiction decision</h3>
            <dl>
              <div>
                <dt>State</dt>
                <dd>{response.jurisdiction.state}</dd>
              </div>
              <div>
                <dt>Resolved jurisdiction</dt>
                <dd>{response.jurisdiction.normalized_jurisdiction ?? "Not resolved"}</dd>
              </div>
              <div>
                <dt>Requires escalation</dt>
                <dd>{response.jurisdiction.requires_escalation ? "Yes" : "No"}</dd>
              </div>
            </dl>
          </div>
        )}
      </div>
    </section>
  );
}
