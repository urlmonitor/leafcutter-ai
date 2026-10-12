/**
 * UXP-591-5-i - leaving a flow while its drawer is open keeps that drawer on
 * the entry left behind, so going Back restores it. (Ticket names a Python
 * test file; vitest only collects *.test.{ts,tsx}.)
 *
 * The push must not first rewrite the entry it leaves: that entry keeps the
 * URL last replaced into it (?step=resolve, ?step=code).
 */
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup } from "@testing-library/react";
import {
  addressOf,
  drillNode,
  expectNoRouter,
  expectOnScreen,
  labelOf,
  nameOf,
  openSubFlowInDrawer,
  openTab,
  replayRows,
  selectFlow,
  sessionRows,
  traverse,
  watchNav,
  here,
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

const RENDER = "leafcutter/flow-render-pipeline";
const PYTHON = "leafcutter/python-coder-internal";
const HOW = "leafcutter/how-acs-are-built";

describe("leaving a flow with its drawer open", () => {
  it("picking python-coder-internal with the resolve drawer open pushes its address and Back reopens resolve", async () => {
    // covers: UXP-591-5-i
    // angle: criterion
    await openTab(nav, `/flows/${RENDER}?step=resolve`);
    await expectOnScreen({ flow: RENDER, drawer: "resolve" });
    const w = watchNav(nav);
    selectFlow(nameOf(PYTHON));
    await expectOnScreen({ flow: PYTHON, drawer: null, address: `/flows/${PYTHON}` });
    // one push, and the left entry was not rewritten before it
    expect(w.push).toHaveBeenCalledTimes(1);
    expect(addressOf(w.push.mock.calls[0][2])).toBe(`/flows/${PYTHON}`);
    expect(w.replace).not.toHaveBeenCalled();
    expect(window.history.length).toBe(w.length + 1);
    expectNoRouter(nav);

    await traverse("back");
    await expectOnScreen({ flow: RENDER, drawer: "resolve", address: `/flows/${RENDER}?step=resolve` });
  });

  it("'Open sub-flow' from the code drawer pushes python-coder-internal and Back reopens the code drawer", async () => {
    // covers: UXP-591-5-i
    // angle: seam
    await openTab(nav, `/flows/${HOW}?step=code`);
    await expectOnScreen({ flow: HOW, drawer: "code" });
    const w = watchNav(nav);
    openSubFlowInDrawer();
    await expectOnScreen({ flow: PYTHON, crumbs: [HOW, PYTHON], drawer: null, address: `/flows/${PYTHON}` });
    expect(w.push).toHaveBeenCalledTimes(1);
    expect(w.replace).not.toHaveBeenCalled();
    expect(window.history.length).toBe(w.length + 1);

    await traverse("back");
    await expectOnScreen({ flow: HOW, crumbs: [HOW], drawer: "code", address: `/flows/${HOW}?step=code` });
  });

  it("the drill affordance on the node shares the same push path as 'Open sub-flow'", async () => {
    // covers: UXP-591-5-i
    // angle: discrimination
    await openTab(nav, `/flows/${HOW}?step=code`);
    const w = watchNav(nav);
    drillNode(labelOf(HOW, "code"));
    await expectOnScreen({ flow: PYTHON, drawer: null, address: `/flows/${PYTHON}` });
    expect(w.push).toHaveBeenCalledTimes(1);
    expect(addressOf(w.push.mock.calls[0][2])).toBe(`/flows/${PYTHON}`);
    expect(w.replace).not.toHaveBeenCalled();
    await traverse("back");
    await expectOnScreen({ drawer: "code", address: `/flows/${HOW}?step=code` });
  });

  it("Back does not return the flow with no drawer (the left entry's URL is still the ?step= one)", async () => {
    // covers: UXP-591-5-i
    // angle: failure
    await openTab(nav, `/flows/${RENDER}?step=resolve`);
    selectFlow(nameOf(PYTHON));
    await expectOnScreen({ flow: PYTHON });
    await traverse("back");
    expect(here()).toBe(`/flows/${RENDER}?step=resolve`);
    await expectOnScreen({ drawer: "resolve" });
  });

  it.each([
    ["drawer-in-history", [1, 2, 3]],
    ["select-from-open-drawer", [1, 2, 3]],
  ])("replays the first rows of the %s session from atlas-flows.mock.json", async (session, seqs) => {
    // covers: UXP-591-5-i
    // angle: real_artifact
    const rows = sessionRows(session, seqs as number[]);
    expect(rows).toHaveLength(3);
    await replayRows(nav, rows);
  });
});
