/**
 * UXP-591-2-ii - opening a real drawer after a 'Step not found' notice clears
 * the notice and replaces the unknown step in place. (Ticket names a Python
 * test file; vitest only collects *.test.{ts,tsx}. The select-another-flow
 * then Back half belongs to UXP-591-5 and is not tested here.)
 */
import fs from "node:fs";
import path from "node:path";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup } from "@testing-library/react";
import { clickNode, drawers, squash } from "../helpers/flow-routes";
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

const FLOW = "leafcutter/python-coder-internal";
const mockFile = path.resolve(
  process.cwd(),
  "../docs/product-truth/mock-data/leafcutter/atlas-flows.mock.json",
);
const session = (
  JSON.parse(fs.readFileSync(mockFile, "utf8")).entities.FlowNavigation.records as any[]
)
  .filter((r) => r.session === "clear-step-notice")
  .sort((a, b) => a.seq - b.seq);

describe("opening a real drawer from the 'Step not found' state", () => {
  it("clicking Doc-enforcer clears the notice, opens its drawer and replaces ?step=lint with ?step=docenforce", async () => {
    // covers: UXP-591-2-ii
    // angle: criterion
    await openAt(nav, `/flows/${FLOW}?step=lint`);
    expect(squash(document.body.textContent)).toContain("Step not found");
    const w = watchHistory(nav);
    clickNode("Doc-enforcer");
    expect(document.body.textContent).not.toContain("Step not found");
    expect(drawers().map((d) => d.id)).toEqual(["docenforce"]);
    // one replace, never a push and never a second write
    expectReplaced(nav, w, `/flows/${FLOW}?step=docenforce`);
    expect(String(w.replace.mock.calls[0][2])).not.toContain("lint");
  });

  it("replays the clear-step-notice session's load and open-drawer rows from atlas-flows.mock.json", async () => {
    // covers: UXP-591-2-ii
    // angle: real_artifact
    const [load, open] = session;
    expect(load.step_notice).not.toBeNull();
    expect(open.history_op).toBe("replace");
    await openAt(nav, load.address_bar);
    expect(squash(document.body.textContent)).toContain(load.step_notice.detail);
    const w = watchHistory(nav);
    clickNode("Doc-enforcer");
    expect(open.step_notice).toBeNull();
    expect(document.body.textContent).not.toContain(load.step_notice.title);
    expect(drawers().map((d) => d.id)).toEqual([open.drawer]);
    expectReplaced(nav, w, open.address_bar);
  });

  it("the entry's stored view state no longer names the unknown step", async () => {
    // covers: UXP-591-2-ii
    // angle: seam
    await openAt(nav, `/flows/${FLOW}?step=lint`);
    const w = watchHistory(nav);
    clickNode("Doc-enforcer");
    expect(w.replace).toHaveBeenCalledTimes(1);
    const state = window.history.state as Record<string, any>;
    expect(state.__NA).toBe(true);
    expect(JSON.stringify(state)).not.toContain("lint");
    expect(window.location.search).not.toContain("lint");
  });

  it("control: with a known step already open the notice never shows and a click still replaces once", async () => {
    // covers: UXP-591-2-ii
    // angle: discrimination
    await openAt(nav, `/flows/${FLOW}?step=conventions`);
    expect(document.body.textContent).not.toContain("Step not found");
    const w = watchHistory(nav);
    clickNode("Doc-enforcer");
    expectReplaced(nav, w, `/flows/${FLOW}?step=docenforce`);
  });
});
