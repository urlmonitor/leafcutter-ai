/**
 * UXP-591-3 (and the UXP-524 gap it closes) - each 'Appears in flows' link in
 * an AC's detail drawer points at the step address of the node that implements
 * the AC: /flows/<product>/<flow>?step=<id>. (Ticket names a Python test file;
 * vitest only collects *.test.{ts,tsx}.)
 *
 * Real data: the AC comes from the AC store and the appearances from
 * flowAppearancesByAc(), the same producer app/atlas/page.tsx uses.
 */
import fs from "node:fs";
import path from "node:path";
import React from "react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, within } from "@testing-library/react";
import { drawers, forwardedHeaders, load, paramsFor, runMiddleware, searchParamsOf } from "../helpers/flow-routes";

const hoisted = vi.hoisted(() => ({ headers: new Headers() }));

vi.mock("server-only", () => ({}));
vi.mock("next/headers", () => ({ headers: () => hoisted.headers }));
vi.mock("next/navigation", () => ({
  notFound: vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
  redirect: vi.fn(),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/atlas",
  useSearchParams: () => new URLSearchParams(),
}));

import { acById } from "@/lib/data/ac-store";
import { flowAppearancesByAc } from "@/lib/data/flows";
import { DetailDrawer } from "@/components/atlas/detail-drawer";

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

/** The hrefs under 'Appears in flows' when the AC's detail is opened. */
function appearsInFlowsHrefs(acId: string): string[] {
  const ac = acById(acId);
  expect(ac, `AC ${acId} in the store`).toBeTruthy();
  const { container } = render(
    React.createElement(DetailDrawer, {
      ac: ac!,
      presentIds: new Set<string>(),
      onSelect: () => {},
      onClose: () => {},
      flowAppearances: flowAppearancesByAc()[acId] ?? [],
    }),
  );
  const matches = Array.from(container.querySelectorAll("div")).filter(
    (e) => e.textContent?.trim() === "Appears in flows",
  );
  const heading = matches[matches.length - 1];
  expect(heading, "an 'Appears in flows' section").toBeTruthy();
  const section = heading.parentElement!;
  return within(section as HTMLElement)
    .getAllByRole("link")
    .map((a) => a.getAttribute("href")!);
}

const mockFile = path.resolve(
  process.cwd(),
  "../docs/product-truth/mock-data/leafcutter/atlas-flows.mock.json",
);
const appearances = JSON.parse(fs.readFileSync(mockFile, "utf8")).entities.FlowAppearance
  .records as any[];
const byAc = new Map<string, string[]>();
for (const r of appearances) byAc.set(r.ac, [...(byAc.get(r.ac) ?? []), r.href]);

describe("'Appears in flows' links are step addresses", () => {
  it("UXP-411, UXP-210d-2 and BO-2000b link to /flows/<product>/<flow>?step=<id>, one per node", () => {
    // covers: UXP-591-3
    // covers: UXP-524
    // angle: criterion
    expect(appearsInFlowsHrefs("UXP-411")).toEqual([
      "/flows/leafcutter/flow-render-pipeline?step=resolve",
    ]);
    cleanup();
    expect(appearsInFlowsHrefs("UXP-210d-2").sort()).toEqual([
      "/flows/fern-and-fig/checkout-and-pay?step=declined",
      "/flows/fern-and-fig/customer-buys-a-plant?step=paymentFailed",
    ]);
    cleanup();
    expect(appearsInFlowsHrefs("BO-2000b").sort()).toEqual([
      "/flows/leafcutter/how-acs-are-built?step=code",
      "/flows/leafcutter/python-coder-internal?step=complexity",
      "/flows/leafcutter/python-coder-internal?step=conventions",
      "/flows/leafcutter/python-coder-internal?step=docenforce",
    ]);
  });

  it("no link uses the ?flow= form or percent-encodes the slash in a flow id", () => {
    // covers: UXP-591-3
    // covers: UXP-524
    // angle: failure
    for (const ac of ["UXP-411", "UXP-210d-2", "BO-2000b"]) {
      const hrefs = appearsInFlowsHrefs(ac);
      expect(hrefs.length).toBeGreaterThan(0);
      for (const h of hrefs) {
        expect(h).toMatch(/^\/flows\/[a-z0-9-]+\/[a-z0-9-]+\?step=[A-Za-z0-9_-]+$/);
        expect(h).not.toMatch(/\?flow=|%2F/i);
      }
      cleanup();
    }
  });

  it("every FlowAppearance record in atlas-flows.mock.json yields its href in its AC's detail", () => {
    // covers: UXP-591-3
    // covers: UXP-524
    // angle: real_artifact
    expect(byAc.size).toBeGreaterThan(0);
    for (const [ac, hrefs] of byAc) {
      expect(appearsInFlowsHrefs(ac).sort(), ac).toEqual([...hrefs].sort());
      cleanup();
    }
  });

  it("branch appearances are kept and two nodes of one flow are two links", () => {
    // covers: UXP-591-3
    // covers: UXP-524
    // angle: discrimination
    const hrefs = appearsInFlowsHrefs("BO-2000b");
    expect(hrefs).toHaveLength(4);
    expect(hrefs.filter((h) => h.startsWith("/flows/leafcutter/python-coder-internal?"))).toHaveLength(3);
    cleanup();
    expect(appearsInFlowsHrefs("UXP-210d-2").some((h) => h.endsWith("?step=declined"))).toBe(true);
  });

  it("following UXP-411's link through the catch-all route opens flow-render-pipeline with the resolve drawer", async () => {
    // covers: UXP-591-3
    // covers: UXP-524
    // angle: reachability
    const [href] = appearsInFlowsHrefs("UXP-411");
    cleanup();
    const abs = `http://localhost${href}`;
    hoisted.headers = forwardedHeaders(await runMiddleware(abs));
    const mod = await load("@/app/flows/[...id]/page");
    render(await mod.default({ params: paramsFor(abs), searchParams: searchParamsOf(abs) }));
    expect(drawers().map((d) => d.id)).toEqual(["resolve"]);
    expect(document.body.textContent).toContain("How a flow renders in the Atlas");
  });
});
