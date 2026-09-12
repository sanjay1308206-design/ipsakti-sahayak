import { describe, expect, it } from "vitest";
import { classifyOutcome } from "./outcome";
import { makeAbstainResponse, makeEscalateResponse, makeSafeResponse } from "../test/fixtures";

describe("classifyOutcome", () => {
  it("classifies a DELIVERED + SAFE_TO_PRESENT response as SUCCESS", () => {
    expect(classifyOutcome(makeSafeResponse())).toBe("SUCCESS");
  });

  it("classifies an ABSTAIN response as ABSTAINED", () => {
    expect(classifyOutcome(makeAbstainResponse())).toBe("ABSTAINED");
  });

  it("classifies an ESCALATE response as ESCALATED regardless of delivery_status", () => {
    expect(classifyOutcome(makeEscalateResponse())).toBe("ESCALATED");
  });

  it("never classifies a non-DELIVERED response as SUCCESS even with SAFE_TO_PRESENT missing", () => {
    const response = makeSafeResponse({ delivery_status: "TRANSLATION_FAILED", safety_status: "SAFE_TO_PRESENT" });
    expect(classifyOutcome(response)).toBe("ABSTAINED");
  });

  it("treats a null safety_status as not SUCCESS", () => {
    const response = makeSafeResponse({ safety_status: null });
    expect(classifyOutcome(response)).toBe("ABSTAINED");
  });
});
