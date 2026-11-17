/**
 * UXP-617-1-iii - facets, chips and recounts: OR within a facet, AND across
 * facets, a flow count beside every option, removable chips and "Clear all".
 * (Ticket names test_uxp_617_1_iii.py; vitest only collects *.test.{ts,tsx}.)
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, screen, within } from "@testing-library/react";
import {
  facetGroup,
  facetPanel,
  isDisabled,
  optionBox,
  optionCount,
  renderFinderPage,
  searchBox,
  statusText,
} from "../helpers/flow-finder-ui";
import { finderRecord, flowIds, frozenIndex, replay, run, stateOf, storeIndex } from "../helpers/flow-finder";

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

const lastReplaced = (spy: ReturnType<typeof vi.spyOn>) => {
  const url = spy.mock.calls.at(-1)?.[2];
  const u = new URL(String(url), window.location.href);
  return u.pathname + u.search;
};

describe("facet replays", () => {
  it("AC-1..AC-3: ticking Person: '2 flows, 5 steps match', Actor counts Code 5 / AI agent 1 / Person 2 / Jev 0, the chip and Clear all", async () => {
    // covers: UXP-617-1-iii
    // angle: real_artifact
    const { rec, out } = await replay("finder-selected-option-person");

    expect(out.status_text).toBe("2 flows, 5 steps match");
    expect(out.facet_counts.actor).toEqual({ deterministic: 5, llm: 1, human: 2, jev: 0 });
    expect(out.applied_chips).toEqual([
      {
        facet: "actor",
        value: "human",
        label: "Actor: Person",
        remove_href: "/flows?q=selected+option",
      },
    ]);
    expect(out.clear_all_href).toBe("/flows?q=selected+option");
    expect(out.facet_counts).toEqual(rec.facet_counts);
  });

  it.each([
    "finder-produces-selected-option-pipeline",
    "finder-uses-selected-option-person",
    "finder-jev-built",
    "finder-order-checkout",
  ])("AC-2/AC-5/AC-7: %s: counts, chips in address order and Clear all equal the record", async (id) => {
    // covers: UXP-617-1-iii
    // angle: real_artifact
    const { rec, out } = await replay(id);

    expect(out.status_text).toBe(rec.status_text);
    expect(out.result_count).toEqual(rec.result_count);
    expect(flowIds(out)).toEqual(rec.results.map((r: any) => r.flow_id));
    expect(out.applied_chips).toEqual(rec.applied_chips);
    expect(out.clear_all_href).toBe(rec.clear_all_href);
    expect(out.facet_counts).toEqual(rec.facet_counts);
  });
});

describe("OR within a facet, AND across facets", () => {
  it("AC-4/AC-5: Person + Code lists the union of both actors' steps; a facet from another group narrows by AND", async () => {
    // covers: UXP-617-1-iii
    // angle: discrimination
    const index = await frozenIndex();
    const q = "selected option";
    const person = await run(index, stateOf(q, { actor: ["human"] }));
    const code = await run(index, stateOf(q, { actor: ["deterministic"] }));
    const both = await run(index, stateOf(q, { actor: ["human", "deterministic"] }));

    // OR within one facet: the two actors never share a node, so steps add up and flows union
    expect(person.result_count.steps).toBeGreaterThan(0);
    expect(code.result_count.steps).toBeGreaterThan(0);
    expect(both.result_count.steps).toBe(person.result_count.steps + code.result_count.steps);
    expect(new Set(flowIds(both))).toEqual(new Set([...flowIds(person), ...flowIds(code)]));
    expect(both.result_count.steps).toBeGreaterThan(0); // an AND would list nothing

    // AND across facets: Person AND level=journey -> the flows in both lists, exactly
    const journey = await run(index, stateOf(q, { level: ["journey"] }));
    const pipeline = await run(index, stateOf(q, { level: ["pipeline"] }));
    const personJourney = await run(index, stateOf(q, { actor: ["human"], level: ["journey"] }));
    const personPipeline = await run(index, stateOf(q, { actor: ["human"], level: ["pipeline"] }));

    const common = (a: string[], b: string[]) => a.filter((x) => b.includes(x));
    expect(journey.result_count.flows).toBeGreaterThan(0);
    expect(flowIds(personJourney)).toEqual(common(flowIds(person), flowIds(journey)));
    expect(personJourney.result_count).toEqual({ flows: 0, steps: 0 });
    // control row: a facet value that the person flows do meet keeps them, step for step
    expect(flowIds(personPipeline)).toEqual(common(flowIds(person), flowIds(pipeline)));
    expect(personPipeline.result_count).toEqual(person.result_count);
    // an OR across facets would have listed the journey flow beside the person flows
    expect(flowIds(personPipeline)).not.toContain(flowIds(journey)[0]);
  });
});

describe("the facet panel on the finder screen", () => {
  it("AC-3: the Jev option stays listed but disabled at 0, and a ticked Person gets a chip whose remove button has its full name", async () => {
    // covers: UXP-617-1-iii
    // angle: criterion
    const replaceState = vi.spyOn(window.history, "replaceState");
    const pushState = vi.spyOn(window.history, "pushState");
    await renderFinderPage({ q: "selected option" });
    replaceState.mockClear(); // drop the harness's own address setup
    pushState.mockClear();

    const actor = facetGroup("Actor");
    const jev = optionBox(actor, "Jev");
    expect(isDisabled(jev)).toBe(true);
    expect(optionCount(jev)).toBe(0);

    fireEvent.click(optionBox(actor, "Person"));

    const live = await run(await storeIndex(), stateOf("selected option", { actor: ["human"] }));
    expect(statusText()).toBe(live.status_text);
    expect(screen.getByText("Actor: Person")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Remove filter Actor: Person" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Clear all" }).getAttribute("href")).toBe(
      "/flows?q=selected+option",
    );

    // the counts beside the options are the recounts, and nothing reflowed
    const labels: Array<[string, string]> = [
      ["deterministic", "Code"],
      ["llm", "AI agent"],
      ["human", "Person"],
      ["jev", "Jev"],
    ];
    for (const [value, label] of labels) {
      const box = optionBox(facetGroup("Actor"), label);
      expect(optionCount(box), label).toBe(live.facet_counts.actor[value]);
    }
    expect(isDisabled(optionBox(facetGroup("Actor"), "Jev"))).toBe(true);
    expect(optionBox(facetGroup("Actor"), "Person").checked).toBe(true);

    // an in-place edit of the address, never a new history entry or a router navigation
    expect(lastReplaced(replaceState)).toBe(finderRecord("finder-selected-option-person").url);
    expect(pushState).not.toHaveBeenCalled();
    expect(hoisted.routerPush).not.toHaveBeenCalled();
    expect(hoisted.routerReplace).not.toHaveBeenCalled();

    // removing the chip unticks the box and restores the unfiltered recount
    fireEvent.click(screen.getByRole("button", { name: "Remove filter Actor: Person" }));
    expect(optionBox(facetGroup("Actor"), "Person").checked).toBe(false);
    expect(screen.queryByRole("button", { name: /^Remove filter / })).toBeNull();
  });

  it("AC-6: 'Clear all' removes every facet value and keeps the search 'selected option'", async () => {
    // covers: UXP-617-1-iii
    // angle: boundary
    const replaceState = vi.spyOn(window.history, "replaceState");
    await renderFinderPage({ q: "selected option" });
    replaceState.mockClear();

    fireEvent.click(optionBox(facetGroup("Actor"), "Person"));
    fireEvent.click(optionBox(facetGroup("Actor"), "Code"));
    fireEvent.click(optionBox(facetGroup("Level"), "Pipeline"));
    expect(screen.getAllByRole("button", { name: /^Remove filter / })).toHaveLength(3);

    fireEvent.click(screen.getByRole("link", { name: "Clear all" }));

    expect(screen.queryAllByRole("checkbox", { checked: true })).toHaveLength(0);
    expect(screen.queryByRole("button", { name: /^Remove filter / })).toBeNull();
    expect(screen.queryByRole("link", { name: "Clear all" })).toBeNull();
    expect(searchBox().value).toBe("selected option");
    const live = await run(await storeIndex(), stateOf("selected option"));
    expect(statusText()).toBe(live.status_text);
    expect(lastReplaced(replaceState)).toBe("/flows?q=selected+option");
  });

  it("AC-7: the panel offers the ten facets in order, with Uses and Produces field picked by typing a field name", async () => {
    // covers: UXP-617-1-iii
    // angle: criterion
    await renderFinderPage({});

    const heads = Array.from(facetPanel().querySelectorAll("legend, summary")).map((e) =>
      (e.textContent ?? "").replace(/\s+/g, " ").trim(),
    );
    const order = [
      "Product",
      "Actor",
      "Kind",
      "Realization",
      "Level",
      "Uses field",
      "Produces field",
      "I/O",
      "Entity",
      "Screen",
    ];
    expect(heads.map((h) => order.find((o) => h.startsWith(o)))).toEqual(order);

    // nothing is listed for a field facet until a field name is typed
    expect(within(facetPanel()).queryAllByRole("checkbox", { name: /selected_option_id/ })).toHaveLength(0);
    const input = within(facetPanel())
      .getAllByLabelText(/uses field/i)
      .find((e): e is HTMLInputElement => e instanceof HTMLInputElement)!;
    expect(input, "an input labelled 'Uses field'").toBeTruthy();
    fireEvent.change(input, { target: { value: "selected_option" } });

    const option = await within(facetPanel()).findByRole("checkbox", {
      name: /Decision record › selected_option_id/,
    });
    fireEvent.click(option);
    expect(screen.getByText("Uses field: Decision record › selected_option_id")).toBeTruthy();

    const live = await run(
      await storeIndex(),
      stateOf(null, { uses: ["decision_record.selected_option_id"] }),
    );
    expect(statusText()).toBe(live.status_text);

    const produces = within(facetPanel())
      .getAllByLabelText(/produces field/i)
      .find((e): e is HTMLInputElement => e instanceof HTMLInputElement)!;
    expect(produces, "an input labelled 'Produces field'").toBeTruthy();
  });

  it("AC-1..AC-3: reachable from the route: /flows?q=selected+option&actor=human opens with Person ticked, its chip and the recounts", async () => {
    // covers: UXP-617-1-iii
    // angle: reachability
    await renderFinderPage({ q: "selected option", actor: "human" });

    expect(optionBox(facetGroup("Actor"), "Person").checked).toBe(true);
    expect(screen.getByRole("button", { name: "Remove filter Actor: Person" })).toBeTruthy();
    const live = await run(await storeIndex(), stateOf("selected option", { actor: ["human"] }));
    expect(statusText()).toBe(live.status_text);
    expect(optionCount(optionBox(facetGroup("Actor"), "Code"))).toBe(live.facet_counts.actor.deterministic);
    expect(isDisabled(optionBox(facetGroup("Actor"), "Jev"))).toBe(true);
  });
});
