/**
 * UXP-591-5-iii (amended 2026-10-14) - a Source, Kind or Realization change
 * never picks or swaps the drawn flow: it rewrites the current entry in place
 * (same URL, ?step= kept, new filters in the entry's view state), and an
 * 'Outside the current filters' notice shows when the entry flow no longer
 * fits. (Ticket names a Python test file; vitest only collects
 * *.test.{ts,tsx}.)
 *
 * Replaces the PR #1176 re-pick tests. The notice is derived from the entry
 * flow (crumbs[0]) and the filters, never stored; it clears only when another
 * flow is picked (a push) or the filters match again.
 */
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, waitFor } from "@testing-library/react";
import { activeOf, clickNode, closeWithX, squash } from "../helpers/flow-routes";
import {
  DEFAULT,
  addressOf,
  crumbNames,
  drillNode,
  expectNoRouter,
  expectOnScreen,
  groupButtonsText,
  h1,
  labelOf,
  nameOf,
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
const TITLE = "Outside the current filters";
const body = () => squash(document.body.textContent);

/** deliver-a-feature -> drill into how-acs-are-built -> code drawer open (two entries). */
async function drilledWithDrawer() {
  await openTab(nav, `/flows/${DEFAULT}`);
  drillNode(labelOf(DEFAULT, "build"));
  await expectOnScreen({ flow: HOW });
  clickNode(labelOf(HOW, "code"));
  await expectOnScreen({ drawer: "code", address: `/flows/${HOW}?step=code` });
}

const noticeDetail = (entry: string, source: string, kind: string, realization: string) =>
  `'${nameOf(entry)}' is not a ${source} · ${kind} · ${realization} flow, so the flow list no longer shows it. It stays on screen until you pick another flow.`;

describe("a filter change that excludes the entry flow keeps the drawn flow", () => {
  it("Realization Spec keeps how-acs-are-built, its breadcrumb and drawer, keeps ?step=code and two entries, and shows the notice", async () => {
    // covers: UXP-591-5-iii
    // angle: criterion
    await drilledWithDrawer();
    const before = window.history.length;
    const w = watchNav(nav);
    setFilter("Realization", "Spec");

    await expectOnScreen({
      flow: HOW,
      crumbs: [DEFAULT, HOW],
      drawer: "code",
      address: `/flows/${HOW}?step=code`,
    });
    // the same URL (?step= kept) is written once, in place: never a push, never another flow
    await waitFor(() => expect(w.replace).toHaveBeenCalledTimes(1));
    expect(addressOf(w.replace.mock.calls[0][2])).toBe(`/flows/${HOW}?step=code`);
    expect(w.push).not.toHaveBeenCalled();
    expect(window.history.length).toBe(before);
    expectNoRouter(nav);
    expect(storedView()).toEqual({
      crumbs: [DEFAULT, HOW],
      filters: { source: "real", kind: "user", realization: "spec" },
    });
    // the dataset's wording, exactly
    expect(body()).toContain(TITLE);
    expect(body()).toContain(
      "'Deliver a feature end-to-end' is not a Real · User · Spec flow, so the flow list no longer shows it. It stays on screen until you pick another flow.",
    );
    // the selector follows the filters even though it no longer lists the drawn flow
    const listed = groupButtonsText("Flow").join(" | ");
    expect(listed).not.toContain(nameOf(DEFAULT));
    expect(listed).toContain(nameOf(DEFINE));
    expect(h1()).not.toContain(nameOf(DEFINE));
  });

  it("Back returns deliver-a-feature at Real, User, All with no notice; Forward brings back Spec and the notice", async () => {
    // covers: UXP-591-5-iii
    // angle: seam
    await drilledWithDrawer();
    setFilter("Realization", "Spec");
    await waitFor(() => expect(body()).toContain(TITLE));

    await traverse("back");
    await expectOnScreen({ flow: DEFAULT, crumbs: [DEFAULT], drawer: null, address: `/flows/${DEFAULT}` });
    await waitFor(() => expect(activeOf("Realization")).toBe("All"));
    expect(activeOf("Source")).toBe("Real");
    expect(activeOf("Kind")).toBe("User");
    expect(body()).not.toContain(TITLE);

    await traverse("forward");
    await expectOnScreen({ flow: HOW, crumbs: [DEFAULT, HOW], drawer: "code", address: `/flows/${HOW}?step=code` });
    await waitFor(() => expect(activeOf("Realization")).toMatch(/spec/i));
    expect(body()).toContain(noticeDetail(DEFAULT, "Real", "User", activeOf("Realization")));
  });

  it("replays filter-replace seq 1 to 7, including the notice records -5 and -7 and the notice-free -6", async () => {
    // covers: UXP-591-5-iii
    // angle: real_artifact
    const rows = sessionRows("filter-replace", [1, 2, 3, 4, 5, 6, 7]);
    expect(rows).toHaveLength(7);
    expect(rows[4].scope_notice).not.toBeNull(); // the dataset sets the notice on -5 and -7 only
    expect(rows[5].scope_notice).toBeNull();
    expect(rows[6].scope_notice).not.toBeNull();
    await replayRows(nav, rows);
  });

  it.each([
    ["Source", "Mock", "Mock", "User", "All"],
    ["Kind", "Data", "Real", "Data", "All"],
    ["Realization", "Spec", "Real", "User", "Spec"],
  ])("%s %s keeps the drawn flow and shows the notice naming the three filter labels", async (group, option, s, k, r) => {
    // covers: UXP-591-5-iii
    // angle: boundary
    await openTab(nav, `/flows/${DEFAULT}?step=plan`);
    const w = watchNav(nav);
    setFilter(group as "Source" | "Kind" | "Realization", option);

    await waitFor(() => expect(body()).toContain(TITLE));
    expect(body()).toContain(noticeDetail(DEFAULT, s, k, r));
    expect(h1()).toContain(nameOf(DEFAULT));
    expect(crumbNames()).toEqual([]);
    await expectOnScreen({ drawer: "plan", address: `/flows/${DEFAULT}?step=plan` });
    expect(w.replace).toHaveBeenCalledTimes(1);
    expect(addressOf(w.replace.mock.calls[0][2])).toBe(`/flows/${DEFAULT}?step=plan`);
    expect(w.push).not.toHaveBeenCalled();
    expect(window.history.length).toBe(w.length);
  });

  it("no notice while the filters still fit the entry flow: Built or All, and again once they match", async () => {
    // covers: UXP-591-5-iii
    // angle: boundary
    await openTab(nav, `/flows/${DEFAULT}`);
    expect(body()).not.toContain(TITLE);
    setFilter("Realization", "Built"); // deliver-a-feature is a built flow: its own realization
    await waitFor(() => expect(activeOf("Realization")).toBe("Built"));
    expect(body()).not.toContain(TITLE);
    setFilter("Realization", "Spec");
    await waitFor(() => expect(body()).toContain(TITLE));
    setFilter("Realization", "All"); // the filters match the entry flow again
    await waitFor(() => expect(body()).not.toContain(TITLE));
    expect(h1()).toContain(nameOf(DEFAULT));
  });
});

describe("the notice stays until another flow is picked", () => {
  it("drawer actions leave it on screen; picking a flow the filters list pushes an entry and clears it", async () => {
    // covers: UXP-591-5-iii
    // angle: discrimination
    await openTab(nav, `/flows/${DEFAULT}`);
    setFilter("Realization", "Spec");
    await waitFor(() => expect(body()).toContain(TITLE));

    clickNode(labelOf(DEFAULT, "plan"));
    await expectOnScreen({ drawer: "plan", address: `/flows/${DEFAULT}?step=plan` });
    expect(body()).toContain(TITLE);
    closeWithX();
    await expectOnScreen({ drawer: null, address: `/flows/${DEFAULT}` });
    expect(body()).toContain(TITLE);

    const before = window.history.length;
    selectFlow(nameOf(DEFINE)); // a Spec flow: the filters list it
    await expectOnScreen({ flow: DEFINE, crumbs: [DEFINE], address: `/flows/${DEFINE}` });
    expect(window.history.length).toBe(before + 1); // the ordinary select push
    expect(body()).not.toContain(TITLE);
  });
});
