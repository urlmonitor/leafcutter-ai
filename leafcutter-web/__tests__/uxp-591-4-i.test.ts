/**
 * UXP-591-4-i - switching from one drawer to another swaps the single ?step=
 * value without adding a Back entry. (Ticket names a Python test file; vitest
 * only collects *.test.{ts,tsx}. The real-click scrim spec needs Chromium and
 * is deferred: jsdom does no hit-testing.)
 */
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup } from "@testing-library/react";
import { clickNode, closeWithCanvas, drawers, expectDrawers } from "./helpers/flow-routes";
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

describe("switching drawers", () => {
  it("clicking Build while Plan is open leaves only Build open at ?step=build, one replace, no new entry", async () => {
    // covers: UXP-591-4-i
    // angle: criterion
    await openAt(nav, `/flows/${DEFAULT}?step=plan`);
    expect(drawers().map((d) => d.id)).toEqual(["plan"]);
    const w = watchHistory(nav);
    clickNode("Build");
    expect(drawers().map((d) => d.id)).toEqual(["build"]);
    // one write: no intermediate close-then-open
    expectReplaced(nav, w, `/flows/${DEFAULT}?step=build`);
  });

  it("the switched address carries exactly one step parameter", async () => {
    // covers: UXP-591-4-i
    // angle: boundary
    await openAt(nav, `/flows/${DEFAULT}?step=plan`);
    watchHistory(nav);
    clickNode("Build");
    const sp = new URLSearchParams(window.location.search);
    expect(sp.getAll("step")).toEqual(["build"]);
  });

  it("switching twice (Plan, Build, Finalize) still writes one replace per click and ends on one drawer", async () => {
    // covers: UXP-591-4-i
    // angle: boundary
    await openAt(nav, `/flows/${DEFAULT}?step=plan`);
    const w = watchHistory(nav);
    clickNode("Build");
    clickNode("Finalize");
    expect(drawers().map((d) => d.id)).toEqual(["finalize"]);
    expectReplaced(nav, w, `/flows/${DEFAULT}?step=finalize`, 2);
  });

  it("a click on empty canvas beside the open drawer still closes it, back to the canonical address", async () => {
    // covers: UXP-591-4-i
    // angle: failure
    await openAt(nav, `/flows/${DEFAULT}?step=plan`);
    const w = watchHistory(nav);
    closeWithCanvas();
    await expectDrawers([]);
    expectReplaced(nav, w, `/flows/${DEFAULT}`);
  });

  it("control: re-clicking the open node does not add an entry or a second step value", async () => {
    // covers: UXP-591-4-i
    // angle: discrimination
    await openAt(nav, `/flows/${DEFAULT}?step=plan`);
    const w = watchHistory(nav);
    clickNode("Build");
    clickNode("Build");
    expect(w.push).not.toHaveBeenCalled();
    expect(window.history.length).toBe(w.length);
    expect(new URLSearchParams(window.location.search).getAll("step")).toEqual(["build"]);
    expect(drawers().map((d) => d.id)).toEqual(["build"]);
  });
});
