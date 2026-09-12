/**
 * Typed API client for the Phase 17 backend
 * (docs/PHASE_18_FRONTEND_PRODUCTIZATION.md Section "API Client").
 *
 * [ENGINEERING RECOMMENDATION] This module centralizes the API base URL,
 * request/response typing, and HTTP/network error translation. It
 * contains NO business rule of any kind - it never inspects a domain
 * field (safety_status, jurisdiction, classification_state, an evidence
 * id) to decide anything; it only moves bytes and reports what actually
 * happened (HTTP status + parsed body, or a network failure).
 */

import type { ApiErrorBody, HealthResponse, QueryRequest, QueryResponse } from "./types";

/**
 * [ENGINEERING RECOMMENDATION] Base URL is read once from Vite's env
 * mechanism (`VITE_API_BASE_URL`), defaulting to same-origin relative
 * paths for local development against `vite dev --proxy` or a
 * same-host deployment. No API key, token, or credential is read or
 * sent by this client anywhere - none exists in the Phase 17 contract.
 */
const API_BASE_URL: string =
  (typeof import.meta !== "undefined" && (import.meta as ImportMeta).env?.VITE_API_BASE_URL) || "";

/** A structured, typed representation of every way a request to the backend can fail - never a bare thrown string. */
export type ApiFailure =
  | { kind: "http_error"; status: number; body: ApiErrorBody }
  | { kind: "malformed_response"; status: number }
  | { kind: "network_error"; message: string };

export class ApiError extends Error {
  readonly failure: ApiFailure;

  constructor(failure: ApiFailure) {
    super(ApiError.describe(failure));
    this.name = "ApiError";
    this.failure = failure;
  }

  private static describe(failure: ApiFailure): string {
    switch (failure.kind) {
      case "http_error":
        return `Request failed (${failure.status}): ${failure.body.detail}`;
      case "malformed_response":
        return `Backend returned an unexpected response shape (HTTP ${failure.status}).`;
      case "network_error":
        return `Could not reach the backend: ${failure.message}`;
    }
  }
}

function isApiErrorBody(value: unknown): value is ApiErrorBody {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as Record<string, unknown>).detail === "string" &&
    typeof (value as Record<string, unknown>).error_type === "string"
  );
}

async function request<TResponse>(path: string, init?: RequestInit): Promise<TResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch (error) {
    throw new ApiError({
      kind: "network_error",
      message: error instanceof Error ? error.message : "unknown network failure",
    });
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    if (!response.ok) {
      throw new ApiError({ kind: "malformed_response", status: response.status });
    }
    throw new ApiError({ kind: "malformed_response", status: response.status });
  }

  if (!response.ok) {
    if (isApiErrorBody(body)) {
      throw new ApiError({ kind: "http_error", status: response.status, body });
    }
    throw new ApiError({ kind: "malformed_response", status: response.status });
  }

  return body as TResponse;
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health", { method: "GET" });
}

export function postQuery(payload: QueryRequest): Promise<QueryResponse> {
  return request<QueryResponse>("/api/v1/query", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
