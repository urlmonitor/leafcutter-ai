/**
 * UXP-617-1-ii - results are grouped by flow: a card per flow with at most
 * three step rows (actor badge + reason), "N more step(s)", and a fixed order.
 * (Ticket names test_uxp_617_1_ii.py; vitest only collects *.test.{ts,tsx}.)
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup } from "@testing-library/react";
import { cardOf, flowLinks, renderFinderPage, rowsInCard, squash } from "../helpers/flow-finder-ui";
import {
  cards,
  flowIds,
  frozenIndex,
  replay,
  rowsOf,
  run,
  stateOf,
  storeIndex,
} from "../helpers/flow-finder";

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

describe("result cards replay the dataset", () => {
  it("AC-1..AC-4: 'selected option' + Person: card order, three rows with Person badges and reasons, '1 more step'", async () => {
    // covers: UXP-617-1-ii
    // angle: real_artifact
    const { rec, out } = await replay("finder-selected-option-person");

    expect(flowIds(out)).toEqual([
      "leafcutter/decision-publishing",
      "leafcutter/decision-retrieval",
    ]);
    const first = out.results[0];
    expect(first.matching_steps).toBe(4);
    expect(first.step_rows.map((r) => r.label)).toEqual([
      "Decide to publish",
      "Commit and review in git",
      "Merge to main",
    ]);
    expect(first.step_rows.map((r) => r.actor_label)).toEqual(["Person", "Person", "Person"]);
    for (const row of first.step_rows) {
      expect(row.reason).toMatch(/^(Input|Output) · Decision record › selected_option_id$/);
    }
    expect(first.more_steps).toBe(1);
    expect(out.results[1].step_rows.map((r) => r.label)).toEqual(["Reuse it, or decide anew?"]);
    expect(out.results[1].more_steps).toBe(0);

    // and the whole record, row by row
    expect(cards(out.results)).toEqual(cards(rec.results));
    expect(rowsOf(out.results)).toEqual(rowsOf(rec.results));
  });

  it("AC-2/AC-5: every row of 'selected option' carries the reason the dataset ranks first, and hrefs are step links", async () => {
    // covers: UXP-617-1-ii
    // angle: real_artifact
    const { rec, out } = await replay("finder-selected-option");

    expect(rowsOf(out.results)).toEqual(rowsOf(rec.results));
    for (const r of out.results) {
      for (const row of r.step_rows) {
        expect(row.href).toBe(`/flows/${r.flow_id}?step=${row.node_id}`);
      }
    }
  });

  it("AC-2 (reason ranking): with an AC-id search the row says which AC matched, with a screen facet it says the screen", async () => {
    // covers: UXP-617-1-ii
    // angle: real_artifact
    for (const id of ["finder-ac-prefix", "finder-order-checkout", "finder-jev-built"]) {
      const { rec, out } = await replay(id);
      expect(rowsOf(out.results), id).toEqual(rowsOf(rec.results));
    }
  });
});

describe("result cards on the finder screen", () => {
  it("AC-1..AC-4: rendered cards show the step rows, badges, reasons, '1 more step' and row hrefs of the run", async () => {
    // covers: UXP-617-1-ii
    // angle: criterion
    await renderFinderPage({ q: "selected option", actor: "human" });

    // first assertion is about the screen itself: a card per flow, as real links
    const links = flowLinks().map((a) => a.getAttribute("href"));
    expect(links.length).toBeGreaterThan(0);

    const live = await run(await storeIndex(), stateOf("selected option", { actor: ["human"] }));
    expect(links).toEqual(live.results.map((r) => `/flows/${r.flow_id}`));
    expect(live.results[0].flow_id).toBe("leafcutter/decision-publishing");

    for (const result of live.results) {
      const card = cardOf(result.flow_id);
      const rows = rowsInCard(card);
      expect(rows.map((r) => r.link!.getAttribute("href"))).toEqual(
        result.step_rows.map((r) => r.href),
      );
      expect(rows.map((r) => r.link!.textContent)).toEqual(
        result.step_rows.map((r) => expect.stringContaining(r.label)),
      );
      result.step_rows.forEach((sr, i) => {
        expect(rows[i].text).toContain("Person"); // the actor badge
        expect(rows[i].text).toContain(sr.reason);
      });
      if (result.more_steps === 1) {
        expect(squash(card.textContent)).toMatch(/1 more step$/);
      } else {
        expect(squash(card.textContent)).not.toMatch(/\bmore steps?\b/);
      }
    }
    // the first card is the 4-step flow: three rows, then '1 more step'
    expect(rowsInCard(cardOf("leafcutter/decision-publishing"))).toHaveLength(3);
    expect(squash(cardOf("leafcutter/decision-publishing").textContent)).toMatch(/1 more step$/);
  });

  it("AC-1/AC-4: reachable from the route: /flows?q=selected+option&actor=human lists Publishing the decision record first", async () => {
    // covers: UXP-617-1-ii
    // angle: reachability
    await renderFinderPage({ q: "selected option", actor: "human" });

    const hrefs = flowLinks().map((a) => a.getAttribute("href"));
    expect(hrefs.slice(0, 2)).toEqual([
      "/flows/leafcutter/decision-publishing",
      "/flows/leafcutter/decision-retrieval",
    ]);
    const first = rowsInCard(cardOf("leafcutter/decision-publishing"));
    expect(first.map((r) => r.link!.textContent)).toEqual([
      expect.stringContaining("Decide to publish"),
      expect.stringContaining("Commit and review in git"),
      expect.stringContaining("Merge to main"),
    ]);
    expect(rowsInCard(cardOf("leafcutter/decision-retrieval")).map((r) => r.link!.textContent)).toEqual([
      expect.stringContaining("Reuse it, or decide anew?"),
    ]);
  });
});

describe("row cap and ordering rules", () => {
  it("AC-5: no card shows more than three rows, steps come before branches, and more_steps is the rest", async () => {
    // covers: UXP-617-1-ii
    // angle: boundary
    const index = await frozenIndex();
    const out = await run(index, stateOf(null, { io: ["gap"] }));

    // independent expectation from the index's own nodes: matching = io-gap nodes
    const nodesOf = (flowId: string) =>
      index.nodes.filter((n: any) => n.flowId === flowId && n.ioGap === true);
    let bothKinds = 0; // flows whose full matching list holds steps AND branches
    let branchOnlyShown = 0; // flows with no matching step: a branch row still shows
    let cappedFlows = 0;
    for (const r of out.results) {
      const matching = nodesOf(r.flow_id);
      const steps = matching
        .filter((n: any) => n.nodeKind === "step")
        .sort((a: any, b: any) => a.order - b.order);
      const branches = matching.filter((n: any) => n.nodeKind === "branch"); // stored order
      const expectedRows = [...steps, ...branches].slice(0, 3).map((n: any) => n.nodeId);

      expect(r.matching_steps, r.flow_id).toBe(matching.length);
      expect(r.step_rows.length, r.flow_id).toBeLessThanOrEqual(3);
      expect(r.step_rows.map((s) => s.node_id), r.flow_id).toEqual(expectedRows);
      expect(r.more_steps, r.flow_id).toBe(matching.length - expectedRows.length);

      // steps before branches in what is shown
      const kinds = r.step_rows.map((s) => s.node_kind);
      expect(kinds, r.flow_id).toEqual([...kinds].sort((a, b) => (a === b ? 0 : a === "step" ? -1 : 1)));

      if (steps.length > 0 && branches.length > 0) bothKinds++;
      if (steps.length === 0 && branches.length > 0 && kinds.join() === "branch") branchOnlyShown++;
      if (matching.length > 3) cappedFlows++;
    }
    // non-vacuity: the data must contain a capped flow, flows that match both steps and
    // branches (ordering is then checked on the full matching list above), and a branch-only flow
    expect(cappedFlows).toBeGreaterThan(0);
    expect(bothKinds).toBeGreaterThan(0);
    expect(branchOnlyShown).toBeGreaterThan(0);
  });

  it("AC-6: with a search, a flow whose own name matches is listed before flows with more matching steps, then by steps, then by name", async () => {
    // covers: UXP-617-1-ii
    // angle: discrimination
    const index = await frozenIndex();
    const words = new Set<string>();
    for (const f of index.flows) {
      for (const w of String(f.name).toLowerCase().match(/[\p{L}\p{N}]+/gu) ?? []) {
        if (w.length > 3) words.add(w);
      }
    }

    // find a search where a name-matching flow has FEWER matching steps than a flow that does not match by name
    let witness: string | null = null;
    for (const q of words) {
      const out = await run(index, stateOf(q));
      const named = out.results.filter((r) => r.flow_match !== null);
      const plain = out.results.filter((r) => r.flow_match === null);
      if (named.some((n) => plain.some((p) => p.matching_steps > n.matching_steps))) {
        witness = q;
        break;
      }
    }
    expect(witness, "the index holds a search whose name match has fewer steps than another flow").not.toBeNull();

    const out = await run(index, stateOf(witness));
    const keyed = out.results.map((r) => ({
      id: r.flow_id,
      own: r.flow_match !== null ? 0 : 1,
      steps: r.matching_steps,
      name: r.flow_name.toLowerCase(),
    }));
    const expected = [...keyed].sort(
      (a, b) =>
        a.own - b.own || b.steps - a.steps || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0),
    );
    expect(keyed.map((k) => k.id)).toEqual(expected.map((k) => k.id));
    // a name match is flagged 'Name' (or 'Entity · <name>')
    for (const r of out.results.filter((x) => x.flow_match !== null)) {
      expect(r.flow_match).toMatch(/^(Name|Entity · .+)$/);
    }
  });
});
