/**
 * UXP-617-3-ii - the tab title names what is shown: '<flow name> · Flows ·
 * Leafcutter Atlas', 'Flows · Leafcutter Atlas' for the finder and 'Flow not
 * found · Flows · Leafcutter Atlas' for an unknown id, on the server and after
 * every client navigation. (Ticket names test_uxp_617_3_ii.py; vitest only
 * collects *.test.{ts,tsx}.)
 *
 * Planned design pinned here: the page modules export Next metadata (a
 * `metadata` object or a `generateMetadata` function) whose title is the
 * string above. For an unknown flow id the title may come from either the
 * catch-all page's generateMetadata or the not-found module's metadata; the
 * test accepts either, since Next treats not-found metadata differently.
 */
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { paramsFor, searchParamsOf } from "../helpers/flow-routes";
import {
  drillNode,
  expectOnScreen,
  labelOf,
  nameOf,
  openTab,
  traverse,
  type NavState,
} from "../helpers/flow-history-nav";
import { clickNode } from "../helpers/flow-routes";
import { dataset } from "../helpers/flow-finder";

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
  useRouter: () => ({ push: nav.routerPush, replace: nav.routerReplace, refresh: vi.fn() }),
  usePathname: () => "/flows",
  useSearchParams: () => new URLSearchParams(window.location.search),
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
  nav.headers = new Headers();
  document.title = "";
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const SUFFIX = "Flows · Leafcutter Atlas";
const FINDER = SUFFIX;
const NOT_FOUND = `Flow not found · ${SUFFIX}`;
const PIPE = "leafcutter/flow-render-pipeline";
const DELIVER = "leafcutter/deliver-a-feature";
const HOW = "leafcutter/how-acs-are-built";
const PIPE_TITLE = `How a flow renders in the Atlas · ${SUFFIX}`;

/** The title a Next page module declares for these props: `metadata` or `generateMetadata`. */
async function titleOf(mod: any, props: unknown): Promise<string | undefined> {
  try {
    const meta =
      typeof mod.generateMetadata === "function"
        ? await mod.generateMetadata(props, Promise.resolve({}))
        : mod.metadata;
    const t = meta?.title;
    return typeof t === "string" ? t : t?.absolute ?? t?.default;
  } catch {
    return undefined;
  }
}

async function serverTitle(address: string): Promise<(string | undefined)[]> {
  const url = new URL(address, "http://localhost");
  const searchParams = searchParamsOf(url.href);
  if (url.pathname === "/flows") {
    return [await titleOf(await import("@/app/flows/page"), { searchParams })];
  }
  const idPage = await import("@/app/flows/[...id]/page");
  const props = { params: paramsFor(url.href), searchParams };
  return [await titleOf(idPage, props), await titleOf(await import("@/app/flows/[...id]/not-found"), {})];
}

describe("server metadata", () => {
  it("a flow address and a step address both give the flow's title; the finder gives 'Flows · Leafcutter Atlas'", async () => {
    // covers: UXP-617-3-ii
    // angle: reachability
    const idPage = await import("@/app/flows/[...id]/page");
    const params = { id: ["leafcutter", "flow-render-pipeline"] };
    expect(await titleOf(idPage, { params, searchParams: {} })).toBe(PIPE_TITLE);
    expect(await titleOf(idPage, { params, searchParams: { step: "resolve" } })).toBe(PIPE_TITLE);

    const finderPage = await import("@/app/flows/page");
    expect(await titleOf(finderPage, { searchParams: {} })).toBe(FINDER);
    expect(await titleOf(finderPage, { searchParams: { q: "selected option", actor: "human" } })).toBe(FINDER);
  });

  it("an unknown flow id gets 'Flow not found · Flows · Leafcutter Atlas' in the server output", async () => {
    // covers: UXP-617-3-ii
    // angle: failure
    const idPage = await import("@/app/flows/[...id]/page");
    const nf = await import("@/app/flows/[...id]/not-found");
    const fromPage = await titleOf(idPage, {
      params: { id: ["leafcutter", "flow-render-pipline"] },
      searchParams: {},
    });
    const fromBoundary = await titleOf(nf, {});
    // the root layout's title must not be what an unknown id keeps
    expect([fromPage, fromBoundary]).toContain(NOT_FOUND);
  });

  it("every FlowRoute and FlowNavigation page_title in atlas-flows.mock.json equals the title the page modules declare", async () => {
    // covers: UXP-617-3-ii
    // angle: real_artifact
    const d = dataset().entities;
    const records: any[] = [...d.FlowRoute.records, ...d.FlowNavigation.records];
    expect(records.length).toBeGreaterThan(60);
    const misses: string[] = [];
    for (const r of records) {
      const titles = await serverTitle(r.address_bar);
      if (!titles.includes(r.page_title)) misses.push(`${r.id}: ${r.address_bar} -> ${JSON.stringify(titles)} != ${r.page_title}`);
    }
    expect(misses).toEqual([]);
  });
});

describe("client navigation keeps the title in step", () => {
  it("drilling into Build sets the sub-flow title and Back restores 'Deliver a feature end-to-end · Flows · Leafcutter Atlas'", async () => {
    // covers: UXP-617-3-ii
    // angle: seam
    await openTab(nav, `/flows/${DELIVER}`);
    document.title = `${nameOf(DELIVER)} · ${SUFFIX}`; // what the server's metadata gave this load

    drillNode(labelOf(DELIVER, "build"));
    await expectOnScreen({ flow: HOW });
    await waitFor(() => expect(document.title).toBe(`How a ticket is built (the phase chain) · ${SUFFIX}`));

    // a drawer replace does not change it
    clickNode(labelOf(HOW, "code"));
    await expectOnScreen({ drawer: "code" });
    expect(document.title).toBe(`How a ticket is built (the phase chain) · ${SUFFIX}`);

    await traverse("back");
    await expectOnScreen({ flow: DELIVER, drawer: null });
    await waitFor(() => expect(document.title).toBe(`Deliver a feature end-to-end · ${SUFFIX}`));
    await traverse("forward");
    await expectOnScreen({ flow: HOW });
    await waitFor(() => expect(document.title).toBe(`How a ticket is built (the phase chain) · ${SUFFIX}`));
  });

  it("opening a result from the finder sets the flow's title, and Back to the finder restores 'Flows · Leafcutter Atlas'", async () => {
    // covers: UXP-617-3-ii
    // angle: seam
    await openTab(nav, "/flows?q=selected+option&actor=human");
    document.title = FINDER;

    fireEvent.click(screen.getByRole("link", { name: "Reuse it, or decide anew?" }));
    await expectOnScreen({ flow: "leafcutter/decision-retrieval", drawer: "offer-reuse" });
    await waitFor(() => expect(document.title).toBe(`${nameOf("leafcutter/decision-retrieval")} · ${SUFFIX}`));

    await traverse("back");
    await waitFor(() => expect(document.title).toBe(FINDER));
    await traverse("forward");
    await waitFor(() => expect(document.title).toBe(`${nameOf("leafcutter/decision-retrieval")} · ${SUFFIX}`));
  });
});
