/**
 * UXP-591-2-iii - an old /flows?flow=...&step=... link redirects permanently
 * (308) to the step address. (Ticket names a Python test file; vitest only
 * collects *.test.{ts,tsx}. The Playwright history spec is deferred.)
 *
 * The redirect is issued by middleware.ts: only on the bare /flows path, only
 * when a flow parameter is present, a pure function of the query (no flow
 * lookup), same-origin and always under /flows/.
 */
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render } from "@testing-library/react";
import {
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
const LEGACY = `${BASE}/flows?flow=leafcutter%2Fflow-render-pipeline&step=resolve`;

describe("legacy step link redirect", () => {
  it("answers 308 to /flows/leafcutter/flow-render-pipeline?step=resolve with the slash literal", async () => {
    // covers: UXP-591-2-iii
    // angle: criterion
    const r = await redirectOf(LEGACY);
    expect(r.res.status).toBe(308);
    expect(r.location).toBe(`${BASE}/flows/leafcutter/flow-render-pipeline?step=resolve`);
    expect(r.location).not.toMatch(/%2F|flow=/i);
  });

  it("control: bare /flows without a flow parameter is not redirected", async () => {
    // covers: UXP-591-2-iii
    // angle: discrimination
    const legacy = await redirectOf(LEGACY);
    expect(legacy.res.status).toBe(308);
    const bare = await redirectOf(`${BASE}/flows`);
    expect(bare.res.status).not.toBe(308);
    expect(bare.location).toBeNull();
    const stepOnly = await redirectOf(`${BASE}/flows?step=resolve`);
    expect(stepOnly.location).toBeNull();
  });

  it("fires only on the bare /flows path, not on a canonical address carrying ?flow=", async () => {
    // covers: UXP-591-2-iii
    // angle: boundary
    const legacy = await redirectOf(LEGACY);
    expect(legacy.res.status).toBe(308);
    const canonical = await redirectOf(
      `${BASE}/flows/leafcutter/flow-render-pipeline?flow=leafcutter%2Fdeliver-a-feature`,
    );
    expect(canonical.location).toBeNull();
  });

  it("carries mock=1 and every other parameter over verbatim and in order, dropping only flow", async () => {
    // covers: UXP-591-2-iii
    // angle: boundary
    const r = await redirectOf(
      `${BASE}/flows?mock=1&flow=leafcutter%2Fflow-render-pipeline&step=resolve&x=a%20b&y=2`,
    );
    expect(r.res.status).toBe(308);
    expect(r.path).toBe("/flows/leafcutter/flow-render-pipeline");
    expect(r.search).toBe("?mock=1&step=resolve&x=a%20b&y=2");
  });

  it.each([
    ["dot segments", "..%2F..%2Fatlas"],
    ["leading double slash", "%2F%2Fevil.example"],
    ["scheme", "https%3A%2F%2Fevil.example%2Fx"],
    ["single dot", "."],
    ["encoded dots", "%2e%2e%2f%2e%2e%2fatlas"],
    ["empty segments", "a%2F%2Fb"],
  ])("a hostile flow value (%s) never leaves /flows/ on this origin", async (_name, value) => {
    // covers: UXP-591-2-iii
    // angle: failure
    const r = await redirectOf(`${BASE}/flows?flow=${value}&step=resolve`);
    expect(r.res.status).toBe(308);
    expect(r.origin).toBe(BASE);
    expect(r.location!.startsWith(`${BASE}/flows/`)).toBe(true);
    expect(r.location).not.toMatch(/\/\.\.?(\/|$|\?)/);
    expect(r.path!.startsWith("/flows/")).toBe(true);
  });

  it("the 308 location opens the flow with the resolve drawer through the catch-all route", async () => {
    // covers: UXP-591-2-iii
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
    expect(drawers().map((d) => d.id)).toEqual(["resolve"]);
    expect(document.body.textContent).not.toContain("Flow not found");
  });

  it("is permanent: the status is exactly 308, not 301, 302 or 307", async () => {
    // covers: UXP-591-2-iii
    // angle: failure
    const r = await redirectOf(LEGACY);
    expect([301, 302, 307]).not.toContain(r.res.status);
    expect(r.res.status).toBe(308);
  });
});
