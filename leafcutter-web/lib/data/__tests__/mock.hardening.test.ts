/**
 * Black-box tests for the mock-mode hardening resolution order on the
 * data-layer seam (leafcutter-web/lib/data/mock.ts), derived exclusively from
 * the acceptance criteria — NOT from reading the implementation.
 *
 * ACs covered: UXP-607-1, UXP-607-2, UXP-608-2.
 *
 * Pinned public contract (given by the dispatching ticket, not the source):
 *   - isMockActive(): boolean  — exported from lib/data/mock.ts.
 *   - Runtime override travels as request header `x-mock-active` ("1"=mock,
 *     "0"=live), set by middleware.ts from the ?mock query param / sticky
 *     "mock" cookie.
 *   - Env inputs: LEAFCUTTER_MOCK=1 (env default=mock),
 *     LEAFCUTTER_MOCK_LOCK=real (production lock, highest precedence).
 *   - NEW: LEAFCUTTER_MOCK_ALLOW_OVERRIDE=1 (explicit production opt-in to
 *     runtime overrides).
 *   - Production detection: process.env.NODE_ENV === "production".
 *   - Resolution order: LOCK > production-default-deny > runtime override >
 *     env default.
 *
 * Harness: next/headers is request-scoped in the real app; here it is mocked
 * so isMockActive() can read a simulated forwarded x-mock-active header. We
 * do not know whether isMockActive() reads env / the header at call time or
 * caches at import time, so every scenario does vi.resetModules() + a fresh
 * dynamic import (a legitimate harness technique, not implementation-peeking
 * — see the test-writer mandate for exactly this ambiguity).
 */
import { describe, it, expect, afterEach, vi } from "vitest";

const ENV_KEYS = [
  "NODE_ENV",
  "LEAFCUTTER_MOCK",
  "LEAFCUTTER_MOCK_LOCK",
  "LEAFCUTTER_MOCK_ALLOW_OVERRIDE",
] as const;
type EnvKey = (typeof ENV_KEYS)[number];

let savedEnv: Partial<Record<EnvKey, string | undefined>> = {};

afterEach(() => {
  for (const k of ENV_KEYS) {
    if (savedEnv[k] === undefined) delete process.env[k];
    else process.env[k] = savedEnv[k];
  }
  vi.resetModules();
  vi.restoreAllMocks();
});

/**
 * Loads a fresh copy of lib/data/mock.ts with the given env applied and the
 * given simulated x-mock-active request header (or null for "no override
 * forwarded"). Returns the resolved isMockActive() value from that fresh
 * module instance.
 */
async function resolveMockActive(
  env: Partial<Record<EnvKey, string>>,
  forwardedHeader: string | null
): Promise<boolean> {
  savedEnv = {};
  for (const k of ENV_KEYS) {
    savedEnv[k] = process.env[k];
    if (env[k] !== undefined) process.env[k] = env[k];
    else delete process.env[k];
  }

  vi.resetModules();
  vi.doMock("next/headers", () => ({
    headers: () => ({
      get: (name: string) => (name === "x-mock-active" ? forwardedHeader : null),
    }),
  }));

  const mod = await import("@/lib/data/mock");
  return mod.isMockActive();
}

describe("UXP-607-1 — mock-default deployment, override back to live", () => {
  it("mock_default_override_to_live_shows_live_badge", async () => {
    // covers: UXP-607-1
    // Given LEAFCUTTER_MOCK defaults to mock, When a request carries a
    // runtime override to live (x-mock-active: 0, i.e. ?mock=0), Then the
    // seam isMockActive() — the single source the badge and views both
    // read — resolves to false (live), not the mock default.
    const resolved = await resolveMockActive(
      { NODE_ENV: "development", LEAFCUTTER_MOCK: "1" },
      "0"
    );
    expect(resolved).toBe(false);
  });
});

describe("UXP-607-2 — unlocked live-default deployment, override to mock", () => {
  it("live_default_override_to_mock_shows_mock_badge", async () => {
    // covers: UXP-607-2
    // Given an UNLOCKED deployment defaulting to live (LEAFCUTTER_MOCK unset),
    // When a request carries a runtime override to mock (x-mock-active: 1,
    // i.e. ?mock=1), Then isMockActive() resolves to true (mock/fixtures) —
    // the badge must never lag the override in either direction.
    const resolved = await resolveMockActive({ NODE_ENV: "development" }, "1");
    expect(resolved).toBe(true);
  });
});

describe("UXP-608-2 — the production lock beats an explicit opt-in and the override", () => {
  it("production_lock_beats_opt_in_and_override", async () => {
    // covers: UXP-608-2
    // Given production, LEAFCUTTER_MOCK_LOCK=real, AND the explicit override
    // opt-in ALSO set, When ?mock=1 arrives, Then the lock wins: resolves to
    // false (live) — the override is ignored despite the opt-in.
    // Resolution order under test: lock > opt-in-allow > runtime override > env default.
    const resolved = await resolveMockActive(
      {
        NODE_ENV: "production",
        LEAFCUTTER_MOCK_LOCK: "real",
        LEAFCUTTER_MOCK_ALLOW_OVERRIDE: "1",
      },
      "1"
    );
    expect(resolved).toBe(false);
  });
});
