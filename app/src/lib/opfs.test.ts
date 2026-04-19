import { describe, it, expect } from "vitest";
import { isStale } from "./opfs";

const DAY_MS = 86_400_000;
const TTL_MS = 7 * DAY_MS;

describe("isStale", () => {
  it("is stale when size does not match manifest", () => {
    expect(isStale(1000, { downloaded_at: new Date().toISOString() }, 2000, TTL_MS)).toBe(true);
  });

  it("is stale when cached size is null (file absent)", () => {
    expect(isStale(null, null, 1000, TTL_MS)).toBe(true);
  });

  it("is stale when meta is null (no sidecar — safe migration path)", () => {
    expect(isStale(1000, null, 1000, TTL_MS)).toBe(true);
  });

  it("is stale when TTL is exceeded", () => {
    const eightDaysAgo = new Date(Date.now() - 8 * DAY_MS).toISOString();
    expect(isStale(1000, { downloaded_at: eightDaysAgo }, 1000, TTL_MS)).toBe(true);
  });

  it("is not stale when size matches and TTL is within range", () => {
    const threeDaysAgo = new Date(Date.now() - 3 * DAY_MS).toISOString();
    expect(isStale(1000, { downloaded_at: threeDaysAgo }, 1000, TTL_MS)).toBe(false);
  });

  it("is not stale when downloaded_at is now", () => {
    expect(isStale(1000, { downloaded_at: new Date().toISOString() }, 1000, TTL_MS)).toBe(false);
  });

  it("is stale exactly at TTL boundary", () => {
    const exactlyExpired = new Date(Date.now() - TTL_MS - 1).toISOString();
    expect(isStale(1000, { downloaded_at: exactlyExpired }, 1000, TTL_MS)).toBe(true);
  });
});
