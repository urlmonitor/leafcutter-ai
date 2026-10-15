/**
 * UXP-617-1 - the bare /flows address opens the finder overview with every
 * flow listed and counted filters. (Ticket names test_uxp_617_1.py; vitest
 * only collects *.test.{ts,tsx}.)
 *
 * Planned design pinned here (see helpers/flow-finder.ts for the core
 * contract and helpers/flow-finder-ui.ts for the DOM contract):
 *  - lib/flow-finder/ holds buildFinderIndex() and runFinder(), pure.
 *  - app/flows/page.tsx renders the finder (server HTML included) instead of
 *    the default entry flow.
 *  - fixtures/flow-finder/ holds the frozen measurement-commit index the
 *    dataset's FlowFinderQuery numbers replay against.
 */
import fs from "node:fs";
import path from "node:path";
import { renderToString } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen } from "@testing-library/react";
import {
  FIXTURE_DIR,
  FACETS,
  cards,
  finderRecord,
  flowIds,
  frozenIndex,
  replay,
  run,
  stateOf,
  storeIndex,
} from "../helpers/flow-finder";
import {
  facetGroup,
  flowLinks,
  optionBox,
  optionCount,
  pageElement,
  renderFinderPage,
  searchBox,
  stubBrowserGlobals,
  statusRegion,
  statusText,
} from "../helpers/flow-finder-ui";

const hoisted = vi.hoisted(() => ({ routerPush: vi.fn(), routerReplace: vi.fn() }));

vi.mock("server-only", () => ({}));
vi.mock("next/navigation", () => ({
  notFound: vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
  useRouter: () => ({ push: hoisted.routerPush, replace: hoisted.routerReplace }),
  usePathname: () => "/flows",
  useSearchParams: () => new URLSearchParams(window.location.search),
}));

import { getFlows } from "@/lib/data/flows";

// first render of the page pulls in the whole component tree; allow for a cold transform
vi.setConfig({ testTimeout: 180000 });

beforeEach(() => {
  hoisted.routerPush.mockClear();
  hoisted.routerReplace.mockClear();
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

// Product order of the overview: Leafcutter first, then Fern & Fig; flows by name, case ignored.
const PRODUCT_ORDER = ["leafcutter", "fern-and-fig"];
function overviewOrder(flows: Array<{ id: string; name: string; product?: string }>) {
  const productOf = (f: { id: string; product?: string }) => f.product ?? f.id.split("/")[0];
  return [...flows]
    .sort((a, b) => {
      const pa = PRODUCT_ORDER.indexOf(productOf(a));
      const pb = PRODUCT_ORDER.indexOf(productOf(b));
      if (pa !== pb) return pa - pb;
      const na = a.name.toLowerCase();
      const nb = b.name.toLowerCase();
      return na < nb ? -1 : na > nb ? 1 : 0;
    })
    .map((f) => f.id);
}

describe("bare /flows is the finder overview", () => {
  it("AC-1/AC-8: serves the finder: an empty search box, the '<n> flows' summary, no flow, breadcrumb or drawer", async () => {
    // covers: UXP-617-1
    // angle: reachability
    await renderFinderPage({});

    const total = getFlows().length;
    expect(statusText()).toBe(`${total} flows`);
    expect(searchBox().value).toBe("");
    // no flow is drawn, selected, or has a drawer / breadcrumb
    expect(document.querySelector(".react-flow")).toBeNull();
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.queryByRole("navigation", { name: /breadcrumb/i })).toBeNull();
    expect(screen.getByRole("heading", { level: 1 }).textContent).not.toContain(
      "Deliver a feature end-to-end",
    );
    expect(document.body.textContent).not.toContain("Flow not found");
  });

  it("AC-1: the summary and every flow are in the server-rendered HTML, not added client-side", async () => {
    // covers: UXP-617-1
    // angle: reachability
    stubBrowserGlobals();
    const html = renderToString(await pageElement({}));

    const total = getFlows().length;
    expect(html).toMatch(/role="status"/);
    expect(html).toContain(`${total} flows`);
    for (const f of getFlows()) {
      expect(html, `server HTML lists ${f.id}`).toContain(`href="/flows/${f.id}"`);
    }
  });

  it("AC-1/AC-2: the screen lists every flow, product by product, with no selection", async () => {
    // covers: UXP-617-1
    // angle: criterion
    await renderFinderPage({});

    const region = statusRegion(); // exactly one live region
    expect(["polite", null]).toContain(region.getAttribute("aria-live"));
    expect(screen.queryAllByRole("checkbox", { checked: true })).toHaveLength(0);

    const hrefs = flowLinks().map((a) => a.getAttribute("href"));
    const expected = overviewOrder(getFlows() as any).map((id) => `/flows/${id}`);
    expect(hrefs).toEqual(expected);
  });

  it("AC-3..AC-7: the facet panel shows the dataset's counts beside every option on the overview", async () => {
    // covers: UXP-617-1
    // angle: criterion
    await renderFinderPage({});

    const rec = finderRecord("finder-overview");
    const label: Record<string, Record<string, string>> = {
      product: { leafcutter: "Leafcutter", "fern-and-fig": "Fern & Fig" },
      actor: { deterministic: "Code", llm: "AI agent", human: "Person", jev: "Jev" },
      kind: { user: "User", data: "Data", architecture: "Architecture" },
      realization: { built: "Built", spec: "Spec", mock: "Sample" },
      level: { journey: "Journey", pipeline: "Pipeline", agent: "Agent" },
      io: { gap: "I/O not yet defined" },
    };
    const group: Record<string, string> = {
      product: "Product",
      actor: "Actor",
      kind: "Kind",
      realization: "Realization",
      level: "Level",
      io: "I/O not yet defined",
    };
    for (const facet of Object.keys(label)) {
      for (const [value, text] of Object.entries(label[facet])) {
        const box = optionBox(facetGroup(group[facet]), text);
        expect(box.checked).toBe(false);
        // the dataset's number for the overview; the measured flow set is the same
        // as today's for these flow-level facets
        expect(optionCount(box), `${facet} ${value}`).toBe(rec.facet_counts[facet][value]);
      }
    }
  });
});

describe("finder-overview replay over the frozen index", () => {
  it("AC-1/AC-2: status_text, result order and card fields match the finder-overview record", async () => {
    // covers: UXP-617-1
    // angle: real_artifact
    const { rec, out } = await replay("finder-overview");

    expect(out.status_text).toBe("28 flows");
    expect(out.status_text).toBe(rec.status_text);
    expect(out.result_count).toEqual(rec.result_count);
    expect(out.applied_chips).toEqual([]);
    expect(out.clear_all_href).toBeNull();
    expect(out.empty_state).toBeNull();
    // all 28 flows, Leafcutter first then Fern & Fig, name order ignoring case
    expect(flowIds(out)).toEqual(rec.results.map((r: any) => r.flow_id));
    expect(overviewOrder(out.results.map((r) => ({ id: r.flow_id, name: r.flow_name })))).toEqual(
      flowIds(out),
    );
    expect(cards(out.results)).toEqual(cards(rec.results));
  });

  it("AC-3..AC-6: Product, Actor, Kind, Realization, Level and I/O counts equal the record's", async () => {
    // covers: UXP-617-1
    // angle: real_artifact
    const { rec, out } = await replay("finder-overview");

    for (const facet of ["product", "actor", "kind", "realization", "level", "io"]) {
      expect(out.facet_counts[facet], facet).toEqual(rec.facet_counts[facet]);
    }
    expect(out.facet_counts.actor).toEqual({ deterministic: 23, llm: 17, human: 12, jev: 8 });
    expect(out.facet_counts.io).toEqual({ gap: 9 });
  });

  it("AC-3..AC-6: Entity and Screen options and counts equal the record's, and no field facet lists an option yet", async () => {
    // covers: UXP-617-1
    // angle: real_artifact
    const { rec, out } = await replay("finder-overview");

    expect(out.facet_counts.entity).toEqual(rec.facet_counts.entity);
    expect(out.facet_counts.screen).toEqual(rec.facet_counts.screen);
    // uses / produces are picked by type-ahead: nothing is listed until a field is chosen
    expect(out.facet_counts.uses).toEqual({});
    expect(out.facet_counts.produces).toEqual({});
  });

  it("AC-3: the frozen fixture is the measurement-commit index: provenance, 28 flows, 306 steps and branches, 102 with undefined I/O", async () => {
    // covers: UXP-617-1
    // angle: real_artifact
    expect(fs.existsSync(FIXTURE_DIR), "fixtures/flow-finder/ exists").toBe(true);
    const files = fs.readdirSync(FIXTURE_DIR).filter((n) => n.endsWith(".json"));
    expect(files.length).toBeGreaterThan(0);

    const parsed = JSON.parse(fs.readFileSync(path.join(FIXTURE_DIR, files[0]), "utf8"));
    expect(parsed.provenance, "the fixture records its provenance").toBeTruthy();
    const index = parsed.index ?? parsed;
    expect(index.flows).toHaveLength(28);
    expect(index.nodes).toHaveLength(306);
    expect(index.nodes.filter((n: any) => n.ioGap === true)).toHaveLength(102);
    expect(new Set(index.nodes.filter((n: any) => n.ioGap).map((n: any) => n.flowId)).size).toBe(9);
  });
});

describe("overview counts are flow counts", () => {
  it("every count equals the flows listed with that option alone, never a step count, and Jev is its own value", async () => {
    // covers: UXP-617-1
    // angle: discrimination
    const index = await frozenIndex();
    const overview = await run(index, stateOf(null));

    // independent derivation from the index's own nodes
    const flowsWithActor = (kind: string) =>
      new Set(index.nodes.filter((n: any) => n.actorKind === kind).map((n: any) => n.flowId));
    const nodesWithActor = (kind: string) =>
      index.nodes.filter((n: any) => n.actorKind === kind).length;

    for (const kind of ["deterministic", "llm", "human", "jev"]) {
      expect(overview.facet_counts.actor[kind], `actor ${kind}`).toBe(flowsWithActor(kind).size);
    }
    // a step-summing implementation would equal the node count: make sure the data tells them apart
    expect(nodesWithActor("llm")).toBeGreaterThan(flowsWithActor("llm").size);
    expect(overview.facet_counts.actor.llm).not.toBe(nodesWithActor("llm"));
    // Jev nodes are never folded into the AI-agent count
    expect(overview.facet_counts.actor.jev).toBeGreaterThan(0);
    expect(overview.facet_counts.actor.llm).toBe(flowsWithActor("llm").size);

    // flow facets count Flow fields
    for (const facet of ["product", "kind", "realization", "level"] as const) {
      for (const [value, n] of Object.entries(overview.facet_counts[facet])) {
        expect(
          index.flows.filter((f: any) => f[facet] === value).length,
          `${facet} ${value}`,
        ).toBe(n);
      }
    }

    // and each count is exactly what choosing that option alone lists
    for (const facet of FACETS) {
      for (const [value, n] of Object.entries(overview.facet_counts[facet])) {
        const alone = await run(index, stateOf(null, { [facet]: [value] }));
        expect(alone.result_count.flows, `${facet}=${value}`).toBe(n);
      }
    }
  });
});

describe("the finder reads the same flows the Flows view loads", () => {
  it("AC-2: an index built from the loaded flow store lists every loaded flow once", async () => {
    // covers: UXP-617-1
    // angle: seam
    const index = await storeIndex();
    const out = await run(index, stateOf(null));

    const loaded = getFlows().map((f) => f.id);
    expect([...flowIds(out)].sort()).toEqual([...loaded].sort());
    expect(out.status_text).toBe(`${loaded.length} flows`);
    expect(flowIds(out)).toEqual(overviewOrder(getFlows() as any));
  });
});
