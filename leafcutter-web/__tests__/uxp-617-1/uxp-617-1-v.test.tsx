/**
 * UXP-617-1-v - no match: the summary says "No flows match", the empty state
 * is titled for the search or the filters, and offers one way out per chosen
 * filter with the number of flows it would list. (Ticket names
 * test_uxp_617_1_v.py; vitest only collects *.test.{ts,tsx}.)
 */
import { renderToString } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, screen } from "@testing-library/react";
import {
  cardOf,
  flowLinks,
  pageElement,
  renderFinderPage,
  searchBox,
  statusText,
  stubBrowserGlobals,
} from "../helpers/flow-finder-ui";
import {
  type FacetName,
  flowIds,
  frozenIndex,
  replay,
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

describe("no-match replays and rules", () => {
  it("AC-1..AC-3: tracking + Jev: 'No flows match', the quoted title and 'Remove Actor: Jev' linking /flows?q=tracking with 3 flows", async () => {
    // covers: UXP-617-1-v
    // angle: real_artifact
    const { rec, out } = await replay("finder-no-match");

    expect(out.status_text).toBe("No flows match");
    expect(out.result_count).toEqual({ flows: 0, steps: 0 });
    expect(out.results).toEqual([]);
    expect(out.empty_state).not.toBeNull();
    expect(out.empty_state!.title).toBe("No flows match 'tracking'");
    expect(out.empty_state!.suggestions).toEqual([
      { label: "Remove Actor: Jev", href: "/flows?q=tracking", flows: 3 },
    ]);
    expect(out.empty_state).toEqual(rec.empty_state);
    expect(out.applied_chips).toEqual(rec.applied_chips);
    expect(out.clear_all_href).toBe("/flows?q=tracking");
    expect(out.facet_counts).toEqual(rec.facet_counts);
  });

  it("AC-5: with no search, a facet combination that matches nothing is titled 'No flows match these filters', one suggestion per chip", async () => {
    // covers: UXP-617-1-v
    // angle: boundary
    const index = await frozenIndex();

    // choose the combination from the index: two flow facets whose values never meet
    const values = (facet: "product" | "kind") => [...new Set(index.flows.map((f: any) => f[facet]))] as string[];
    let pair: [string, string] | null = null;
    for (const p of values("product")) {
      for (const k of values("kind")) {
        if (!index.flows.some((f: any) => f.product === p && f.kind === k)) pair = [p, k];
      }
    }
    expect(pair, "the index holds a product and a kind that no flow shares").not.toBeNull();
    const facets = { product: [pair![0]], kind: [pair![1]] };

    const out = await run(index, stateOf(null, facets));
    expect(out.status_text).toBe("No flows match");
    expect(out.results).toEqual([]);
    expect(out.empty_state!.title).toBe("No flows match these filters");
    expect(out.applied_chips).toHaveLength(2);
    expect(out.empty_state!.suggestions).toHaveLength(2);

    for (const [i, chip] of out.applied_chips.entries()) {
      const sug = out.empty_state!.suggestions[i];
      expect(sug.label).toBe(`Remove ${chip.label}`);
      expect(sug.href).toBe(chip.remove_href);
      // the suggestion's number is what that address lists
      const without: Partial<Record<FacetName, string[]>> = { ...facets };
      delete without[chip.facet as FacetName];
      const wider = await run(index, stateOf(null, without));
      expect(sug.flows, sug.label).toBe(wider.result_count.flows);
    }
    // control row: removing nothing-matching facets, the pair alone each list something
    const lone = await run(index, stateOf(null, { product: [pair![0]] }));
    expect(lone.result_count.flows).toBeGreaterThan(0);
  });

  it("AC-2: a search-only no-match is titled for the search and offers no suggestions", async () => {
    // covers: UXP-617-1-v
    // angle: boundary
    const out = await run(await frozenIndex(), stateOf("zzzzqx"));

    expect(out.status_text).toBe("No flows match");
    expect(out.empty_state!.title).toBe("No flows match 'zzzzqx'");
    expect(out.empty_state!.suggestions).toEqual([]);
    expect(out.applied_chips).toEqual([]);
    expect(out.clear_all_href).toBeNull();
    // a match is not an empty state
    const some = await run(await frozenIndex(), stateOf("tracking"));
    expect(some.empty_state).toBeNull();
    expect(some.result_count.flows).toBe(3);
  });
});

describe("the empty state on the finder screen", () => {
  it("AC-1..AC-4: following 'Remove Actor: Jev' lists the 3 flows with the search kept and adds no history entry", async () => {
    // covers: UXP-617-1-v
    // angle: seam
    await renderFinderPage({ q: "tracking", actor: "jev" });
    const replaceState = vi.spyOn(window.history, "replaceState");
    const pushState = vi.spyOn(window.history, "pushState");
    replaceState.mockClear();

    // consumer side: the empty state the core produced is what the screen shows
    expect(statusText()).toBe("No flows match");
    expect(flowLinks()).toHaveLength(0);
    expect(screen.getByText("No flows match 'tracking'")).toBeTruthy();
    const suggestion = screen.getByRole("link", { name: /^Remove Actor: Jev/ });
    expect(suggestion.getAttribute("href")).toBe("/flows?q=tracking");
    expect(suggestion.textContent).toContain("3 flows");

    const live = await run(await storeIndex(), stateOf("tracking", { actor: ["jev"] }));
    expect(live.empty_state!.suggestions[0].flows).toBe(3);

    const proceed = fireEvent.click(suggestion);
    expect(proceed, "the click edits the finder in place instead of navigating").toBe(false);

    const wider = await run(await storeIndex(), stateOf("tracking"));
    expect(statusText()).toBe(wider.status_text);
    expect(flowLinks().map((a) => a.getAttribute("href"))).toEqual(
      flowIds(wider).map((id) => `/flows/${id}`),
    );
    expect(flowLinks()).toHaveLength(3);
    expect(searchBox().value).toBe("tracking");
    expect(screen.queryByText("No flows match 'tracking'")).toBeNull();

    // replace, never push, never a router navigation
    const url = new URL(String(replaceState.mock.calls.at(-1)?.[2]), window.location.href);
    expect(url.pathname + url.search).toBe("/flows?q=tracking");
    expect(pushState).not.toHaveBeenCalled();
    expect(hoisted.routerPush).not.toHaveBeenCalled();
    expect(hoisted.routerReplace).not.toHaveBeenCalled();
  });

  it("AC-1/AC-2/AC-5: reachable from the route: /flows?q=tracking&actor=jev answers the empty state, in the server HTML too; filters alone give the filters title", async () => {
    // covers: UXP-617-1-v
    // angle: reachability
    await renderFinderPage({ q: "tracking", actor: "jev" });
    expect(statusText()).toBe("No flows match");
    expect(screen.getByText("No flows match 'tracking'")).toBeTruthy();

    cleanup();
    stubBrowserGlobals();
    const html = renderToString(await pageElement({ q: "tracking", actor: "jev" }));
    expect(html).toContain("No flows match");
    expect(html).toContain("Remove Actor: Jev");

    cleanup();
    // a filter combination that matches nothing, chosen from the index, with no search
    const index = await storeIndex();
    const kinds = [...new Set(index.flows.map((f: any) => f.kind))] as string[];
    const products = [...new Set(index.flows.map((f: any) => f.product))] as string[];
    let pair: [string, string] | null = null;
    for (const p of products) {
      for (const k of kinds) {
        if (!index.flows.some((f: any) => f.product === p && f.kind === k)) pair = [p, k];
      }
    }
    expect(pair, "the loaded flows hold a product and a kind that no flow shares").not.toBeNull();
    await renderFinderPage({ product: pair![0], kind: pair![1] });
    expect(statusText()).toBe("No flows match");
    expect(screen.getByText("No flows match these filters")).toBeTruthy();
    expect(() => cardOf("leafcutter/decision-publishing")).toThrow();
  });
});
