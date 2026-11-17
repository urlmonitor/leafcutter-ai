/**
 * UXP-591-2-v - an old /flows?flow=... link naming an unknown flow redirects
 * to its canonical form, which shows 'Flow not found' (404). (Ticket names a
 * Python test file; vitest only collects *.test.{ts,tsx}.)
 *
 * The middleware never checks whether the flow exists (Edge runtime): an
 * unknown id gets the same 308 as a known one; the 404 comes from the
 * catch-all route it lands on.
 */
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import {
  activeButtons,
  activeOf,
  drawers,
  forwardedHeaders,
  load,
  paramsFor,
  redirectOf,
  runMiddleware,
  searchParamsOf,
  squash,
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
afterEach(cleanup);

const BASE = "http://localhost";
const WITH_STEP = `${BASE}/flows?flow=leafcutter%2Fflow-render-pipline&step=resolve`;
const WITHOUT_STEP = `${BASE}/flows?flow=leafcutter%2Fflow-render-pipline`;

describe("legacy link naming an unknown flow", () => {
  it("gets the same 308 a known id gets, with and without &step=", async () => {
    // covers: UXP-591-2-v
    // angle: criterion
    const a = await redirectOf(WITH_STEP);
    const b = await redirectOf(WITHOUT_STEP);
    expect(a.res.status).toBe(308);
    expect(a.location).toBe(`${BASE}/flows/leafcutter/flow-render-pipline?step=resolve`);
    expect(b.res.status).toBe(308);
    expect(b.location).toBe(`${BASE}/flows/leafcutter/flow-render-pipline`);
    // never the bare Flows view
    expect(a.path).not.toBe("/flows");
    expect(b.path).not.toBe("/flows");
  });

  it.each([
    ["with step", WITH_STEP],
    ["without step", WITHOUT_STEP],
  ])("%s: the 308 location reaches notFound() and renders 'Flow not found' with nothing drawn", async (_n, legacy) => {
    // covers: UXP-591-2-v
    // angle: reachability
    const r = await redirectOf(legacy);
    expect(r.res.status).toBe(308);
    const landing = r.location!;
    hoisted.headers = forwardedHeaders(await runMiddleware(landing));

    const page = await load("@/app/flows/[...id]/page");
    await expect(
      Promise.resolve().then(() =>
        page.default({ params: paramsFor(landing), searchParams: searchParamsOf(landing) }),
      ),
    ).rejects.toThrow("NEXT_NOT_FOUND");

    const nf = await load("@/app/flows/[...id]/not-found");
    render(await nf.default());
    const text = squash(document.body.textContent);
    expect(text).toContain("Flow not found");
    expect(text).toContain("No flow has the id 'leafcutter/flow-render-pipline'.");
    expect(text).not.toContain("Step not found");
    expect(drawers()).toHaveLength(0);
    expect(activeOf("Source")).toBe("Real");
    expect(activeOf("Kind")).toBe("User");
    expect(activeButtons("Flow")).toHaveLength(0);
    expect(screen.queryAllByRole("navigation")).toHaveLength(0);
    expect(
      screen.queryAllByRole("heading", { level: 1 }).some((h) =>
        h.textContent!.includes("Deliver a feature end-to-end"),
      ),
    ).toBe(false);
  });

  it("control: a known flow id gets a landing that does not 404", async () => {
    // covers: UXP-591-2-v
    // angle: discrimination
    const r = await redirectOf(`${BASE}/flows?flow=leafcutter%2Fflow-render-pipeline&step=resolve`);
    expect(r.res.status).toBe(308);
    const landing = r.location!;
    hoisted.headers = forwardedHeaders(await runMiddleware(landing));
    const page = await load("@/app/flows/[...id]/page");
    const { notFound } = await import("next/navigation");
    vi.mocked(notFound).mockClear();
    render(await page.default({ params: paramsFor(landing), searchParams: searchParamsOf(landing) }));
    expect(notFound).not.toHaveBeenCalled();
  });
});
