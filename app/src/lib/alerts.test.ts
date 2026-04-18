import { describe, it, expect, beforeEach } from "vitest";
import { diffAndAppend, loadAlerts, markRead, markAllRead } from "./alerts";
import type { AlertEntry } from "./alerts";

beforeEach(() => {
  localStorage.clear();
});

// ── diffAndAppend ─────────────────────────────────────────────────────────────

describe("diffAndAppend", () => {
  it('generates a "new" alert when an MMSI appears for the first time', () => {
    const result = diffAndAppend(
      [],
      [{ mmsi: "123456789", confidence: 0.8, vessel_name: "DARK STAR" }],
    );
    expect(result).toHaveLength(1);
    expect(result[0].kind).toBe("new");
    expect(result[0].mmsi).toBe("123456789");
    expect(result[0].vessel_name).toBe("DARK STAR");
    expect(result[0].delta).toBeNull();
    expect(result[0].read).toBe(false);
  });

  it("carries vessel_name as null when not provided", () => {
    const result = diffAndAppend([], [{ mmsi: "123456789", confidence: 0.8 }]);
    expect(result[0].vessel_name).toBeNull();
  });

  it('generates an "increase" alert when confidence rises by >= 0.05', () => {
    const prev = [{ mmsi: "111111111", confidence: 0.5 }];
    const next = [{ mmsi: "111111111", confidence: 0.6 }];
    const result = diffAndAppend(prev, next);
    expect(result).toHaveLength(1);
    expect(result[0].kind).toBe("increase");
    expect(result[0].delta).toBeCloseTo(0.1, 5);
    expect(result[0].confidence).toBeCloseTo(0.6, 5);
  });

  it("generates an alert at exactly the 0.05 boundary", () => {
    const prev = [{ mmsi: "111111111", confidence: 0.5 }];
    const next = [{ mmsi: "111111111", confidence: 0.55 }];
    const result = diffAndAppend(prev, next);
    expect(result).toHaveLength(1);
    expect(result[0].kind).toBe("increase");
  });

  it("does NOT generate an alert when confidence rises by < 0.05", () => {
    const prev = [{ mmsi: "111111111", confidence: 0.5 }];
    const next = [{ mmsi: "111111111", confidence: 0.549 }];
    const result = diffAndAppend(prev, next);
    expect(result).toHaveLength(0);
  });

  it("does NOT generate an alert when confidence decreases", () => {
    const prev = [{ mmsi: "111111111", confidence: 0.8 }];
    const next = [{ mmsi: "111111111", confidence: 0.6 }];
    const result = diffAndAppend(prev, next);
    expect(result).toHaveLength(0);
  });

  it("does not generate an alert when confidence is unchanged", () => {
    const prev = [{ mmsi: "111111111", confidence: 0.7 }];
    const next = [{ mmsi: "111111111", confidence: 0.7 }];
    const result = diffAndAppend(prev, next);
    expect(result).toHaveLength(0);
  });

  it("generates alerts for multiple new vessels in one call", () => {
    const result = diffAndAppend(
      [],
      [
        { mmsi: "AAA111111", confidence: 0.6 },
        { mmsi: "BBB222222", confidence: 0.7 },
      ],
    );
    expect(result).toHaveLength(2);
    expect(result.map((a) => a.kind).every((k) => k === "new")).toBe(true);
  });

  it("persists new alerts to localStorage", () => {
    diffAndAppend([], [{ mmsi: "999999999", confidence: 0.9 }]);
    const loaded = loadAlerts();
    expect(loaded).toHaveLength(1);
    expect(loaded[0].mmsi).toBe("999999999");
  });

  it("prepends new alerts before existing ones (most-recent first)", () => {
    diffAndAppend([], [{ mmsi: "AAA111111", confidence: 0.6 }]);
    diffAndAppend([], [{ mmsi: "BBB222222", confidence: 0.7 }]);
    const alerts = loadAlerts();
    expect(alerts[0].mmsi).toBe("BBB222222");
    expect(alerts[1].mmsi).toBe("AAA111111");
  });

  it("caps the ring buffer at 50 entries", () => {
    const existing: AlertEntry[] = Array.from({ length: 50 }, (_, i) => ({
      id: `old-${i}`,
      timestamp: new Date().toISOString(),
      mmsi: String(i).padStart(9, "0"),
      vessel_name: null,
      confidence: 0.5,
      delta: null,
      kind: "new" as const,
      read: true,
    }));
    localStorage.setItem("arktrace_alerts", JSON.stringify(existing));

    const result = diffAndAppend([], [{ mmsi: "999999999", confidence: 0.9 }]);
    expect(result).toHaveLength(50);
    expect(result[0].mmsi).toBe("999999999");
  });

  it("returns existing alerts unchanged when no new entries", () => {
    diffAndAppend([], [{ mmsi: "AAA111111", confidence: 0.6 }]);
    // Same vessel, no change — should return current stored list
    const result = diffAndAppend(
      [{ mmsi: "AAA111111", confidence: 0.6 }],
      [{ mmsi: "AAA111111", confidence: 0.6 }],
    );
    expect(result).toHaveLength(1);
    expect(result[0].mmsi).toBe("AAA111111");
  });
});

// ── markRead ──────────────────────────────────────────────────────────────────

describe("markRead", () => {
  it("marks a single alert as read by id", () => {
    diffAndAppend([], [{ mmsi: "123456789", confidence: 0.8 }]);
    const id = loadAlerts()[0].id;
    const updated = markRead(id);
    expect(updated.find((a) => a.id === id)?.read).toBe(true);
  });

  it("does not mark other alerts as read", () => {
    diffAndAppend([], [
      { mmsi: "AAA111111", confidence: 0.6 },
      { mmsi: "BBB222222", confidence: 0.7 },
    ]);
    const alerts = loadAlerts();
    const idToMark = alerts[0].id;
    const updated = markRead(idToMark);
    expect(updated.filter((a) => a.id !== idToMark).every((a) => !a.read)).toBe(true);
  });

  it("persists the read state across loadAlerts calls", () => {
    diffAndAppend([], [{ mmsi: "123456789", confidence: 0.8 }]);
    const id = loadAlerts()[0].id;
    markRead(id);
    expect(loadAlerts().find((a) => a.id === id)?.read).toBe(true);
  });
});

// ── markAllRead ───────────────────────────────────────────────────────────────

describe("markAllRead", () => {
  it("marks all alerts as read", () => {
    diffAndAppend([], [
      { mmsi: "AAA111111", confidence: 0.6 },
      { mmsi: "BBB222222", confidence: 0.7 },
    ]);
    const updated = markAllRead();
    expect(updated.every((a) => a.read)).toBe(true);
  });

  it("persists the all-read state", () => {
    diffAndAppend([], [{ mmsi: "AAA111111", confidence: 0.6 }]);
    markAllRead();
    expect(loadAlerts().every((a) => a.read)).toBe(true);
  });

  it("returns empty array when no alerts exist", () => {
    expect(markAllRead()).toEqual([]);
  });
});

// ── loadAlerts ────────────────────────────────────────────────────────────────

describe("loadAlerts", () => {
  it("returns empty array when localStorage has no key", () => {
    expect(loadAlerts()).toEqual([]);
  });

  it("returns empty array when localStorage value is malformed JSON", () => {
    localStorage.setItem("arktrace_alerts", "{not-valid-json");
    expect(loadAlerts()).toEqual([]);
  });

  it("returns empty array when localStorage value is not an array", () => {
    localStorage.setItem("arktrace_alerts", JSON.stringify({ foo: "bar" }));
    expect(loadAlerts()).toEqual([]);
  });
});
