/**
 * UXP-591-1-ii - an unknown flow id shows 'Flow not found' (404) and never
 * falls back to another flow. (Ticket names test_uxp_591_1_ii.py; vitest only
 * collects *.test.{ts,tsx}.)
 *
 * Planned design pinned here: app/flows/[...id]/page.tsx calls notFound();
 * app/flows/[...id]/not-found.tsx (default export) renders the Flows view in
 * not-found mode, reading the raw requested id from a request header that
 * middleware.ts forwards (read via next/headers). The header NAME is not
 * pinned: the real middleware's forwarded headers are piped into the mocked
 * headers() so only the producer->consumer behaviour is asserted.
 */
import fs from "node:fs";
import path from "node:path";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import {
  activeButtons,
  activeOf,
  forwardedHeaders,
  paramsFor,
  runMiddleware,
  searchParamsOf,
  load,
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
  hoisted.headers = new Headers();
});
afterEach(cleanup);

/** Run the real middleware for the URL and expose its forwarded headers to headers(). */
async function arrive(requestedUrl: string) {
  const res = await runMiddleware(`http://localhost${requestedUrl}`);
  hoisted.headers = forwardedHeaders(res);
}

async function pageFor(requestedUrl: string) {
  const mod = await load("@/app/flows/[...id]/page");
  return mod.default({
    params: paramsFor(`http://localhost${requestedUrl}`),
    searchParams: searchParamsOf(`http://localhost${requestedUrl}`),
  } as never);
}

async function renderNotFound() {
  const mod = await load("@/app/flows/[...id]/not-found");
  const el = await (mod.default as unknown as () => Promise<React.ReactElement>)();
  return render(el);
}

const mockFile = path.resolve(
  process.cwd(),
  "../docs/product-truth/mock-data/leafcutter/atlas-flows.mock.json",
);
const notFoundRoutes = (
  JSON.parse(fs.readFileSync(mockFile, "utf8")).entities.FlowRoute.records as any[]
).filter((r) => r.resolution === "not-found");

const TWO_SEGMENT_WORDING = "The link may be mistyped, or the flow was renamed or removed.";
const PRODUCT_AND_FLOW_WORDING =
  "A flow link names a product and a flow, for example /flows/leafcutter/deliver-a-feature.";

function expectNotFoundState() {
  // selector shown at Real / User, nothing drawn, no breadcrumb, no drawer
  expect(activeOf("Source")).toBe("Real");
  expect(activeOf("Kind")).toBe("User");
  expect(activeButtons("Flow")).toHaveLength(0);
  const flowNames = getFlows().map((f) => f.name);
  for (const h of screen.queryAllByRole("heading", { level: 1 })) {
    expect(flowNames.some((n) => h.textContent!.includes(n))).toBe(false);
  }
  expect(screen.queryAllByRole("navigation")).toHaveLength(0);
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(document.body.textContent).not.toContain("Step not found");
}

describe("catch-all route answers 404 and never falls back", () => {
  it.each(notFoundRoutes.map((r) => [r.id, r.requested_url]))(
    "%s: %s calls notFound()",
    async (_id, url) => {
      // covers: UXP-591-1-ii
      // angle: reachability
      const { notFound } = await import("next/navigation");
      await arrive(url);
      await expect(Promise.resolve().then(() => pageFor(url))).rejects.toThrow(
        "NEXT_NOT_FOUND",
      );
      expect(notFound).toHaveBeenCalled();
    },
  );

  it("control: a known flow with the same shape does not call notFound()", async () => {
    // covers: UXP-591-1-ii
    // angle: discrimination
    const { notFound } = await import("next/navigation");
    vi.mocked(notFound).mockClear();
    const url = "/flows/leafcutter/flow-render-pipeline";
    await arrive(url);
    await expect(Promise.resolve().then(() => pageFor(url))).resolves.toBeTruthy();
    expect(notFound).not.toHaveBeenCalled();
  });
});

describe("'Flow not found' state", () => {
  it.each(notFoundRoutes.map((r) => [r.id, r]))(
    "%s renders the dataset's notice title, detail and action link",
    async (_id, r) => {
      // covers: UXP-591-1-ii
      // angle: real_artifact
      await arrive(r.requested_url);
      await renderNotFound();
      const text = squash(document.body.textContent);
      expect(text).toContain(r.notice.title);
      expect(text).toContain(r.notice.detail);
      const link = screen.getByRole("link", { name: r.notice.action_label });
      expect(link.getAttribute("href")).toBe(r.notice.action_href);
      expect(r.notice.action_href).toBe("/flows");
      expectNotFoundState();
    },
  );

  it("ignores ?step=resolve: no 'Step not found' and no drawer", async () => {
    // covers: UXP-591-1-ii
    // angle: boundary
    await arrive("/flows/leafcutter/flow-render-pipline?step=resolve");
    await renderNotFound();
    const text = squash(document.body.textContent);
    // the quoted id is the path only, not the query
    expect(text).toContain("No flow has the id 'leafcutter/flow-render-pipline'.");
    expect(text).not.toContain("resolve'");
    expectNotFoundState();
  });

  it("picks the wording by the shape of the id, not by comparing example ids", async () => {
    // covers: UXP-591-1-ii
    // angle: boundary
    // two-segment id never seen in the dataset -> mistyped-link wording
    await arrive("/flows/zzz/never-heard-of-it");
    await renderNotFound();
    let text = squash(document.body.textContent);
    expect(text).toContain(`No flow has the id 'zzz/never-heard-of-it'. ${TWO_SEGMENT_WORDING}`);
    expect(text).not.toContain(PRODUCT_AND_FLOW_WORDING);
    cleanup();

    // uppercase fails ^[a-z0-9-]+/[a-z0-9-]+$ -> product-and-flow wording
    await arrive("/flows/Leafcutter/Deliver-A-Feature");
    await renderNotFound();
    text = squash(document.body.textContent);
    expect(text).toContain(
      `No flow has the id 'Leafcutter/Deliver-A-Feature'. ${PRODUCT_AND_FLOW_WORDING}`,
    );
    expect(text).not.toContain(TWO_SEGMENT_WORDING);
  });

  it("renders a hostile id as text only, never as markup or a link target", async () => {
    // covers: UXP-591-1-ii
    // angle: failure
    await arrive("/flows/x/%3Cimg%20src=x%20onerror=alert(1)%3E");
    await renderNotFound();
    expect(document.querySelector("img[src='x']")).toBeNull();
    expect(screen.getByRole("link", { name: "Open the Flows view" }).getAttribute("href")).toBe(
      "/flows",
    );
  });
});
