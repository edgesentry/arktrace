import { describe, it, expect } from "vitest";
import {
  validateTransition,
  tierColor,
  handoffLabel,
  TIERS,
  HANDOFF_STATES,
} from "./reviews";
import type { DecisionTier, HandoffState } from "./reviews";

// ── validateTransition ────────────────────────────────────────────────────────

describe("validateTransition", () => {
  it("returns null for a standard in-progress transition", () => {
    expect(
      validateTransition("queued_review", "in_review", null, ""),
    ).toBeNull();
  });

  it("returns null for handoff_recommended with tier + rationale", () => {
    expect(
      validateTransition(
        "in_review",
        "handoff_recommended",
        "Confirmed",
        "Observed STS event at grid 7N",
      ),
    ).toBeNull();
  });

  it("rejects handoff_recommended when rationale is empty", () => {
    const err = validateTransition(
      "in_review",
      "handoff_recommended",
      "Confirmed",
      "",
    );
    expect(err).not.toBeNull();
    expect(err).toMatch(/rationale/i);
  });

  it("rejects handoff_recommended when rationale is only whitespace", () => {
    const err = validateTransition(
      "in_review",
      "handoff_recommended",
      "Confirmed",
      "   ",
    );
    expect(err).not.toBeNull();
    expect(err).toMatch(/rationale/i);
  });

  it("rejects handoff_recommended when tier is null", () => {
    const err = validateTransition(
      "in_review",
      "handoff_recommended",
      null,
      "Valid rationale text",
    );
    expect(err).not.toBeNull();
    expect(err).toMatch(/tier/i);
  });

  it("rejects handoff_recommended when both tier and rationale are missing", () => {
    // tier check happens after rationale check — expect rationale error first
    const err = validateTransition("in_review", "handoff_recommended", null, "");
    expect(err).not.toBeNull();
  });

  it("allows all other transitions without tier or rationale", () => {
    const pairs: [HandoffState | undefined, HandoffState][] = [
      [undefined, "queued_review"],
      ["queued_review", "in_review"],
      ["in_review", "handoff_accepted"],
      ["handoff_accepted", "handoff_completed"],
      ["handoff_completed", "closed"],
    ];
    for (const [from, to] of pairs) {
      expect(validateTransition(from, to, null, "")).toBeNull();
    }
  });

  it("allows handoff_recommended with every valid tier", () => {
    const tiers: DecisionTier[] = [
      "Confirmed",
      "Probable",
      "Suspect",
      "Cleared",
      "Inconclusive",
    ];
    for (const tier of tiers) {
      expect(
        validateTransition("in_review", "handoff_recommended", tier, "Evidence"),
      ).toBeNull();
    }
  });
});

// ── tierColor ─────────────────────────────────────────────────────────────────

describe("tierColor", () => {
  it("returns red (#fc8181) for Confirmed", () => {
    expect(tierColor("Confirmed")).toBe("#fc8181");
  });

  it("returns amber (#f6ad55) for Probable", () => {
    expect(tierColor("Probable")).toBe("#f6ad55");
  });

  it("returns yellow (#fbd38d) for Suspect", () => {
    expect(tierColor("Suspect")).toBe("#fbd38d");
  });

  it("returns green (#68d391) for Cleared", () => {
    expect(tierColor("Cleared")).toBe("#68d391");
  });

  it("returns grey (#718096) for Inconclusive", () => {
    expect(tierColor("Inconclusive")).toBe("#718096");
  });

  it("returns dark grey (#4a5568) for null (unreviewed)", () => {
    expect(tierColor(null)).toBe("#4a5568");
  });
});

// ── handoffLabel ──────────────────────────────────────────────────────────────

describe("handoffLabel", () => {
  it("replaces underscores with spaces", () => {
    expect(handoffLabel("queued_review")).toBe("queued review");
    expect(handoffLabel("in_review")).toBe("in review");
    expect(handoffLabel("handoff_recommended")).toBe("handoff recommended");
    expect(handoffLabel("handoff_accepted")).toBe("handoff accepted");
    expect(handoffLabel("handoff_completed")).toBe("handoff completed");
  });

  it("returns plain string for states without underscores", () => {
    expect(handoffLabel("closed")).toBe("closed");
  });
});

// ── TIERS ─────────────────────────────────────────────────────────────────────

describe("TIERS", () => {
  it("contains exactly five decision tiers", () => {
    expect(TIERS).toHaveLength(5);
  });

  it("includes all expected tier values", () => {
    expect(TIERS).toContain("Confirmed");
    expect(TIERS).toContain("Probable");
    expect(TIERS).toContain("Suspect");
    expect(TIERS).toContain("Cleared");
    expect(TIERS).toContain("Inconclusive");
  });
});

// ── HANDOFF_STATES ────────────────────────────────────────────────────────────

describe("HANDOFF_STATES", () => {
  it("contains exactly six handoff states", () => {
    expect(HANDOFF_STATES).toHaveLength(6);
  });

  it("starts with queued_review and ends with closed", () => {
    expect(HANDOFF_STATES[0]).toBe("queued_review");
    expect(HANDOFF_STATES[HANDOFF_STATES.length - 1]).toBe("closed");
  });

  it("includes all expected state values", () => {
    const expected: HandoffState[] = [
      "queued_review",
      "in_review",
      "handoff_recommended",
      "handoff_accepted",
      "handoff_completed",
      "closed",
    ];
    for (const s of expected) {
      expect(HANDOFF_STATES).toContain(s);
    }
  });
});
