/**
 * UXP-591-1-iii - a flow address with a percent-encoded '/' or a trailing
 * slash shows 'Flow not found' (404). (Ticket names test_uxp_591_1_iii.py;
 * vitest only collects *.test.{ts,tsx}. The Playwright spec named there is
 * deferred.)
 *
 * Planned design pinned here (see -ii): middleware.ts classifies the RAW
 * request path and forwards the raw id on a request header the catch-all
 * route checks before notFound(); the route also 404s any id that is not
 * exactly two segments on its own (defence in depth); next.config.mjs sets
 * skipTrailingSlashRedirect: true and middleware re-implements the slash-less
 * 308 for every other path.
 */
import { pathToFileURL } from "node:url";
import path from "node:path";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import {
  activeButtons,
  activeOf,
  forwardedHeaders,
  runMiddleware,
  load,
  squash,
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

const PRODUCT_AND_FLOW_WORDING =
  "A flow link names a product and a flow, for example /flows/leafcutter/deliver-a-feature.";

// [requested path, raw id, params.id as Next.js would hand the page]
const BAD_ADDRESSES: Array<[string, string, string[]]> = [
  [
    "/flows/leafcutter%2Fflow-render-pipeline",
    "leafcutter%2Fflow-render-pipeline",
    ["leafcutter/flow-render-pipeline"],
  ],
  [
    "/flows/leafcutter%2fflow-render-pipeline",
    "leafcutter%2fflow-render-pipeline",
    ["leafcutter/flow-render-pipeline"],
  ],
  [
    "/flows/leafcutter/flow-render-pipeline/",
    "leafcutter/flow-render-pipeline/",
    ["leafcutter", "flow-render-pipeline"],
  ],
];

async function arrive(requestedPath: string) {
  const res = await runMiddleware(`http://localhost${requestedPath}`);
  hoisted.headers = forwardedHeaders(res);
  return res;
}

async function callPage(id: string[]) {
  const mod = await load("@/app/flows/[...id]/page");
  return mod.default({ params: { id }, searchParams: {} } as never);
}

describe("middleware classifies the raw address", () => {
  it.each(BAD_ADDRESSES)(
    "%s is passed on with its raw id and never redirected",
    async (reqPath, rawId) => {
      // covers: UXP-591-1-iii
      // angle: failure
      const res = await arrive(reqPath);
      // no redirect to the flow, no stripping of the slash, no decoding
      expect(res.status).not.toBe(308);
      expect(res.headers.get("location")).toBeNull();
      const rewrite = res.headers.get("x-middleware-rewrite");
      if (rewrite) {
        expect(rewrite).not.toMatch(/\/flows\/leafcutter\/flow-render-pipeline$/);
      }
      // the raw, still-encoded id is on a forwarded request header (or the rewrite target)
      const carried =
        Array.from(hoisted.headers.values()).includes(rawId) ||
        (rewrite !== null && rewrite.includes(rawId));
      expect(carried).toBe(true);
    },
  );

  it("keeps the slash-less 308 for /flows/ and /atlas/ (query preserved)", async () => {
    // covers: UXP-591-1-iii
    // angle: boundary
    const cases: Array<[string, string]> = [
      ["/flows/", "/flows"],
      ["/atlas/", "/atlas"],
      ["/atlas/?x=1", "/atlas?x=1"],
    ];
    for (const [from, to] of cases) {
      const res = await runMiddleware(`http://localhost${from}`);
      expect(res.status, from).toBe(308);
      const loc = new URL(res.headers.get("location")!, "http://localhost");
      expect(loc.pathname + loc.search, from).toBe(to);
    }
  });
});

describe("next.config.mjs", () => {
  it("lets the trailing slash reach middleware (skipTrailingSlashRedirect: true)", async () => {
    // covers: UXP-591-1-iii
    // angle: real_artifact
    const href = pathToFileURL(path.resolve(process.cwd(), "next.config.mjs")).href;
    const cfg = (await import(/* @vite-ignore */ href)).default;
    expect(cfg.skipTrailingSlashRedirect).toBe(true);
  });
});

describe("catch-all route + 'Flow not found' state", () => {
  it.each(BAD_ADDRESSES)(
    "%s answers 404 through middleware -> route",
    async (reqPath, _rawId, params) => {
      // covers: UXP-591-1-iii
      // angle: seam
      const { notFound } = await import("next/navigation");
      await arrive(reqPath);
      await expect(Promise.resolve().then(() => callPage(params))).rejects.toThrow(
        "NEXT_NOT_FOUND",
      );
      expect(notFound).toHaveBeenCalled();
    },
  );

  it("control: the canonical address through middleware -> route is not a 404", async () => {
    // covers: UXP-591-1-iii
    // angle: discrimination
    const { notFound } = await import("next/navigation");
    vi.mocked(notFound).mockClear();
    await arrive("/flows/leafcutter/flow-render-pipeline");
    const el = await callPage(["leafcutter", "flow-render-pipeline"]);
    expect(el).toBeTruthy();
    expect(notFound).not.toHaveBeenCalled();
  });

  it("route alone 404s a single decoded segment containing '/', with no middleware marker", async () => {
    // covers: UXP-591-1-iii
    // angle: failure
    // defence in depth: headers() carries nothing
    await expect(
      Promise.resolve().then(() => callPage(["leafcutter/flow-render-pipeline"])),
    ).rejects.toThrow("NEXT_NOT_FOUND");
  });

  it.each(BAD_ADDRESSES)(
    "%s quotes the raw id with the product-and-flow wording and an empty flow selection",
    async (reqPath, rawId) => {
      // covers: UXP-591-1-iii
      // angle: criterion
      await arrive(reqPath);
      const mod = await load("@/app/flows/[...id]/not-found");
      const el = await (mod.default as unknown as () => Promise<React.ReactElement>)();
      render(el);
      const text = squash(document.body.textContent);
      expect(text).toContain("Flow not found");
      expect(text).toContain(`No flow has the id '${rawId}'. ${PRODUCT_AND_FLOW_WORDING}`);
      expect(screen.getByRole("link", { name: "Open the Flows view" }).getAttribute("href")).toBe(
        "/flows",
      );
      expect(activeOf("Source")).toBe("Real");
      expect(activeOf("Kind")).toBe("User");
      expect(activeButtons("Flow")).toHaveLength(0);
      expect(screen.queryAllByRole("navigation")).toHaveLength(0);
      expect(screen.queryByRole("dialog")).toBeNull();
    },
  );
});
