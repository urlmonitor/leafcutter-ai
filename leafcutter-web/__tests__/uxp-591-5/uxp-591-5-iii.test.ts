/**
 * UXP-591-5-iii - a filter change that excludes the entry flow re-picks the
 * flow and replaces the address in place, with no Back entry. (Ticket names a
 * Python test file; vitest only collects *.test.{ts,tsx}.)
 *
 * Whether the flow is kept is decided against the entry flow (crumbs[0]), not
 * the drawn sub-flow. The re-pick is the first flow the selector lists under
 * the new filters.
 */
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, waitFor } from "@testing-library/react";
import { activeOf, clickNode } from "../helpers/flow-routes";
import {
  DEFAULT,
  addressOf,
  drillNode,
  expectNoRouter,
  expectOnScreen,
  groupButtonsText,
  h1,
  labelOf,
  nameOf,
  openTab,
  replayRows,
  sessionRows,
  setFilter,
  storedView,
  traverse,
  watchNav,
  type NavState,
} from "../helpers/flow-history-nav";

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

vi.setConfig({ testTimeout: 180000 });

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

const HOW = "leafcutter/how-acs-are-built";
const DEFINE = "leafcutter/define-a-feature";

/** deliver-a-feature -> drill into how-acs-are-built -> code drawer open (two entries). */
async function drilledWithDrawer() {
  await openTab(nav, `/flows/${DEFAULT}`);
  drillNode(labelOf(DEFAULT, "build"));
  await expectOnScreen({ flow: HOW });
  clickNode(labelOf(HOW, "code"));
  await expectOnScreen({ drawer: "code", address: `/flows/${HOW}?step=code` });
}

describe("a filter change that excludes the entry flow", () => {
  it("Realization Spec draws define-a-feature alone and replaces the entry at two history entries", async () => {
    // covers: UXP-591-5-iii
    // angle: criterion
    await drilledWithDrawer();
    const w = watchNav(nav);
    setFilter("Realization", "Spec");
    await expectOnScreen({ flow: DEFINE, crumbs: [DEFINE], drawer: null, address: `/flows/${DEFINE}` });
    expect(w.replace).toHaveBeenCalledTimes(1);
    expect(addressOf(w.replace.mock.calls[0][2])).toBe(`/flows/${DEFINE}`); // no ?step=code
    expect(w.push).not.toHaveBeenCalled();
    expect(window.history.length).toBe(w.length);
    expectNoRouter(nav);
    expect(storedView()).toEqual({
      crumbs: [DEFINE],
      filters: { source: "real", kind: "user", realization: "spec" },
    });
  });

  it("Back then Forward after the re-pick returns deliver-a-feature, then define-a-feature at Spec", async () => {
    // covers: UXP-591-5-iii
    // angle: seam
    await drilledWithDrawer();
    setFilter("Realization", "Spec");
    await expectOnScreen({ flow: DEFINE });
    await traverse("back");
    await expectOnScreen({ flow: DEFAULT, address: `/flows/${DEFAULT}` });
    await waitFor(() => expect(activeOf("Realization")).toBe("All"));
    await traverse("forward");
    await expectOnScreen({ flow: DEFINE, crumbs: [DEFINE], drawer: null, address: `/flows/${DEFINE}` });
    await waitFor(() => expect(activeOf("Realization")).toMatch(/spec/i));
  });

  it("replays nav-filter-replace-1 to -3 and -5 to -7 from atlas-flows.mock.json", async () => {
    // covers: UXP-591-5-iii
    // angle: real_artifact
    const rows = sessionRows("filter-replace", [1, 2, 3, 5, 6, 7]);
    expect(rows).toHaveLength(6);
    await replayRows(nav, rows);
  });

  it("the re-picked flow is the first one the selector lists under the new Source filter", async () => {
    // covers: UXP-591-5-iii
    // angle: boundary
    await openTab(nav, `/flows/${DEFAULT}`);
    const w = watchNav(nav);
    setFilter("Source", "Mock");
    let first = "";
    await waitFor(() => {
      first = groupButtonsText("Flow")[0];
      expect(first).toBeTruthy();
      expect(first).not.toContain(nameOf(DEFAULT));
    });
    await waitFor(() => expect(first).toContain(h1()));
    expect(w.push).not.toHaveBeenCalled();
    expect(w.replace).toHaveBeenCalledTimes(1);
    expect(addressOf(w.replace.mock.calls[0][2])).toMatch(/^\/flows\/fern-and-fig\/[a-z0-9-]+$/);
    expect(window.history.length).toBe(w.length);
  });

  it("the replaced entry carries no ?step= even though the left drawer had one", async () => {
    // covers: UXP-591-5-iii
    // angle: failure
    await drilledWithDrawer();
    const w = watchNav(nav);
    setFilter("Realization", "Spec");
    await expectOnScreen({ flow: DEFINE });
    expect(w.replace).toHaveBeenCalledTimes(1);
    for (const call of w.replace.mock.calls) expect(String(call[2])).not.toContain("step=");
  });
});
