/**
 * UXP-617-1-i - search: one box over flow names, step labels and text, field
 * names, AC ids, entities and screens; every typed word must start a word of
 * ONE single target of a step. (Ticket names test_uxp_617_1_i.py; vitest only
 * collects *.test.{ts,tsx}.)
 */
import { renderToString } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent } from "@testing-library/react";
import { coreFn, flowIds, frozenIndex, replay, run, stateOf, storeIndex } from "../helpers/flow-finder";
import {
  cardOf,
  pageElement,
  renderFinderPage,
  searchBox,
  statusRegion,
  statusText,
  stubBrowserGlobals,
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

const SUMMARY = /^\d+ flows?, \d+ steps? match$/;

describe("search replays", () => {
  it("AC-1/AC-2: 'selected option' -> '5 flows, 27 steps match' with the five flows in record order and their matching step counts", async () => {
    // covers: UXP-617-1-i
    // angle: real_artifact
    const { rec, out } = await replay("finder-selected-option");

    expect(out.status_text).toBe("5 flows, 27 steps match");
    expect(out.result_count).toEqual({ flows: 5, steps: 27 });
    expect(flowIds(out)).toEqual([
      "leafcutter/decision-publishing",
      "leafcutter/decision-retrieval",
      "leafcutter/decision-forming",
      "leafcutter/decision-staging",
      "leafcutter/decision-lifecycle",
    ]);
    expect(out.results.map((r) => r.matching_steps)).toEqual([7, 6, 5, 5, 4]);
    expect(out.results.map((r) => r.flow_name)).toEqual(rec.results.map((r: any) => r.flow_name));
    expect(flowIds(out)).toEqual(rec.results.map((r: any) => r.flow_id));
  });

  it("AC-3: 'Selected Option' returns the same flows and steps as 'selected option'", async () => {
    // covers: UXP-617-1-i
    // angle: criterion
    const index = await frozenIndex();
    const lower = await run(index, stateOf("selected option"));
    const mixed = await run(index, stateOf("Selected Option"));
    const upper = await run(index, stateOf("SELECTED OPTION"));

    expect(lower.status_text).toBe("5 flows, 27 steps match"); // control: not an empty-equals-empty pass
    expect(mixed).toEqual(lower);
    expect(upper).toEqual(lower);
  });

  it("AC-7: 'UXP-210d' lists 2 flows with 8 matching steps, found by their AC ids", async () => {
    // covers: UXP-617-1-i
    // angle: real_artifact
    const { rec, out } = await replay("finder-ac-prefix");

    expect(out.status_text).toBe("2 flows, 8 steps match");
    expect(flowIds(out)).toEqual([
      "fern-and-fig/checkout-and-pay",
      "fern-and-fig/customer-buys-a-plant",
    ]);
    expect(out.results.map((r) => r.matching_steps)).toEqual([5, 3]);
    expect(flowIds(out)).toEqual(rec.results.map((r: any) => r.flow_id));
    expect(out.results.flatMap((r) => r.step_rows.map((s) => s.reason))).toEqual(
      rec.results.flatMap((r: any) => r.step_rows.map((s: any) => s.reason)),
    );
  });
});

describe("one single target, words split at non-alphanumerics", () => {
  it("AC-4/AC-6: a node with 'selected' only in its label and 'option' only in its text does not match", async () => {
    // covers: UXP-617-1-i
    // angle: discrimination
    // Built from a real loaded flow whose steps are replaced by four probe steps, so the
    // two-target node is real producer input and only the matching rule can decide.
    const buildFinderIndex = await coreFn("buildFinderIndex");
    const base = getFlows().find((f) => f.id === "leafcutter/decision-publishing")!;
    const probe = (id: string, label: string, description: string, order: number) => ({
      ...base.steps[0],
      id,
      label,
      description,
      order,
      screen: null,
      agent: null,
      produces: [],
      consumes: [],
      ioContracts: undefined,
      reads: [],
      writes: [],
      implements: [],
      acs: [],
      expandsTo: null,
    });
    const flow = {
      ...base,
      id: "leafcutter/zebra-probe",
      name: "Zebra probe",
      entities: [],
      mockDataRef: null,
      steps: [
        // label has 'selected', only the text has 'option'  -> must NOT match
        probe("split", "Selected winner", "Choose the option", 1),
        // 'selected' occurs inside a word but starts none -> must NOT match
        probe("inside", "Unselected options", "Nothing here", 2),
        // control rows: one target carries both words, as whole word and as a prefix
        probe("both", "Selected option", "Nothing here", 3),
        probe("prefix", "Selected options listed", "Nothing here", 4),
      ],
      branches: [],
    };
    const index = buildFinderIndex([flow]);
    const out = await run(index, stateOf("selected option"));

    expect(out.result_count).toEqual({ flows: 1, steps: 2 });
    expect(out.results[0].matching_steps).toBe(2);
    expect(out.results[0].step_rows.map((r) => r.node_id)).toEqual(["both", "prefix"]);
  });

  it("AC-5: words split at every non-letter, non-digit character: field keys, kebab-case and AC ids", async () => {
    // covers: UXP-617-1-i
    // angle: boundary
    const index = await frozenIndex();
    const status = async (q: string | null) => (await run(index, stateOf(q))).status_text;

    const base = await status("selected option");
    expect(base).toBe("5 flows, 27 steps match");
    // snake_case and dotted keys split, so these all reach decision_record.selected_option_id
    expect(await status("selected_option")).toBe(base);
    expect(await status("selected-option")).toBe(base);
    expect(await status("selected.option")).toBe(base);
    expect(await status("selected_option_id")).toMatch(SUMMARY);
    expect(await status("record selected option id")).toMatch(SUMMARY);
    // an AC id splits at its hyphen
    const ac = await status("UXP-210d");
    expect(ac).toBe("2 flows, 8 steps match");
    expect(await status("uxp 210d")).toBe(ac);
    expect(await status("uxp_210d")).toBe(ac);
    // surrounding and repeated whitespace is trimmed away; an empty search is the overview
    expect(await status("  selected    option  ")).toBe(base);
    expect(await status("   ")).toBe(`${index.flows.length} flows`);
    expect(await status("")).toBe(`${index.flows.length} flows`);
    expect(await status(null)).toBe(`${index.flows.length} flows`);
  });
});

describe("the search box on the finder screen", () => {
  it("AC-8: typing updates the one polite live region in place with the new summary, with no server request", async () => {
    // covers: UXP-617-1-i
    // angle: criterion
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    await renderFinderPage({});

    const region = statusRegion();
    const before = region.textContent;
    fireEvent.change(searchBox(), { target: { value: "selected option" } });

    // same element, still in the document: updated in place, not re-created
    expect(statusRegion()).toBe(region);
    expect(region.isConnected).toBe(true);
    expect(["polite", null]).toContain(region.getAttribute("aria-live"));
    expect(region.textContent).not.toBe(before);
    expect(statusText()).toMatch(SUMMARY);

    // the shown summary is exactly what the core says for the typed text
    const live = await run(await liveIndex(), stateOf("selected option"));
    expect(statusText()).toBe(live.status_text);
    for (const id of flowIds(live)) expect(cardOf(id)).toBeTruthy();

    fireEvent.change(searchBox(), { target: { value: "Selected Option" } });
    expect(statusText()).toBe(live.status_text);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("AC-1/AC-8: reachable from the route: /flows?q=selected+option shows the summary and the matching flows, in the server HTML too", async () => {
    // covers: UXP-617-1-i
    // angle: reachability
    await renderFinderPage({ q: "selected option" });

    expect(searchBox().value).toBe("selected option");
    const shown = statusText();
    expect(shown).toMatch(SUMMARY);

    const live = await run(await liveIndex(), stateOf("selected option"));
    expect(shown).toBe(live.status_text);
    expect(flowIds(live).length).toBeGreaterThan(0);
    for (const id of flowIds(live)) expect(cardOf(id)).toBeTruthy();

    cleanup();
    stubBrowserGlobals();
    const html = renderToString(await pageElement({ q: "selected option" }));
    expect(html).toContain(live.status_text);
  });
});

const liveIndex = () => storeIndex();
