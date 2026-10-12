/**
 * UXP-591-4-ii regression - the address's ?step= seeds the drawer only on the
 * first mount of the flow the address named. After the drawer is closed, a
 * drill and a breadcrumb back to that flow remounts the explorer; it must come
 * back with no drawer, matching the canonical address, not re-open the stale step.
 */
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent } from "@testing-library/react";
import { clickNode, closeWithX, drawers, expectDrawers, squash } from "../helpers/flow-routes";
import { openAt, type NavState } from "../helpers/drawer-nav";

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

/** Drill into the sub-flow of the first drillable step, then click the first crumb back. */
async function drillAndReturn() {
  const drill = document.querySelector("[data-flow-drill]");
  expect(drill, "a drillable step in the default flow").toBeTruthy();
  fireEvent.click(drill as Element);
  const crumbs = document.querySelectorAll("nav button");
  expect(crumbs.length).toBeGreaterThan(1);
  fireEvent.click(crumbs[0]);
  await expectDrawers([]);
  expect(document.querySelectorAll("nav button").length).toBe(0);
}

describe("explorer remount after the first drawer change", () => {
  it("closing ?step=plan, drilling and returning leaves no drawer and the canonical address", async () => {
    // covers: UXP-591-4-ii
    // angle: failure
    await openAt(nav, `/flows/${DEFAULT}?step=plan`);
    expect(drawers().map((d) => d.id)).toEqual(["plan"]);
    closeWithX();
    await expectDrawers([]);
    expect(window.location.pathname + window.location.search).toBe(`/flows/${DEFAULT}`);
    await drillAndReturn();
    expect(drawers()).toHaveLength(0);
    expect(window.location.pathname + window.location.search).toBe(`/flows/${DEFAULT}`);
  });

  it("switching plan to build, then drilling and returning, does not revert to plan", async () => {
    // covers: UXP-591-4-ii
    // angle: failure
    await openAt(nav, `/flows/${DEFAULT}?step=plan`);
    clickNode("Build");
    expect(drawers().map((d) => d.id)).toEqual(["build"]);
    await drillAndReturn();
    expect(drawers().map((d) => d.id)).not.toContain("plan");
    expect(squash(document.body.textContent)).not.toContain("Step not found");
  });
});
