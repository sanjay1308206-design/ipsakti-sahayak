/**
 * Phase 19 test: the dynamic half of the frontend XSS-rendering proof
 * (Python side already proves, in tests/test_phase_19_redteam.py's
 * P19-06 check, that no component source contains an unsafe raw-HTML
 * sink and that the backend never strips/sanitizes such payloads out of
 * evidence text). This file proves the actual RENDERING behavior: a
 * backend-supplied `answer_text` containing a literal <script> tag or
 * event-handler payload must appear in the DOM only as escaped, inert
 * text - never as a parsed element, and never executed.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { makeSafeResponse } from "./fixtures";

function mockFetchJson(body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => body }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

async function submitQuery() {
  const user = userEvent.setup();
  render(<App />);
  await user.type(screen.getByRole("textbox", { name: /your question/i }), "Tell me about Ministry of Ayush policy in India.");
  await user.click(screen.getByRole("button", { name: /^ask$/i }));
}

describe("Phase 19: backend-sourced text is never rendered as executable markup", () => {
  it("renders a literal <script> tag in answer_text as inert visible text, not a DOM element", async () => {
    const malicious = '<script>window.__xss_fired = true;</script>';
    mockFetchJson(makeSafeResponse({ answer_text: `Some answer text. ${malicious}` }));
    await submitQuery();

    await waitFor(() => expect(document.querySelector(".answer-text")).not.toBeNull());
    const answer = document.querySelector(".answer-text");
    expect(answer?.textContent).toContain(malicious);
    expect(document.querySelectorAll("script").length).toBe(0);
    expect((window as unknown as { __xss_fired?: boolean }).__xss_fired).toBeUndefined();
  });

  it("renders an event-handler-shaped payload in answer_text as inert text, never as an attribute", async () => {
    const malicious = '<img src=x onerror="window.__xss_fired_2 = true">';
    mockFetchJson(makeSafeResponse({ answer_text: `Some answer text. ${malicious}` }));
    await submitQuery();

    await waitFor(() => expect(document.querySelector(".answer-text")).not.toBeNull());
    const answer = document.querySelector(".answer-text");
    expect(answer?.textContent).toContain(malicious);
    expect(document.querySelectorAll("img").length).toBe(0);
    expect((window as unknown as { __xss_fired_2?: boolean }).__xss_fired_2).toBeUndefined();
  });
});
