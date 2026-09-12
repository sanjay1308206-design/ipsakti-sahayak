import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import {
  makeAbstainResponse,
  makeEscalateResponse,
  makeSafeResponse,
  makeUnresolvedCitationResponse,
} from "./test/fixtures";

function mockFetchJson(status: number, body: unknown) {
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

// 1. Application renders.
it("renders the application shell", () => {
  render(<App />);
  expect(screen.getByText("IP-SAKTI Sahayak")).toBeInTheDocument();
  expect(screen.getByRole("textbox", { name: /your question/i })).toBeInTheDocument();
});

describe("query submission", () => {
  // 2. Query submission invokes API client.
  it("invokes the API client with the entered query", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => makeSafeResponse() });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);

    await user.type(screen.getByRole("textbox", { name: /your question/i }), "Tell me about Ministry of Ayush policy in India.");
    await user.click(screen.getByRole("button", { name: /^ask$/i }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/api/v1/query");
    expect(JSON.parse(init.body).query).toBe("Tell me about Ministry of Ayush policy in India.");
  });

  // 3. Loading state appears.
  it("shows a loading indicator while the request is in flight", async () => {
    let resolveFetch: (value: unknown) => void = () => {};
    const pending = new Promise((resolve) => {
      resolveFetch = resolve;
    });
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(pending));
    const user = userEvent.setup();
    render(<App />);

    await user.type(screen.getByRole("textbox", { name: /your question/i }), "query");
    await user.click(screen.getByRole("button", { name: /^ask$/i }));

    expect(await screen.findByRole("status", { name: "" })).toBeInTheDocument();
    expect(screen.getByText(/consulting the regulatory knowledge pipeline/i)).toBeInTheDocument();

    resolveFetch({ ok: true, status: 200, json: async () => makeSafeResponse() });
    await waitFor(() => expect(screen.queryByText(/consulting the regulatory knowledge pipeline/i)).not.toBeInTheDocument());
  });

  // 4. Successful grounded response renders.
  it("renders a grounded answer on a SAFE_TO_PRESENT response", async () => {
    mockFetchJson(200, makeSafeResponse());
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByRole("textbox", { name: /your question/i }), "query");
    await user.click(screen.getByRole("button", { name: /^ask$/i }));

    expect(await screen.findByText("Safe to present")).toBeInTheDocument();
    expect(screen.getByText(/Ayurveda formulation registration follows AYUSH/)).toBeInTheDocument();
  });

  // 5. Evidence renders.
  it("renders cited evidence identifiers", async () => {
    const fixture = makeSafeResponse();
    mockFetchJson(200, fixture);
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByRole("textbox", { name: /your question/i }), "query");
    await user.click(screen.getByRole("button", { name: /^ask$/i }));

    await screen.findByText("Safe to present");
    const evidenceHeading = screen.getByRole("heading", { name: "Evidence" });
    const evidenceSection = evidenceHeading.closest("section")!;
    expect(evidenceSection).toHaveTextContent(fixture.cited_evidence_ids[0]);
  });

  // 6. Citation references render.
  it("renders the citation summary", async () => {
    mockFetchJson(200, makeSafeResponse());
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByRole("textbox", { name: /your question/i }), "query");
    await user.click(screen.getByRole("button", { name: /^ask$/i }));

    await screen.findByText("Safe to present");
    const citationsHeading = screen.getByRole("heading", { name: "Citations" });
    const citationsSection = citationsHeading.closest("section")!;
    expect(citationsSection).toHaveTextContent("100%");
  });

  // 7. Unresolved citation is clearly represented.
  it("clearly represents unresolved/invalid citation attempts without inventing detail", async () => {
    mockFetchJson(200, makeUnresolvedCitationResponse());
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByRole("textbox", { name: /your question/i }), "query");
    await user.click(screen.getByRole("button", { name: /^ask$/i }));

    await screen.findByText("Safe to present");
    expect(screen.getByText(/2 citation attempt\(s\) could not be resolved/)).toBeInTheDocument();
  });

  // 8. ABSTAIN state renders correctly.
  it("renders an ABSTAIN outcome without a fabricated answer", async () => {
    mockFetchJson(200, makeAbstainResponse());
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByRole("textbox", { name: /your question/i }), "What license do I need?");
    await user.click(screen.getByRole("button", { name: /^ask$/i }));

    expect(await screen.findByText(/system abstained/i)).toBeInTheDocument();
    expect(screen.getByText(/no grounded answer was produced/i)).toBeInTheDocument();
  });

  // 9. ESCALATE state renders correctly.
  it("renders an ESCALATE outcome with review details", async () => {
    mockFetchJson(200, makeEscalateResponse());
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByRole("textbox", { name: /your question/i }), "how can i protect this");
    await user.click(screen.getByRole("button", { name: /^ask$/i }));

    expect(await screen.findByText(/escalated for human review/i)).toBeInTheDocument();
    expect(screen.getByText("SAFETY_ESCALATE")).toBeInTheDocument();
    expect(screen.getByText("CRITICAL")).toBeInTheDocument();
  });

  // 10. API/network failure renders an error.
  it("renders an error panel on a network failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByRole("textbox", { name: /your question/i }), "query");
    await user.click(screen.getByRole("button", { name: /^ask$/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/could not reach the backend/i);
  });

  it("renders an error panel on a 503 (provider not configured)", async () => {
    mockFetchJson(503, { detail: "a required generation provider is not configured", error_type: "GENERATION_PROVIDER_NOT_CONFIGURED" });
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByRole("textbox", { name: /your question/i }), "query");
    await user.click(screen.getByRole("button", { name: /^ask$/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/not configured/i);
  });

  // 11. Empty input is rejected at UI level.
  it("rejects an empty query without calling the API", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: /^ask$/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/enter a question/i);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  // 12. Unicode English/Hindi/Tamil input renders correctly.
  it.each([
    ["Hindi/Devanagari", "आयुर्वेद औषधि पंजीकरण"],
    ["Tamil", "மருந்து பதிவு விண்ணப்பம்"],
    ["English", "What license do I need?"],
  ])("preserves %s input end-to-end", async (_label, text) => {
    const fixture = makeSafeResponse({ original_query: text, canonical_query: text });
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => fixture });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);

    await user.type(screen.getByRole("textbox", { name: /your question/i }), text);
    await user.click(screen.getByRole("button", { name: /^ask$/i }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [, init] = fetchMock.mock.calls[0];
    expect(JSON.parse(init.body).query).toBe(text);
    expect(await screen.findAllByText(text)).not.toHaveLength(0);
  });

  // 13. Frontend does not fabricate evidence/citations.
  it("shows no evidence identifiers beyond what the backend returned", async () => {
    mockFetchJson(200, makeAbstainResponse());
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByRole("textbox", { name: /your question/i }), "query");
    await user.click(screen.getByRole("button", { name: /^ask$/i }));

    await screen.findByText(/system abstained/i);
    expect(screen.getByText("No evidence is associated with this response.")).toBeInTheDocument();
    expect(screen.getByText("No validated citations are associated with this response.")).toBeInTheDocument();
  });

  // 14. Backend response fields are rendered faithfully.
  it("renders classification and jurisdiction fields exactly as returned", async () => {
    mockFetchJson(200, makeSafeResponse());
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByRole("textbox", { name: /your question/i }), "query");
    await user.click(screen.getByRole("button", { name: /^ask$/i }));

    await screen.findByText("Safe to present");
    expect(screen.getAllByText("KNOWN").length).toBeGreaterThan(0);
    expect(screen.getByText("INDIA")).toBeInTheDocument();
    expect(screen.getByText("GENERAL_INFORMATION_REQUEST")).toBeInTheDocument();
  });

  // 15. Reset/clear behavior works.
  it("clears the form and results on reset", async () => {
    mockFetchJson(200, makeSafeResponse());
    const user = userEvent.setup();
    render(<App />);
    const textbox = screen.getByRole("textbox", { name: /your question/i });
    await user.type(textbox, "query");
    await user.click(screen.getByRole("button", { name: /^ask$/i }));
    await screen.findByText("Safe to present");

    await user.click(screen.getByRole("button", { name: /clear/i }));

    expect(textbox).toHaveValue("");
    expect(screen.queryByText("Safe to present")).not.toBeInTheDocument();
  });
});
