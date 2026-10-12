/**
 * UXP-591-4-ii - closing the drawer returns the address to the flow's
 * canonical address without adding a Back entry. (Ticket names a Python test
 * file; vitest only collects *.test.{ts,tsx}. Drill-then-Back belongs to
 * UXP-591-5 and is not tested here.)
 */
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup } from "@testing-library/react";
import { clickNode, closeWithCanvas, closeWithX, drawers, expectDrawers } from "./helpers/flow-routes";
import { expectReplaced, openAt, watchHistory, type NavState } from "./helpers/drawer-nav";

const nav = vi.hoisted(() => ({
  headers: new Headers(),
  routerPush: vi.fn(),
  routerReplace: vi.fn(),
})) as NavState;

vi.mock("server-only", () => ({}));
vi.mock("next/headers", () => ({ headers: () => nav.headers }));
vi.mock("next/navigation", () => ({
  notFound: vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
  redirect: vi.fn(),
  useRouter: () => ({ push: nav.routerPush, replace: nav.routerReplace }),
  usePathname: () => "/flows",
  useSearchParams: () => new URLSearchParams(),
}));

vi.setConfig({ testTimeout: 60000 });

beforeAll(() => {
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
});
beforeEach(() => {
  nav.headers = new Headers();
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const DEFAULT = "leafcutter/deliver-a-feature";

describe("closing the drawer", () => {
  it.each([
    ["the X button", closeWithX],
    ["a click on the canvas beside it", closeWithCanvas],
  ])("%s returns the address to the canonical one with no query, one replace, no new entry", async (_n, close) => {
    // covers: UXP-591-4-ii
    // angle: criterion
    await openAt(nav, `/flows/${DEFAULT}?step=build`);
    expect(drawers().map((d) => d.id)).toEqual(["build"]);
    const w = watchHistory(nav);
    close();
    await expectDrawers([]);
    expectReplaced(nav, w, `/flows/${DEFAULT}`);
    expect(window.location.search).toBe("");
  });

  it("a drawer opened and closed on the bare /flows ends at the default flow's canonical address, never /flows", async () => {
    // covers: UXP-591-4-ii
    // angle: boundary
    await openAt(nav, "/flows");
    const w = watchHistory(nav);
    clickNode("Plan");
    closeWithX();
    await expectDrawers([]);
    expectReplaced(nav, w, `/flows/${DEFAULT}`, 2);
    for (const call of w.replace.mock.calls) {
      expect(String(call[2])).not.toMatch(/^\/flows\/?(\?|$)/);
    }
  });

  it("stores the entry's view state with the drawer closed, beside the App Router's keys", async () => {
    // covers: UXP-591-4-ii
    // angle: seam
    await openAt(nav, `/flows/${DEFAULT}?step=build`);
    const w = watchHistory(nav);
    closeWithX();
    await expectDrawers([]);
    expect(w.replace).toHaveBeenCalledTimes(1);
    const state = window.history.state as Record<string, any>;
    expect(state.__NA).toBe(true);
    expect(state.__PRIVATE_NEXTJS_INTERNALS_TREE).toEqual(["", {}]);
    const viewState = Object.values(state).find(
      (v) => v && typeof v === "object" && !Array.isArray(v) && "crumbs" in v,
    ) as { crumbs: string[] } | undefined;
    expect(viewState).toBeTruthy();
    expect(viewState!.crumbs).toEqual([DEFAULT]);
    expect(JSON.stringify(state)).not.toContain("build");
  });
});
