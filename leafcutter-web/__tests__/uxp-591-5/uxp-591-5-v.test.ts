/**
 * UXP-591-5-v - a filter change while 'Flow not found' shows clears the
 * notice, re-picks a flow, and replaces the address in place. (Ticket names a
 * Python test file; vitest only collects *.test.{ts,tsx}.)
 *
 * The not-found state is the Flows view rendered by the route's not-found
 * boundary; the entry state written by the replace must win over that
 * boundary's server-rendered props whenever the entry is shown again.
 */
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, waitFor } from "@testing-library/react";
import { activeOf } from "../helpers/flow-routes";
import {
  addressOf,
  crumbNames,
  drawerIds,
  expectNoRouter,
  expectOnScreen,
  groupButtonsText,
  h1,
  here,
  nameOf,
  openNotFoundTab,
  openTab,
  selectFlow,
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

const UNKNOWN = "/flows/leafcutter/flow-render-pipline?step=resolve";
const ARCH = "leafcutter/product-truth-architecture";
const CHECKOUT = "fern-and-fig/checkout-and-pay";
const BUYS = "fern-and-fig/customer-buys-a-plant";

describe("a filter change from the 'Flow not found' state", () => {
  it("Kind Architecture clears the notice, draws product-truth-architecture alone and replaces the address at one entry", async () => {
    // covers: UXP-591-5-v
    // angle: criterion
    await openNotFoundTab(nav, UNKNOWN);
    expect(document.body.textContent).toContain("Flow not found");
    const w = watchNav(nav);
    setFilter("Kind", "Architecture");
    await expectOnScreen({ flow: ARCH, crumbs: [ARCH], drawer: null, address: `/flows/${ARCH}` });
    expect(document.body.textContent).not.toContain("Flow not found");
    expect(document.body.textContent).not.toContain("Step not found");
    expect(w.replace).toHaveBeenCalledTimes(1);
    // the unknown flow's ?step=resolve is not carried over
    expect(addressOf(w.replace.mock.calls[0][2])).toBe(`/flows/${ARCH}`);
    expect(w.push).not.toHaveBeenCalled();
    expect(window.history.length).toBe(w.length);
    expectNoRouter(nav);
    expect(storedView()).toEqual({
      crumbs: [ARCH],
      filters: { source: "real", kind: "architecture", realization: "all" },
    });
  });

  it("Source Mock picks the first flow the selector lists: fern-and-fig/checkout-and-pay", async () => {
    // covers: UXP-591-5-v
    // angle: boundary
    await openNotFoundTab(nav, UNKNOWN);
    const w = watchNav(nav);
    setFilter("Source", "Mock");
    await expectOnScreen({ flow: CHECKOUT, crumbs: [CHECKOUT], drawer: null, address: `/flows/${CHECKOUT}` });
    expect(groupButtonsText("Flow")[0]).toContain(nameOf(CHECKOUT));
    expect(w.replace).toHaveBeenCalledTimes(1);
    expect(w.push).not.toHaveBeenCalled();
    expect(window.history.length).toBe(w.length);
    expect(document.body.textContent).not.toContain("Flow not found");
  });

  it("after picking Customer buys a plant and pressing Back the entry shows checkout-and-pay, never the notice", async () => {
    // covers: UXP-591-5-v
    // angle: seam
    await openNotFoundTab(nav, UNKNOWN);
    setFilter("Source", "Mock");
    await expectOnScreen({ flow: CHECKOUT });
    const start = window.history.length;
    selectFlow(nameOf(BUYS));
    await expectOnScreen({ flow: BUYS, crumbs: [BUYS], address: `/flows/${BUYS}` });
    expect(window.history.length).toBe(start + 1);

    await traverse("back");
    await expectOnScreen({ flow: CHECKOUT, crumbs: [CHECKOUT], drawer: null, address: `/flows/${CHECKOUT}` });
    expect(document.body.textContent).not.toContain("Flow not found");
    expect(here()).not.toContain("flow-render-pipline");
    await waitFor(() => expect(activeOf("Source")).toBe("Mock"));
  });

  it("a reload of the replaced entry renders the re-picked flow through the catch-all route", async () => {
    // covers: UXP-591-5-v
    // angle: reachability
    await openNotFoundTab(nav, UNKNOWN);
    setFilter("Kind", "Architecture");
    await expectOnScreen({ flow: ARCH, address: `/flows/${ARCH}` });
    const replaced = here();
    cleanup();
    await openTab(nav, replaced);
    expect(h1()).toContain(nameOf(ARCH));
    expect(drawerIds()).toEqual([]);
    expect(crumbNames()).toEqual([]);
  });

  it("control: before any filter change the notice shows with an empty breadcrumb and no flow drawn", async () => {
    // covers: UXP-591-5-v
    // angle: discrimination
    await openNotFoundTab(nav, UNKNOWN);
    expect(document.body.textContent).toContain("No flow has the id 'leafcutter/flow-render-pipline'");
    expect(crumbNames()).toEqual([]);
    expect(drawerIds()).toEqual([]);
    const w = watchNav(nav);
    setFilter("Kind", "Architecture");
    await waitFor(() => expect(document.body.textContent).not.toContain("Flow not found"));
    expect(w.replace).toHaveBeenCalledTimes(1);
  });
});
