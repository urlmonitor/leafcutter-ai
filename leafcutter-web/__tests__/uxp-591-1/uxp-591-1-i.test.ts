/**
 * UXP-591-1-i (amended 2026-10-14) - the bare /flows address is the finder
 * overview: 200, no redirect, the address stays, no flow is drawn or selected.
 * (Ticket names test_uxp_591_1_i.py; vitest only collects *.test.{ts,tsx}.)
 *
 * Replaces the PR #1176 tests that asserted a default entry flow on bare
 * /flows. The finder's content is UXP-617-1 (tests under __tests__/uxp-617-1/);
 * this file keeps the route half: what the route answers and never rewrites.
 */
import fs from "node:fs";
import path from "node:path";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen } from "@testing-library/react";
import { addressOf, redirectOf, runMiddleware } from "../helpers/flow-routes";
import { pageElement, renderFinderPage, searchBox, statusText } from "../helpers/flow-finder-ui";

const hoisted = vi.hoisted(() => ({
  flowsViewMounted: 0,
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
  useSearchParams: () => new URLSearchParams(window.location.search),
}));
// Count how often the page mounts the flow view; render the real component when it does.
vi.mock("@/components/flows/flows-view", async () => {
  const actual = await vi.importActual<typeof import("@/components/flows/flows-view")>(
    "@/components/flows/flows-view",
  );
  return {
    ...actual,
    FlowsView: (props: Record<string, unknown>) => {
      hoisted.flowsViewMounted += 1;
      return React.createElement(actual.FlowsView as React.ComponentType<any>, props);
    },
  };
});

import { getFlows } from "@/lib/data/flows";

// first render pulls in the page's whole component tree; allow for a cold transform
vi.setConfig({ testTimeout: 180000 });

beforeEach(() => {
  hoisted.flowsViewMounted = 0;
  hoisted.routerPush.mockClear();
  hoisted.routerReplace.mockClear();
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

const BASE = "http://localhost";

describe("bare /flows route", () => {
  it("shows the finder instead of a flow: no flow drawn or selected, no breadcrumb, drawer or notice", async () => {
    // covers: UXP-591-1-i
    // angle: reachability
    await renderFinderPage({});

    expect(statusText()).toBe(`${getFlows().length} flows`);
    expect(searchBox().value).toBe("");
    expect(hoisted.flowsViewMounted).toBe(0); // the flow view is not what /flows serves
    expect(document.querySelector(".react-flow")).toBeNull();
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Flows");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.queryByRole("navigation", { name: /breadcrumb/i })).toBeNull();
    expect(document.querySelector("nav button")).toBeNull();
    expect(document.body.textContent).not.toContain("Flow not found");
    expect(document.body.textContent).not.toContain("Step not found");
    expect(document.body.textContent).not.toContain("Outside the current filters");
  });

  it("/flows?q=selected+option&actor=human opens the finder with the search and the Person value", async () => {
    // covers: UXP-591-1-i
    // angle: criterion
    await renderFinderPage({ q: "selected option", actor: "human" });

    expect(hoisted.flowsViewMounted).toBe(0);
    expect(searchBox().value).toBe("selected option");
    expect(screen.getByRole("button", { name: "Remove filter Actor: Person" })).toBeTruthy();
    expect(statusText()).toMatch(/^\d+ flows?, \d+ steps? match$/);
    expect(document.querySelector(".react-flow")).toBeNull();
  });

  it("the page never answers notFound() or a redirect for /flows with or without a finder query", async () => {
    // covers: UXP-591-1-i
    // angle: failure
    for (const sp of [{}, { q: "selected option", actor: "human" }, { q: "zzzzqx" }]) {
      await expect(pageElement(sp)).resolves.toBeTruthy();
    }
  });

  it.each([
    ["the address as typed, in non-canonical parameter order", { actor: "human", q: "selected option" }],
    ["a bare /flows", {}],
  ])("keeps %s after mount: no history rewrite, no router navigation", async (_name, sp) => {
    // covers: UXP-591-1-i
    // angle: failure
    const qs = new URLSearchParams(sp as Record<string, string>).toString();
    const typed = "/flows" + (qs ? "?" + qs : "");
    window.history.replaceState({}, "", typed);
    const replaceState = vi.spyOn(window.history, "replaceState");
    const pushState = vi.spyOn(window.history, "pushState");

    await renderFinderPage(sp as Record<string, string>);
    await new Promise((r) => setTimeout(r, 0)); // let mount effects run

    // every write (the harness's own address setup is the same typed address) is the typed address
    for (const call of replaceState.mock.calls) expect(addressOf(call[2])).toBe(typed);
    expect(pushState).not.toHaveBeenCalled();
    expect(hoisted.routerReplace).not.toHaveBeenCalled();
    expect(hoisted.routerPush).not.toHaveBeenCalled();
    expect(window.location.pathname + window.location.search).toBe(typed);
  });
});

describe("middleware leaves /flows alone", () => {
  it.each([`${BASE}/flows`, `${BASE}/flows?q=selected+option&actor=human`])(
    "%s passes through with no redirect or rewrite",
    async (url) => {
      // covers: UXP-591-1-i
      // angle: criterion
      const res = await runMiddleware(url);
      expect(res.status).toBe(200);
      expect(res.headers.get("location")).toBeNull();
      expect(res.headers.get("x-middleware-rewrite")).toBeNull();
    },
  );

  it("control: only a 'flow' parameter makes /flows a legacy redirect (308)", async () => {
    // covers: UXP-591-1-i
    // angle: discrimination
    const r = await redirectOf(`${BASE}/flows?flow=leafcutter%2Fflow-render-pipeline&step=resolve`);
    expect(r.res.status).toBe(308);
    expect(r.path).toBe("/flows/leafcutter/flow-render-pipeline");
    // a finder query that merely mentions a step or a flow word in q is not a legacy link
    const finder = await redirectOf(`${BASE}/flows?q=flow+step`);
    expect(finder.location).toBeNull();
  });
});

describe("no default entry flow remains", () => {
  it("the default-entry constant and its flow id are gone from the page, the view model and the url helper", () => {
    // covers: UXP-591-1-i
    // angle: discrimination
    const root = process.cwd();
    const files = [
      "app/flows/page.tsx",
      "components/flows/flow-view-model.ts",
      "components/flows/flows-view.tsx",
      "lib/flow-url.ts",
    ].filter((f) => fs.existsSync(path.join(root, f)));
    expect(files.length).toBeGreaterThan(0);
    const hits = files.flatMap((f) => {
      const src = fs.readFileSync(path.join(root, f), "utf8");
      return [
        src.includes("DEFAULT_ENTRY_FLOW_ID") ? `${f}: DEFAULT_ENTRY_FLOW_ID` : null,
        src.includes('"leafcutter/deliver-a-feature"') ? `${f}: "leafcutter/deliver-a-feature"` : null,
      ].filter(Boolean);
    });
    expect(hits).toEqual([]);
  });
});
