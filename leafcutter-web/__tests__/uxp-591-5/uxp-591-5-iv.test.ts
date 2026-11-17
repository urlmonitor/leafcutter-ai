/**
 * UXP-591-5-iv - a filter change that keeps the entry flow leaves the screen
 * and the address unchanged. (Ticket names a Python test file; vitest only
 * collects *.test.{ts,tsx}.)
 *
 * The entry flow (crumbs[0]) is checked against the new filters, not the drawn
 * sub-flow. The only history write allowed is the replace of the entry's
 * stored filters, to the same URL.
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
  here,
  labelOf,
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

async function drilledWithDrawer() {
  await openTab(nav, `/flows/${DEFAULT}`);
  drillNode(labelOf(DEFAULT, "build"));
  await expectOnScreen({ flow: HOW });
  clickNode(labelOf(HOW, "code"));
  await expectOnScreen({ drawer: "code", address: `/flows/${HOW}?step=code` });
}

describe("a filter change that keeps the entry flow", () => {
  it("Realization Built keeps how-acs-are-built drawn with its drawer, breadcrumb and address, at unchanged history length", async () => {
    // covers: UXP-591-5-iv
    // angle: criterion
    await drilledWithDrawer();
    const w = watchNav(nav);
    setFilter("Realization", "Built");
    await waitFor(() => expect(activeOf("Realization")).toBe("Built"));
    await expectOnScreen({
      flow: HOW,
      crumbs: [DEFAULT, HOW],
      drawer: "code",
      address: `/flows/${HOW}?step=code`,
    });
    expect(w.push).not.toHaveBeenCalled();
    expect(window.history.length).toBe(w.length);
    expectNoRouter(nav);
    // the only write allowed is the stored-state update, to the same URL
    expect(w.replace).toHaveBeenCalledTimes(1);
    for (const call of w.replace.mock.calls) {
      expect(addressOf(call[2])).toBe(`/flows/${HOW}?step=code`);
    }
    expect(storedView()?.filters.realization).toBe("built");
  });

  it("the entry's stored filters read Realization Built after the change, with its crumbs intact", async () => {
    // covers: UXP-591-5-iv
    // angle: seam
    await drilledWithDrawer();
    setFilter("Realization", "Built");
    await waitFor(() =>
      expect(storedView()).toEqual({
        crumbs: [DEFAULT, HOW],
        filters: { source: "real", kind: "user", realization: "built" },
      }),
    );
  });

  it("Back then Forward restores the entry with Built and its drawer", async () => {
    // covers: UXP-591-5-iv
    // angle: seam
    await drilledWithDrawer();
    setFilter("Realization", "Built");
    await waitFor(() => expect(storedView()?.filters.realization).toBe("built"));
    await traverse("back");
    await expectOnScreen({ flow: DEFAULT, address: `/flows/${DEFAULT}` });
    await traverse("forward");
    await expectOnScreen({ flow: HOW, crumbs: [DEFAULT, HOW], drawer: "code", address: `/flows/${HOW}?step=code` });
    await waitFor(() => expect(activeOf("Realization")).toBe("Built"));
    expect(here()).toBe(`/flows/${HOW}?step=code`);
  });

  it("replays nav-filter-replace-1 to -4 from atlas-flows.mock.json", async () => {
    // covers: UXP-591-5-iv
    // angle: real_artifact
    const rows = sessionRows("filter-replace", [1, 2, 3, 4]);
    expect(rows).toHaveLength(4);
    await replayRows(nav, rows);
  });
});
