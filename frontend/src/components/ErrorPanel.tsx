import type { ApiError } from "../api/client";

/**
 * [ENGINEERING RECOMMENDATION] Renders exactly the sanitized error the
 * backend (or the network layer) returned - `detail`/`error_type` for an
 * HTTP error (docs Phase 17 Section M: the backend itself never leaks a
 * traceback/credential/filesystem path, so there is nothing sensitive to
 * accidentally forward here), or a plain network-failure message. Never
 * shows a raw stack trace or internal client detail.
 */
export function ErrorPanel({ error }: { error: ApiError }) {
  const { failure } = error;

  let title = "Something went wrong";
  let detail = error.message;

  if (failure.kind === "http_error") {
    if (failure.status === 503) {
      title = "Backend unavailable";
    } else if (failure.status === 422) {
      title = "Request was rejected";
    } else if (failure.status >= 500) {
      title = "Server error";
    }
    detail = failure.body.detail;
  } else if (failure.kind === "network_error") {
    title = "Could not reach the backend";
  } else if (failure.kind === "malformed_response") {
    title = "Unexpected response from the backend";
  }

  return (
    <section className="panel error-panel" role="alert" aria-labelledby="error-heading">
      <h2 id="error-heading">{title}</h2>
      <p>{detail}</p>
    </section>
  );
}
