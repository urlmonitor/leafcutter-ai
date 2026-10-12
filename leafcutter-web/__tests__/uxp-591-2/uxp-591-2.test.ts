/**
 * UXP-591-2 - a step address (/flows/<product>/<flow>?step=<id>) opens the
 * flow with that step's or branch's drawer already open. (Ticket names a
 * Python test file; vitest only collects *.test.{ts,tsx}.)
 *
 * The drawer is the FlowDrawer <aside>; exactly one may be open. The step id
 * comes from searchParams.step on the catch-all route and from FlowsView's
 * flat `step` prop. Playwright and SSR-HTML checks are out of scope here.
 */
import React from "react";
import fs from "node:fs";
import path from "node:path";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import {
  activeOf,
  drawers,
  forwardedHeaders,
  load,
  paramsFor,
  runMiddleware,
  searchParamsOf,
} from "../helpers/flow-routes";

const hoisted = vi.hoisted(() => ({ headers: new Headers() }));

vi.mock("server-only", () => ({}));
vi.mock("next/headers", () => ({ headers: () => hoisted.headers }));
vi.mock("next/navigation", () => ({
  notFound: vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
  redirect: vi.fn(),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/flows",
  useSearchParams: () => new URLSearchParams(),
}));

import { getFlows, mockById, getScreenTitles } from "@/lib/data/flows";
import { FlowDrawer } from "@/components/flows/flow-drawer";
import { buildStepViews } from "@/components/flows/flow-step-view";
import { FlowsView } from "@/components/flows/flows-view";
import type { MockData } from "@/lib/data/types";

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
  hoisted.headers = new Headers();
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

/** Arrive at an address the way Next.js would: middleware, then the catch-all page. */
async function openAddress(url: string) {
  const abs = `http://localhost${url}`;
  hoisted.headers = forwardedHeaders(await runMiddleware(abs));
  const mod = await load("@/app/flows/[...id]/page");
  const el = await mod.default({ params: paramsFor(abs), searchParams: searchParamsOf(abs) });
  return render(el);
}

const flowOf = (id: string) => getFlows().find((f) => f.id === id)!;
const stepLabel = (flowId: string, stepId: string) => {
  const f = flowOf(flowId);
  return [...f.steps, ...f.branches].find((x) => x.id === stepId)!.label;
};

const mockFile = path.resolve(
  process.cwd(),
  "../docs/product-truth/mock-data/leafcutter/atlas-flows.mock.json",
);
const drawerRoutes = (
  JSON.parse(fs.readFileSync(mockFile, "utf8")).entities.FlowRoute.records as any[]
).filter((r) => r.resolution === "selected" && r.open_drawer !== null && r.http_status === 200);

describe("step address opens the drawer", () => {
  it("leafcutter/flow-render-pipeline?step=resolve opens only the resolve drawer at Real/Data/All", async () => {
    // covers: UXP-591-2
    // angle: reachability
    const { notFound } = await import("next/navigation");
    await openAddress("/flows/leafcutter/flow-render-pipeline?step=resolve");
    expect(notFound).not.toHaveBeenCalled();
    const open = drawers();
    expect(open).toHaveLength(1);
    expect(open[0].id).toBe("resolve");
    expect(open[0].label).toBe(stepLabel("leafcutter/flow-render-pipeline", "resolve"));
    expect(screen.getByRole("heading", { level: 1 }).textContent).toContain(
      "How a flow renders in the Atlas",
    );
    expect(activeOf("Source")).toBe("Real");
    expect(activeOf("Kind")).toBe("Data");
    expect(document.body.textContent).not.toContain("Step not found");
    expect(screen.queryAllByRole("navigation")).toHaveLength(0);
  });

  it("a branch id opens the branch drawer: fern-and-fig/checkout-and-pay?step=declined at Mock/User/All", async () => {
    // covers: UXP-591-2
    // angle: criterion
    await openAddress("/flows/fern-and-fig/checkout-and-pay?step=declined");
    const open = drawers();
    expect(open).toHaveLength(1);
    expect(open[0].id).toBe("declined");
    expect(open[0].label).toBe(stepLabel("fern-and-fig/checkout-and-pay", "declined"));
    expect(activeOf("Source")).toBe("Mock");
    expect(activeOf("Kind")).toBe("User");
    expect(document.body.textContent).not.toContain("Step not found");
  });

  it("the deep-linked drawer shows the same contents as the click-opened drawer", async () => {
    // covers: UXP-591-2
    // angle: seam
    const flow = flowOf("leafcutter/flow-render-pipeline");
    const names = Object.fromEntries(getFlows().map((f) => [f.id, f.name]));
    const titles = getScreenTitles();
    const view = buildStepViews(
      flow,
      (s) => (s ? titles[s] ?? null : null),
      (id) => (id ? names[id] ?? null : null),
    ).get("step:resolve")!;
    const mock = flow.mockDataRef ? mockById(flow.mockDataRef) ?? null : null;
    render(React.createElement(FlowDrawer, { step: view, mock, onClose: () => {} }));
    const expected = drawers();
    expect(expected).toHaveLength(1);
    cleanup();

    await openAddress("/flows/leafcutter/flow-render-pipeline?step=resolve");
    const got = drawers();
    expect(got).toHaveLength(1);
    expect(got[0].text).toBe(expected[0].text);
  });

  it.each(drawerRoutes.map((r) => [r.id, r]))(
    "%s: opens exactly its open_drawer at its filters and keeps its address",
    async (_id, r) => {
      // covers: UXP-591-2
      // angle: real_artifact
      window.history.pushState({}, "", r.requested_url);
      await openAddress(r.requested_url);
      expect(drawers().map((d) => d.id)).toEqual([r.open_drawer]);
      expect(activeOf("Source")).toBe(r.filters.source === "mock" ? "Mock" : "Real");
      expect(activeOf("Kind")).toBe(r.filters.kind[0].toUpperCase() + r.filters.kind.slice(1));
      expect(r.crumbs).toEqual([r.rendered_flow]);
      expect(window.location.pathname + window.location.search).toBe(r.address_bar);
    },
  );

  it("keeps the ?step= value verbatim: the address is not rewritten on load", async () => {
    // covers: UXP-591-2
    // angle: failure
    window.history.pushState({}, "", "/flows/leafcutter/flow-render-pipeline?step=resolve");
    const replaceState = vi.spyOn(window.history, "replaceState");
    const pushState = vi.spyOn(window.history, "pushState");
    await openAddress("/flows/leafcutter/flow-render-pipeline?step=resolve");
    await new Promise((r) => setTimeout(r, 0));
    expect(drawers().map((d) => d.id)).toEqual(["resolve"]);
    expect(replaceState).not.toHaveBeenCalled();
    expect(pushState).not.toHaveBeenCalled();
    expect(window.location.search).toBe("?step=resolve");
  });

  it("control: the same flow without ?step= opens no drawer, with ?step=resolve exactly one", async () => {
    // covers: UXP-591-2
    // angle: discrimination
    await openAddress("/flows/leafcutter/flow-render-pipeline");
    expect(drawers()).toHaveLength(0);
    cleanup();
    await openAddress("/flows/leafcutter/flow-render-pipeline?step=resolve");
    expect(drawers()).toHaveLength(1);
  });

  it("FlowsView opens the drawer of its step prop, on a step and on a branch", () => {
    // covers: UXP-591-2
    // angle: boundary
    const flows = getFlows();
    const mocks: Record<string, MockData | null> = {};
    for (const f of flows) mocks[f.id] = f.mockDataRef ? mockById(f.mockDataRef) ?? null : null;
    const View = FlowsView as unknown as React.ComponentType<Record<string, unknown>>;
    for (const [flowId, stepId, source, kind] of [
      ["leafcutter/flow-render-pipeline", "resolve", "real", "data"],
      ["fern-and-fig/checkout-and-pay", "declined", "mock", "user"],
    ]) {
      render(
        React.createElement(View, {
          flows,
          mocks,
          screenTitles: getScreenTitles(),
          flowId,
          crumbs: [flowId],
          filters: { source, kind, realization: "all" },
          step: stepId,
        }),
      );
      expect(drawers().map((d) => d.id)).toEqual([stepId]);
      cleanup();
    }
  });
});
