/**
 * UXP-591-4 - opening a step's or branch's drawer in the Flows view puts its
 * step address in the address bar without adding a Back entry (replaceState
 * semantics). (Ticket names a Python test file; vitest only collects
 * *.test.{ts,tsx}. The Playwright spec is deferred.)
 *
 * Amended 2026-10-14 (UXP-617): bare /flows is the finder, so no drawer opens there
 * and /flows is never rewritten to a step address; the owner-ruling-1 tests and
 * the drawer-on-bare-flows session (removed from dataset v4) are gone. Keyboard
 * open/close is replayed with clicks here; the keys are UXP-617-3-i.
 *
 * jsdom does not run the App Router's history integration, so these tests pin
 * what the view asks the browser to do: one window.history.replaceState to the
 * step address, no pushState, no router.push / router.replace, no new entry.
 * The intent callback between explorer and view is not pinned: tests click
 * graph nodes. The namespaced history.state key is not pinned either.
 */
import fs from "node:fs";
import path from "node:path";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen } from "@testing-library/react";
import { clickNode, closeWithX, drawers, addressOf, expectDrawers } from "../helpers/flow-routes";
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

import { getFlows } from "@/lib/data/flows";

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
const labelOf = (flowId: string, nodeId: string) => {
  const f = getFlows().find((x) => x.id === flowId)!;
  return [...f.steps, ...f.branches].find((x) => x.id === nodeId)!.label;
};

const mockFile = path.resolve(
  process.cwd(),
  "../docs/product-truth/mock-data/leafcutter/atlas-flows.mock.json",
);
const navRecords = JSON.parse(fs.readFileSync(mockFile, "utf8")).entities.FlowNavigation
  .records as any[];
// The drawer-only part of a session: its load plus the open/close actions that
// precede the first drill / select / back.
function drawerSession(session: string) {
  const recs = navRecords.filter((r) => r.session === session).sort((a, b) => a.seq - b.seq);
  const out: any[] = [];
  for (const r of recs) {
    if (!["load", "open-drawer", "close-drawer"].includes(r.action)) break;
    out.push(r);
  }
  return out;
}

describe("opening a drawer replaces the address", () => {
  it("clicking Plan on /flows/leafcutter/deliver-a-feature opens it and replaces the address with ?step=plan", async () => {
    // covers: UXP-591-4
    // angle: criterion
    await openAt(nav, `/flows/${DEFAULT}`);
    const nodeBefore = document.querySelector(".react-flow__node");
    const w = watchHistory(nav);
    clickNode(labelOf(DEFAULT, "plan"));
    expect(drawers().map((d) => d.id)).toEqual(["plan"]);
    expectReplaced(nav, w, `/flows/${DEFAULT}?step=plan`);
    // no remount: the explorer's nodes are the same elements
    expect(nodeBefore!.isConnected).toBe(true);
  });

  it("the finder at /flows renders no flow node or drawer, so no history write turns /flows into a step address", async () => {
    // covers: UXP-591-4
    // angle: boundary
    window.history.replaceState({}, "", "/flows");
    const w = watchHistory(nav);
    await openAt(nav, "/flows");
    await new Promise((r) => setTimeout(r, 0)); // let mount effects run

    expect(document.querySelector(".react-flow__node")).toBeNull();
    expect(screen.queryByRole("button", { name: "Close step details" })).toBeNull();
    // nothing the finder does writes a step address, and nothing adds an entry
    for (const call of w.replace.mock.calls) {
      expect(addressOf(call[2])).toBe("/flows");
      expect(String(call[2])).not.toContain("step=");
    }
    expect(w.push).not.toHaveBeenCalled();
    expect(nav.routerPush).not.toHaveBeenCalled();
    expect(nav.routerReplace).not.toHaveBeenCalled();
    expect(window.location.pathname + window.location.search).toBe("/flows");
    expect(window.history.length).toBe(w.length);
  });

  it("the replaced address reopened through the catch-all route shows the same Plan drawer", async () => {
    // covers: UXP-591-4
    // angle: reachability
    await openAt(nav, `/flows/${DEFAULT}`);
    clickNode(labelOf(DEFAULT, "plan"));
    const after = window.location.pathname + window.location.search;
    expect(after).toBe(`/flows/${DEFAULT}?step=plan`);
    cleanup();
    await openAt(nav, after);
    expect(drawers().map((d) => d.id)).toEqual(["plan"]);
  });

  it("opens a branch drawer the same way: checkout-and-pay declined -> ?step=declined", async () => {
    // covers: UXP-591-4
    // angle: boundary
    const id = "fern-and-fig/checkout-and-pay";
    await openAt(nav, `/flows/${id}`);
    const w = watchHistory(nav);
    clickNode(labelOf(id, "declined"));
    expect(drawers().map((d) => d.id)).toEqual(["declined"]);
    expectReplaced(nav, w, `/flows/${id}?step=declined`);
  });

  it("keeps the App Router's history.state keys and adds the entry's view state beside them", async () => {
    // covers: UXP-591-4
    // angle: failure
    await openAt(nav, `/flows/${DEFAULT}`);
    const w = watchHistory(nav);
    clickNode(labelOf(DEFAULT, "plan"));
    expect(w.replace).toHaveBeenCalledTimes(1);
    const state = window.history.state as Record<string, any>;
    expect(state.__NA).toBe(true);
    expect(state.__PRIVATE_NEXTJS_INTERNALS_TREE).toEqual(["", {}]);
    const viewState = Object.values(state).find(
      (v) => v && typeof v === "object" && !Array.isArray(v) && "crumbs" in v,
    ) as { crumbs: string[]; filters: Record<string, string> } | undefined;
    expect(viewState).toBeTruthy();
    expect(viewState!.crumbs).toEqual([DEFAULT]);
    expect(viewState!.filters).toEqual({ source: "real", kind: "user", realization: "all" });
  });

  it.each(["drawer-replace", "clear-step-notice", "keyboard-step-drawer"])(
    "replays the %s session's drawer actions from atlas-flows.mock.json",
    async (session) => {
      // covers: UXP-591-4
      // angle: real_artifact
      const recs = drawerSession(session);
      expect(recs.length).toBeGreaterThan(1);
      await openAt(nav, recs[0].address_bar);
      const w = watchHistory(nav);
      let writes = 0;
      for (const r of recs.slice(1)) {
        expect(r.history_op).toBe("replace");
        if (r.action === "open-drawer") clickNode(labelOf(r.rendered_flow, r.drawer));
        else closeWithX();
        writes += 1;
        expect(w.replace).toHaveBeenCalledTimes(writes);
        expect(addressOf(w.replace.mock.calls[writes - 1][2])).toBe(r.address_bar);
        await expectDrawers(r.drawer ? [r.drawer] : []);
      }
      expect(w.push).not.toHaveBeenCalled();
      expect(window.history.length).toBe(w.length);
    },
  );
});
