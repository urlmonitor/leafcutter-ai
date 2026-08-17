/**
 * Black-box component tests for the mock/live badge in the Atlas sidebar
 * (leafcutter-web/components/shell/sidebar.tsx), derived exclusively from the
 * acceptance criteria — NOT from reading the implementation.
 *
 * ACs covered: UXP-607.
 *
 * Wiring notes (resolved from the CONSUMER only, per the black-box mandate):
 * - app/layout.tsx imports `{ Sidebar, MobileNav }` from
 *   "@/components/shell/sidebar" and renders `<Sidebar />` with no props, so
 *   Sidebar must derive its own badge state server-side (from the resolved
 *   mock decision), not from a prop passed by the caller.
 * - Badge copy is pinned by the reviewed product-truth mockup
 *   (fixtures/docs/product-truth/mockups/leafcutter/mock-mode-badge.mockup.json):
 *   an amber badge reading "Mock mode" (uppercase tracking) appears when
 *   active; the footer status line switches between
 *   "Live · reads the repo on each request" (live) and
 *   "Fixtures · bundled mock data" (mock). We assert on the stable, casing-
 *   insensitive "mock mode" substring so CSS text-transform doesn't matter.
 * - Sidebar is invoked as a plain function call (not JSX) so the test works
 *   whether it is a sync or an async Server Component:
 *   `await (Sidebar as any)()`. `next/navigation` hooks are stubbed
 *   defensively in case a child client island (e.g. active-link highlighting)
 *   needs an app-router context that jsdom does not provide — a harness
 *   accommodation, not a behavioral assertion (mirrors the ResizeObserver
 *   stub convention used in flow-nodes.decisions.test.tsx).
 */
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type React from "react";

afterEach(() => {
  vi.resetModules();
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
});

async function renderSidebar(mockActive: boolean, nextPublicMockOverride?: string) {
  vi.resetModules();

  vi.doMock("@/lib/data/mock", () => ({
    isMockActive: () => mockActive,
    FIXTURE_ROOT: "/fake/fixture-root",
  }));

  // Harness accommodation: stub next/navigation in case a child client
  // island needs app-router context jsdom does not provide.
  vi.doMock("next/navigation", () => ({
    usePathname: () => "/",
    useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
    useSearchParams: () => new URLSearchParams(),
  }));

  if (nextPublicMockOverride !== undefined) {
    vi.stubEnv("NEXT_PUBLIC_LEAFCUTTER_MOCK", nextPublicMockOverride);
  }

  const { Sidebar } = await import("@/components/shell/sidebar");
  const ui = await (Sidebar as unknown as () => Promise<React.ReactElement> | React.ReactElement)();
  return render(ui as React.ReactElement);
}

describe("UXP-607 — the badge always tells the truth about the resolved decision", () => {
  it("badge_reflects_resolved_mock_decision", async () => {
    // covers: UXP-607
    // "When the resolved decision is 'mock' the badge reads 'mock'."
    await renderSidebar(true);
    expect(screen.getByText(/mock mode/i)).toBeInTheDocument();
  });

  it("badge_reflects_resolved_live_decision", async () => {
    // covers: UXP-607
    // "When the resolved decision is 'live' the badge reads 'live'/real."
    await renderSidebar(false);
    expect(screen.queryByText(/mock mode/i)).not.toBeInTheDocument();
  });

  it("badge_ignores_build_time_next_public_flag", async () => {
    // covers: UXP-607
    // "The badge is derived from that resolved runtime decision … not from
    // the build-time NEXT_PUBLIC_ mock flag." Resolved decision (mocked) is
    // TRUE (mock), while the build-time flag is set to "0" (live) — the
    // badge must follow the resolved decision, not the stale build flag.
    await renderSidebar(true, "0");
    expect(screen.getByText(/mock mode/i)).toBeInTheDocument();
  });
});
