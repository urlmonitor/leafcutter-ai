/**
 * UXP-591-5-ii - Back and Forward return each flow entry as it was left: flow,
 * crumbs, filters and drawer. (Ticket names a Python test file; vitest only
 * collects *.test.{ts,tsx}. The no-reload Playwright spec is deferred.)
 *
 * One popstate listener restores the view: the entry's URL is the authority
 * for the flow and the drawer (?step=), history.state["leafcutter:flows-view"]
 * for crumbs and filters. A pop writes no history.
 */
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, waitFor } from "@testing-library/react";
import { activeOf, clickNode } from "../helpers/flow-routes";
import {
  DEFAULT,
  crumbNames,
  drillNode,
  expectOnScreen,
  groupButtonsText,
  h1,
  here,
  labelOf,
  nameOf,
  openNotFoundTab,
  openTab,
  replayRows,
  selectFlow,
  sessionRows,
  setFilter,
  storedView,
  traverse,
  watchNav,
  type NavState,
} from "../helpers/flow-history-nav";
import { getFlows } from "@/lib/data/flows";

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
const PYTHON = "leafcutter/python-coder-internal";
const otherBuiltUserFlow = getFlows().find(
  (f) => f.source === "real" && f.kind === "user" && f.realization === "built" && f.id !== DEFAULT,
)!;

describe("Back and Forward restore each entry", () => {
  it("Back twice and Forward once after two drills shows how-acs-are-built, the default flow at /flows, then how-acs-are-built again", async () => {
    // covers: UXP-591-5-ii
    // angle: criterion
    await openTab(nav, "/flows");
    drillNode(labelOf(DEFAULT, "build"));
    await expectOnScreen({ flow: HOW });
    drillNode(labelOf(HOW, "code"));
    await expectOnScreen({ flow: PYTHON, crumbs: [DEFAULT, HOW, PYTHON], address: `/flows/${PYTHON}` });

    await traverse("back");
    await expectOnScreen({ flow: HOW, crumbs: [DEFAULT, HOW], address: `/flows/${HOW}` });
    await traverse("back");
    await expectOnScreen({ flow: DEFAULT, crumbs: [DEFAULT], address: "/flows" });
    await traverse("forward");
    await expectOnScreen({ flow: HOW, crumbs: [DEFAULT, HOW], address: `/flows/${HOW}` });
  });

  it("a pop writes no history: no replace or push, and the stored entry state is unchanged", async () => {
    // covers: UXP-591-5-ii
    // angle: boundary
    await openTab(nav, `/flows/${DEFAULT}`);
    const before = storedView();
    drillNode(labelOf(DEFAULT, "build"));
    await expectOnScreen({ flow: HOW });
    const w = watchNav(nav);
    await traverse("back");
    await expectOnScreen({ flow: DEFAULT, crumbs: [DEFAULT] });
    await traverse("forward");
    await expectOnScreen({ flow: HOW, crumbs: [DEFAULT, HOW] });
    expect(w.replace).not.toHaveBeenCalled();
    expect(w.push).not.toHaveBeenCalled();
    expect(window.history.length).toBe(w.length);
    expect(storedView()).toEqual({
      crumbs: [DEFAULT, HOW],
      filters: { source: "real", kind: "user", realization: "all" },
    });
    await traverse("back");
    await waitFor(() => expect(h1()).toContain(nameOf(DEFAULT)));
    if (before) expect(storedView()).toEqual(before);
  });

  it("each entry returns with the drawer its ?step= names and the filters it was left with", async () => {
    // covers: UXP-591-5-ii
    // angle: seam
    expect(otherBuiltUserFlow, "a second built Real/User flow").toBeTruthy();
    await openTab(nav, `/flows/${DEFAULT}`);
    clickNode(labelOf(DEFAULT, "plan"));
    setFilter("Realization", "Built");
    await expectOnScreen({ drawer: "plan" });
    expect(activeOf("Realization")).toBe("Built");
    selectFlow(otherBuiltUserFlow.name);
    await expectOnScreen({ flow: otherBuiltUserFlow.id, drawer: null });
    setFilter("Realization", "All");
    await waitFor(() => expect(activeOf("Realization")).toBe("All"));

    await traverse("back");
    await expectOnScreen({ flow: DEFAULT, drawer: "plan", address: `/flows/${DEFAULT}?step=plan` });
    // the filters it was left with: Built, so spec flows are not listed
    await waitFor(() => expect(activeOf("Realization")).toBe("Built"));
    expect(groupButtonsText("Flow").join(" | ")).not.toContain(nameOf("leafcutter/define-a-feature"));

    await traverse("forward");
    await expectOnScreen({ flow: otherBuiltUserFlow.id, drawer: null, address: `/flows/${otherBuiltUserFlow.id}` });
    await waitFor(() => expect(activeOf("Realization")).toBe("All"));
  });

  it("Back onto /flows/leafcutter/flow-render-pipline shows 'Flow not found' again with no flow drawn", async () => {
    // covers: UXP-591-5-ii
    // angle: failure
    await openNotFoundTab(nav, "/flows/leafcutter/flow-render-pipline");
    selectFlow(nameOf("leafcutter/explore-flows-in-atlas"));
    await expectOnScreen({ flow: "leafcutter/explore-flows-in-atlas" });
    expect(document.body.textContent).not.toContain("Flow not found");
    await traverse("back");
    await waitFor(() => {
      expect(document.body.textContent).toContain("No flow has the id 'leafcutter/flow-render-pipline'");
      expect(crumbNames()).toEqual([]);
      expect(h1()).not.toContain(nameOf(DEFAULT));
      expect(h1()).not.toContain(nameOf("leafcutter/explore-flows-in-atlas"));
    });
    expect(here()).toBe("/flows/leafcutter/flow-render-pipline");
  });

  it("restoring filters on a pop does not call replaceState or pushState", async () => {
    // covers: UXP-591-5-ii
    // angle: discrimination
    await openTab(nav, `/flows/${DEFAULT}`);
    setFilter("Realization", "Built");
    selectFlow(otherBuiltUserFlow.name);
    setFilter("Realization", "All");
    const w = watchNav(nav);
    await traverse("back");
    await waitFor(() => expect(activeOf("Realization")).toBe("Built"));
    expect(w.replace).not.toHaveBeenCalled();
    expect(w.push).not.toHaveBeenCalled();
  });

  it.each([
    ["drill-and-return", [1, 2, 3, 4, 5, 6]],
    ["shared-mock-journey", [1, 2, 3, 4, 5]],
    ["recover-from-unknown", [1, 2, 3]],
  ])("replays the %s session from atlas-flows.mock.json", async (session, seqs) => {
    // covers: UXP-591-5-ii
    // angle: real_artifact
    const rows = sessionRows(session, seqs as number[]);
    expect(rows.length).toBe((seqs as number[]).length);
    await replayRows(nav, rows);
  });
});
