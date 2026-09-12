import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, getHealth, postQuery } from "./client";
import { makeSafeResponse } from "../test/fixtures";

function mockFetchOnce(status: number, body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: status >= 200 && status < 300,
      status,
      json: async () => body,
    }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api client", () => {
  it("returns a typed QueryResponse on success", async () => {
    const fixture = makeSafeResponse();
    mockFetchOnce(200, fixture);
    const result = await postQuery({ query: "test" });
    expect(result).toEqual(fixture);
  });

  it("sends the query payload as the request body", async () => {
    const fixture = makeSafeResponse();
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => fixture });
    vi.stubGlobal("fetch", fetchMock);

    await postQuery({ query: "hello", requested_language: "hi" });

    const [, init] = fetchMock.mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({ query: "hello", requested_language: "hi" });
  });

  it("throws a typed ApiError with the backend's error body on HTTP 503", async () => {
    mockFetchOnce(503, { detail: "a required generation provider is not configured", error_type: "GENERATION_PROVIDER_NOT_CONFIGURED" });
    await expect(postQuery({ query: "test" })).rejects.toMatchObject({
      failure: { kind: "http_error", status: 503, body: { error_type: "GENERATION_PROVIDER_NOT_CONFIGURED" } },
    });
  });

  it("throws a typed ApiError with the backend's error body on HTTP 422", async () => {
    mockFetchOnce(422, { detail: "request payload failed validation", error_type: "REQUEST_VALIDATION_ERROR" });
    await expect(postQuery({ query: "" })).rejects.toBeInstanceOf(ApiError);
  });

  it("throws a network_error ApiError when fetch itself rejects", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(postQuery({ query: "test" })).rejects.toMatchObject({ failure: { kind: "network_error" } });
  });

  it("throws a malformed_response ApiError when the body is not valid JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => {
          throw new SyntaxError("Unexpected token");
        },
      }),
    );
    await expect(postQuery({ query: "test" })).rejects.toMatchObject({ failure: { kind: "malformed_response" } });
  });

  it("never sends a credential-shaped header", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ status: "alive", api_version: "v1", corpus_status: "NOT_VALIDATED", generation_provider_configured: false, translation_provider_configured: false }) });
    vi.stubGlobal("fetch", fetchMock);
    await getHealth();
    const [, init] = fetchMock.mock.calls[0];
    const headerKeys = Object.keys(init.headers).map((k) => k.toLowerCase());
    expect(headerKeys).not.toContain("authorization");
    expect(headerKeys).not.toContain("x-api-key");
  });
});
