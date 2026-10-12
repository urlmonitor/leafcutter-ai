/**
 * UXP-591-1-i - the bare /flows address keeps its address and opens the
 * default entry flow. (Ticket names test_uxp_591_1_i.py; vitest only collects
 * *.test.{ts,tsx}.)
 *
 * Planned design pinned here, shared with the UXP-591-1 tests:
 *  - lib/flow-url.ts exports DEFAULT_ENTRY_FLOW_ID (the single definition of
 *    "leafcutter/deliver-a-feature"; no second literal in the bare page or
 *    FlowsView).
 *  - app/flows/page.tsx hands FlowsView the same flat initial props as a
 *    canonical address: flowId, crumbs, filters, step.
 *
 * The middleware pass-through for bare /flows already holds today (it is
 * green before this AC), so it carries no red test of its own.
 */
import React from "react";
import fs from "node:fs";
import path from "node:path";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import { activeOf, load } from "./helpers/flow-routes";

const hoisted = vi.hoisted(() => ({
  captured: [] as Array<Record<string, unknown>>,
  routerPush: vi.fn(),
  routerReplace: vi.fn(),
}));

vi.mock("server-only", () => ({}));
vi.mock("next/navigation", () => ({
  notFound: vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
  useRouter: () => ({ push: hoisted.routerPush, replace: hoisted.routerReplace }),
  usePathname: () => "/flows",
  useSearchParams: () => new URLSearchParams(),
}));
// Record the props the page hands FlowsView, then render the real component.
vi.mock("@/components/flows/flows-view", async () => {
  const actual = await vi.importActual<typeof import("@/components/flows/flows-view")>(
    "@/components/flows/flows-view",
  );
  return {
    ...actual,
    FlowsView: (props: Record<string, unknown>) => {
      hoisted.captured.push(props);
      return React.createElement(actual.FlowsView as React.ComponentType<any>, props);
    },
  };
});

import { getFlows } from "@/lib/data/flows";

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
  hoisted.captured.length = 0;
  hoisted.routerPush.mockClear();
  hoisted.routerReplace.mockClear();
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

// first render pulls in the whole flow explorer; allow for a cold transform
vi.setConfig({ testTimeout: 60000 });

const DEFAULT_ID = "leafcutter/deliver-a-feature";

async function renderBare() {
  const mod = await load("@/app/flows/page");
  const el = await (mod.default as unknown as (p: unknown) => Promise<React.ReactElement>)({
    searchParams: {},
  });
  return render(el);
}

describe("bare /flows route", () => {
  it("draws the default entry flow at Real/User/All with a one-flow breadcrumb, no drawer, no notice", async () => {
    // covers: UXP-591-1-i
    // angle: reachability
    const { DEFAULT_ENTRY_FLOW_ID } = await load("@/lib/flow-url");
    expect(DEFAULT_ENTRY_FLOW_ID).toBe(DEFAULT_ID);
    const name = getFlows().find((f) => f.id === DEFAULT_ENTRY_FLOW_ID)!.name;
    expect(name).toBe("Deliver a feature end-to-end");

    await renderBare();

    expect(screen.getByRole("heading", { level: 1 }).textContent).toContain(name);
    expect(activeOf("Source")).toBe("Real");
    expect(activeOf("Kind")).toBe("User");
    expect(activeOf("Flow")).toContain(name);
    for (const n of screen.queryAllByRole("navigation")) {
      expect(within(n).queryAllByRole("button").length).toBeLessThanOrEqual(1);
    }
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.body.textContent).not.toContain("Flow not found");
    expect(document.body.textContent).not.toContain("Step not found");
  });

  it("passes FlowsView the same initial props as a canonical address", async () => {
    // covers: UXP-591-1-i
    // angle: seam
    await renderBare();
    expect(hoisted.captured.length).toBeGreaterThan(0);
    const props = hoisted.captured[0];
    expect(props.flowId).toBe(DEFAULT_ID);
    expect(props.crumbs).toEqual([DEFAULT_ID]);
    expect(props.filters).toEqual({ source: "real", kind: "user", realization: "all" });
    expect(props.step).toBeNull();
  });

  it("keeps the address at /flows after mount: no history rewrite, no router navigation", async () => {
    // covers: UXP-591-1-i
    // angle: failure
    const { DEFAULT_ENTRY_FLOW_ID } = await load("@/lib/flow-url");
    window.history.pushState({}, "", "/flows");
    const replaceState = vi.spyOn(window.history, "replaceState");
    const pushState = vi.spyOn(window.history, "pushState");

    await renderBare();
    await new Promise((r) => setTimeout(r, 0)); // let mount effects run

    expect(screen.getByRole("heading", { level: 1 }).textContent).toContain(
      getFlows().find((f) => f.id === DEFAULT_ENTRY_FLOW_ID)!.name,
    );
    expect(window.location.pathname).toBe("/flows");
    expect(replaceState).not.toHaveBeenCalled();
    expect(pushState).not.toHaveBeenCalled();
    expect(hoisted.routerReplace).not.toHaveBeenCalled();
    expect(hoisted.routerPush).not.toHaveBeenCalled();
  });
});

describe("default entry flow id has exactly one definition", () => {
  it("is not re-typed in the bare page or FlowsView", () => {
    // covers: UXP-591-1-i
    // angle: discrimination
    const root = process.cwd();
    const files = [
      "app/flows/page.tsx",
      "components/flows/flows-view.tsx",
      "app/flows/[...id]/page.tsx",
    ].filter((f) => fs.existsSync(path.join(root, f)));
    const hits = files.filter((f) =>
      fs.readFileSync(path.join(root, f), "utf8").includes(`"${DEFAULT_ID}"`),
    );
    expect(hits).toEqual([]);
  });
});
