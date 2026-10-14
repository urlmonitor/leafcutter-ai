/**
 * UXP-591-5-v (amended 2026-10-14, owner-confirmed) - a filter change while
 * 'Flow not found' shows keeps the notice and the address, draws nothing, and
 * only re-lists the selector. (Ticket names a Python test file; vitest only
 * collects *.test.{ts,tsx}.)
 *
 * Replaces the PR #1176 tests that cleared the notice and re-picked a flow.
 * The not-found state is the Flows view rendered by the route's not-found
 * boundary; the entry state written by the replace must win over that
 * boundary's server-rendered defaults (Real, User, All) whenever the entry is
 * shown again.
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
  flowNotFoundNoticeShown,
  groupButtonsText,
  h1,
  here,
  nameOf,
  openNotFoundTab,
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

/** Nothing is drawn: no graph, no heading naming a flow, no breadcrumb, no drawer. */
function expectNothingDrawn() {
  expect(document.querySelector(".react-flow__node")).toBeNull();
  expect(crumbNames()).toEqual([]);
  expect(drawerIds()).toEqual([]);
  expect(h1()).not.toContain(nameOf(ARCH));
  expect(h1()).not.toContain(nameOf(CHECKOUT));
}

describe("a filter change from the 'Flow not found' state", () => {
  it("Kind Architecture keeps the notice, the address and one entry, and the selector lists only product-truth-architecture", async () => {
    // covers: UXP-591-5-v
    // angle: criterion
    await openNotFoundTab(nav, UNKNOWN);
    expect(flowNotFoundNoticeShown()).toBe(true);
    expect(activeOf("Kind")).toBe("User");
    const w = watchNav(nav);
    setFilter("Kind", "Architecture");

    await waitFor(() => expect(activeOf("Kind")).toBe("Architecture"));
    await waitFor(() => expect(groupButtonsText("Flow")).toEqual([nameOf(ARCH)]));
    // a filter change never picks or swaps a flow
    expect(flowNotFoundNoticeShown()).toBe(true);
    expect(document.body.textContent).toContain("No flow has the id 'leafcutter/flow-render-pipline'");
    expectNothingDrawn();
    // the unknown ?step=resolve stays; the entry is rewritten in place
    expect(here()).toBe(UNKNOWN);
    expect(w.replace).toHaveBeenCalledTimes(1);
    expect(addressOf(w.replace.mock.calls[0][2])).toBe(UNKNOWN);
    expect(w.push).not.toHaveBeenCalled();
    expect(window.history.length).toBe(w.length);
    expectNoRouter(nav);
    expect(storedView()?.filters).toEqual({ source: "real", kind: "architecture", realization: "all" });
  });

  it("Source Mock re-lists the selector the same way and still draws nothing", async () => {
    // covers: UXP-591-5-v
    // angle: boundary
    await openNotFoundTab(nav, UNKNOWN);
    const w = watchNav(nav);
    setFilter("Source", "Mock");

    await waitFor(() => expect(activeOf("Source")).toBe("Mock"));
    await waitFor(() => expect(groupButtonsText("Flow")[0]).toContain(nameOf(CHECKOUT)));
    expect(flowNotFoundNoticeShown()).toBe(true);
    expectNothingDrawn();
    expect(here()).toBe(UNKNOWN);
    expect(w.push).not.toHaveBeenCalled();
    expect(window.history.length).toBe(w.length);
  });

  it("picking Product-truth in the leafcutter architecture pushes its canonical address with a one-flow breadcrumb", async () => {
    // covers: UXP-591-5-v
    // angle: criterion
    await openNotFoundTab(nav, UNKNOWN);
    setFilter("Kind", "Architecture");
    await waitFor(() => expect(groupButtonsText("Flow")).toEqual([nameOf(ARCH)]));
    const start = window.history.length;

    selectFlow(nameOf(ARCH));

    await expectOnScreen({ flow: ARCH, crumbs: [ARCH], drawer: null, address: `/flows/${ARCH}` });
    expect(window.history.length).toBe(start + 1); // the ordinary select push
    expect(flowNotFoundNoticeShown()).toBe(false);
  });

  it("Back from there returns the 'Flow not found' entry with the Kind filter at Architecture", async () => {
    // covers: UXP-591-5-v
    // angle: seam
    await openNotFoundTab(nav, UNKNOWN);
    setFilter("Kind", "Architecture");
    await waitFor(() => expect(groupButtonsText("Flow")).toEqual([nameOf(ARCH)]));
    selectFlow(nameOf(ARCH));
    await expectOnScreen({ flow: ARCH, address: `/flows/${ARCH}` });

    await traverse("back");

    await waitFor(() => expect(here()).toBe(UNKNOWN));
    await waitFor(() => expect(flowNotFoundNoticeShown()).toBe(true));
    // the stored filters win over the boundary's server-rendered Real, User, All
    await waitFor(() => expect(activeOf("Kind")).toBe("Architecture"));
    expect(groupButtonsText("Flow")).toEqual([nameOf(ARCH)]);
    expectNothingDrawn();
  });

  it("control: before any filter change the notice shows with an empty breadcrumb and the default filters", async () => {
    // covers: UXP-591-5-v
    // angle: discrimination
    await openNotFoundTab(nav, UNKNOWN);
    expect(document.body.textContent).toContain("No flow has the id 'leafcutter/flow-render-pipline'");
    expect(activeOf("Source")).toBe("Real");
    expect(activeOf("Kind")).toBe("User");
    expect(activeOf("Realization")).toBe("All");
    expectNothingDrawn();
    expect(groupButtonsText("Flow").join(" | ")).not.toContain(nameOf(ARCH));
  });
});
