/**
 * UXP-591-2-iv - an old /flows?flow=... link without &step= redirects
 * permanently to the flow's canonical address. (Ticket names a Python test
 * file; vitest only collects *.test.{ts,tsx}.)
 */
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import {
  activeOf,
  drawers,
  forwardedHeaders,
  load,
  paramsFor,
  redirectOf,
  runMiddleware,
  searchParamsOf,
} from "./helpers/flow-routes";

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
  hoisted.headers = new Headers();
});
afterEach(cleanup);

const BASE = "http://localhost";
const LEGACY = `${BASE}/flows?flow=leafcutter%2Fflow-render-pipeline`;

describe("legacy step-less link redirect", () => {
  it("answers 308 to /flows/leafcutter/flow-render-pipeline with no query at all", async () => {
    // covers: UXP-591-2-iv
    // angle: criterion
    const r = await redirectOf(LEGACY);
    expect(r.res.status).toBe(308);
    expect(r.location).toBe(`${BASE}/flows/leafcutter/flow-render-pipeline`);
    expect(r.location).not.toMatch(/\?|flow=|step=|%2F/i);
  });

  it("another known flow redirects the same way (nothing keyed on one id)", async () => {
    // covers: UXP-591-2-iv
    // angle: boundary
    const r = await redirectOf(`${BASE}/flows?flow=fern-and-fig%2Fcheckout-and-pay`);
    expect(r.res.status).toBe(308);
    expect(r.location).toBe(`${BASE}/flows/fern-and-fig/checkout-and-pay`);
  });

  it("still carries mock=1 over when it is the only other parameter", async () => {
    // covers: UXP-591-2-iv
    // angle: boundary
    const r = await redirectOf(`${LEGACY}&mock=1`);
    expect(r.res.status).toBe(308);
    expect(r.path).toBe("/flows/leafcutter/flow-render-pipeline");
    expect(r.search).toBe("?mock=1");
  });

  it("the step-less location opens the flow at Real/Data/All with a one-flow breadcrumb, no drawer and no notice", async () => {
    // covers: UXP-591-2-iv
    // angle: seam
    const r = await redirectOf(LEGACY);
    expect(r.res.status).toBe(308);
    const landing = r.location!;
    hoisted.headers = forwardedHeaders(await runMiddleware(landing));
    const mod = await load("@/app/flows/[...id]/page");
    const el = await mod.default({
      params: paramsFor(landing),
      searchParams: searchParamsOf(landing),
    });
    render(el);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toContain(
      "How a flow renders in the Atlas",
    );
    expect(activeOf("Source")).toBe("Real");
    expect(activeOf("Kind")).toBe("Data");
    expect(drawers()).toHaveLength(0);
    expect(document.body.textContent).not.toContain("Step not found");
    expect(document.body.textContent).not.toContain("Flow not found");
    expect(screen.queryAllByRole("navigation")).toHaveLength(0);
  });

  it("control: /flows with no flow parameter is not redirected to any flow", async () => {
    // covers: UXP-591-2-iv
    // angle: discrimination
    expect((await redirectOf(LEGACY)).res.status).toBe(308);
    const bare = await redirectOf(`${BASE}/flows`);
    expect(bare.location).toBeNull();
  });
});
