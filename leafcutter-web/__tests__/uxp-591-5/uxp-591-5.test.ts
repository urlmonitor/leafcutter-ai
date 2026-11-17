/**
 * UXP-591-5 - selecting a flow, drilling into one, or clicking a breadcrumb
 * adds ONE Back entry (native pushState) at that flow's canonical address.
 * (Ticket names a Python test file; vitest only collects *.test.{ts,tsx}.
 * The Playwright spec is deferred.)
 *
 * The view must not use the Next router for these moves: router navigation
 * would re-render the keyed route and remount the view. Tests therefore watch
 * window.history.pushState and the mocked router, and read the entry's view
 * state from history.state["leafcutter:flows-view"].
 */
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, waitFor } from "@testing-library/react";
import { clickNode } from "../helpers/flow-routes";
import {
  DEFAULT,
  addressOf,
  clickCrumb,
  crumbNames,
  drillNode,
  expectNoRouter,
  expectOnScreen,
  h1,
  here,
  labelOf,
  nameOf,
  openSubFlowInDrawer,
  openTab,
  replayRows,
  selectFlow,
  sessionRows,
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

describe("drill, select and breadcrumb each push one entry", () => {
  it("drilling into Build pushes /flows/leafcutter/how-acs-are-built with a two-flow breadcrumb", async () => {
    // covers: UXP-591-5
    // angle: criterion
    await openTab(nav, `/flows/${DEFAULT}`);
    const w = watchNav(nav);
    drillNode(labelOf(DEFAULT, "build"));
    await expectOnScreen({ flow: HOW, crumbs: [DEFAULT, HOW], drawer: null });
    expect(w.push).toHaveBeenCalledTimes(1);
    expect(addressOf(w.push.mock.calls[0][2])).toBe(`/flows/${HOW}`);
    expect(here()).toBe(`/flows/${HOW}`);
    expect(window.history.length).toBe(w.length + 1);
    expectNoRouter(nav);
    // the entry carries the App Router's keys and the view state beside them
    expect((w.push.mock.calls[0][0] as any).__NA).toBe(true);
    expect(storedView()).toEqual({
      crumbs: [DEFAULT, HOW],
      filters: { source: "real", kind: "user", realization: "all" },
    });
  });

  it("'Open sub-flow' in the Build drawer takes the same one-push path, with no ?step=", async () => {
    // covers: UXP-591-5
    // angle: seam
    await openTab(nav, `/flows/${DEFAULT}`);
    clickNode(labelOf(DEFAULT, "build"));
    const w = watchNav(nav);
    openSubFlowInDrawer();
    await expectOnScreen({ flow: HOW, crumbs: [DEFAULT, HOW], drawer: null });
    expect(w.push).toHaveBeenCalledTimes(1);
    expect(addressOf(w.push.mock.calls[0][2])).toBe(`/flows/${HOW}`);
    expect(window.history.length).toBe(w.length + 1);
    expectNoRouter(nav);
  });

  it("picking a flow in the selector pushes its canonical address with a one-flow breadcrumb", async () => {
    // covers: UXP-591-5
    // angle: boundary
    await openTab(nav, `/flows/${DEFAULT}`);
    const w = watchNav(nav);
    selectFlow(nameOf(DEFINE));
    await expectOnScreen({ flow: DEFINE, crumbs: [DEFINE], drawer: null });
    expect(w.push).toHaveBeenCalledTimes(1);
    expect(addressOf(w.push.mock.calls[0][2])).toBe(`/flows/${DEFINE}`);
    expect(window.history.length).toBe(w.length + 1);
    expect(storedView()!.crumbs).toEqual([DEFINE]);
    expectNoRouter(nav);
  });

  it("clicking the first breadcrumb pushes that flow's address with the trail cut after it", async () => {
    // covers: UXP-591-5
    // angle: boundary
    await openTab(nav, `/flows/${DEFAULT}`);
    drillNode(labelOf(DEFAULT, "build"));
    await expectOnScreen({ flow: HOW });
    const w = watchNav(nav);
    clickCrumb(nameOf(DEFAULT));
    await expectOnScreen({ flow: DEFAULT, crumbs: [DEFAULT] });
    expect(w.push).toHaveBeenCalledTimes(1);
    expect(addressOf(w.push.mock.calls[0][2])).toBe(`/flows/${DEFAULT}`);
    expect(window.history.length).toBe(w.length + 1);
    expect(storedView()!.crumbs).toEqual([DEFAULT]);
    expectNoRouter(nav);
  });

  it("an entry pushed after Back discards the Forward entries", async () => {
    // covers: UXP-591-5
    // angle: boundary
    await openTab(nav, `/flows/${DEFAULT}`);
    const start = window.history.length;
    drillNode(labelOf(DEFAULT, "build"));
    await expectOnScreen({ flow: HOW });
    expect(window.history.length).toBe(start + 1);
    await traverse("back");
    await expectOnScreen({ flow: DEFAULT });
    selectFlow(nameOf(DEFINE));
    await expectOnScreen({ flow: DEFINE });
    // the how-acs-are-built entry is gone: one entry after start, not two
    expect(window.history.length).toBe(start + 1);
    await traverse("forward");
    expect(here()).toBe(`/flows/${DEFINE}`);
  });

  it("a pushed address reloaded in place renders the same flow through the catch-all route", async () => {
    // covers: UXP-591-5
    // angle: reachability
    await openTab(nav, `/flows/${DEFAULT}`);
    drillNode(labelOf(DEFAULT, "build"));
    await expectOnScreen({ flow: HOW });
    const pushed = here();
    cleanup();
    await openTab(nav, pushed);
    expect(h1()).toContain(nameOf(HOW));
  });

  it.each([
    ["drill-and-return", [1, 2, 3]],
    ["shared-mock-journey", [1, 2, 3]],
  ])("replays the push rows of the %s session from atlas-flows.mock.json", async (session, seqs) => {
    // covers: UXP-591-5
    // angle: real_artifact
    const rows = sessionRows(session, seqs as number[]);
    expect(rows).toHaveLength(3);
    await replayRows(nav, rows);
  });

  it("control: a drawer open on the entry does not push (it replaces), so drilling is the only push", async () => {
    // covers: UXP-591-5
    // angle: discrimination
    await openTab(nav, `/flows/${DEFAULT}`);
    const w = watchNav(nav);
    clickNode(labelOf(DEFAULT, "plan"));
    expect(w.push).not.toHaveBeenCalled();
    drillNode(labelOf(DEFAULT, "build"));
    await expectOnScreen({ flow: HOW });
    expect(w.push).toHaveBeenCalledTimes(1);
  });
});
