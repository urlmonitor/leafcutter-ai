/**
 * UXP-591-4-ii - closing the drawer returns the address to the flow's
 * canonical address without adding a Back entry. (Ticket names a Python test
 * file; vitest only collects *.test.{ts,tsx}.)
 *
 * Amended 2026-10-14 (UXP-617): the bare-/flows clause is gone; /flows is the
 * finder and has no drawer to close.
 */
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen } from "@testing-library/react";
import { closeWithCanvas, closeWithX, drawers, expectDrawers } from "../helpers/flow-routes";
import { drillNode, expectOnScreen, labelOf, openTab, traverse } from "../helpers/flow-history-nav";
import { expectReplaced, openAt, watchHistory, type NavState } from "../helpers/drawer-nav";

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

  it("after closing the drawer and drilling into Build, Back returns deliver-a-feature at its canonical address with no drawer", async () => {
    // covers: UXP-591-4-ii
    // angle: seam
    await openTab(nav, `/flows/${DEFAULT}?step=build`);
    expect(drawers().map((d) => d.id)).toEqual(["build"]);
    closeWithX();
    await expectDrawers([]);
    drillNode(labelOf(DEFAULT, "build"));
    await expectOnScreen({ flow: "leafcutter/how-acs-are-built", drawer: null });
    await traverse("back");
    await expectOnScreen({ flow: DEFAULT, crumbs: [DEFAULT], drawer: null, address: `/flows/${DEFAULT}` });
  });

  it("the finder at /flows has no drawer to close: no graph node, no close button, no history write", async () => {
    // covers: UXP-591-4-ii
    // angle: boundary
    window.history.replaceState({}, "", "/flows");
    const w = watchHistory(nav);
    await openAt(nav, "/flows");
    await new Promise((r) => setTimeout(r, 0));

    expect(document.querySelector(".react-flow__node")).toBeNull();
    expect(document.querySelector(".react-flow__pane")).toBeNull();
    expect(screen.queryByRole("button", { name: "Close step details" })).toBeNull();
    for (const call of w.replace.mock.calls) expect(String(call[2])).not.toContain("step=");
    expect(w.push).not.toHaveBeenCalled();
    expect(window.location.pathname + window.location.search).toBe("/flows");
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
