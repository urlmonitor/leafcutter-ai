/**
 * UXP-617-1-iv - the 'I/O not yet defined' option: finds exactly the steps and
 * branches whose io_contracts declare missing_bindings. (Ticket names
 * test_uxp_617_1_iv.py; vitest only collects *.test.{ts,tsx}.)
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, screen } from "@testing-library/react";
import {
  cardOf,
  facetGroup,
  flowLinks,
  optionBox,
  renderFinderPage,
  rowsInCard,
  statusText,
} from "../helpers/flow-finder-ui";
import { flowIds, frozenIndex, rawFlowFiles, replay, run, stateOf, storeIndex } from "../helpers/flow-finder";

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

describe("io=gap replays", () => {
  it("AC-1/AC-4: io=gap -> '9 flows, 102 steps match'; actor=llm&io=gap -> '6 flows, 8 steps match'", async () => {
    // covers: UXP-617-1-iv
    // angle: real_artifact
    const gap = await replay("finder-io-gap");
    expect(gap.out.status_text).toBe("9 flows, 102 steps match");
    expect(gap.out.result_count).toEqual({ flows: 9, steps: 102 });
    expect(flowIds(gap.out)).toEqual(gap.rec.results.map((r: any) => r.flow_id));
    expect(gap.out.results.map((r) => r.matching_steps)).toEqual(
      gap.rec.results.map((r: any) => r.matching_steps),
    );
    expect(gap.out.facet_counts.io).toEqual({ gap: 9 });

    const llm = await replay("finder-io-gap-ai-agent");
    expect(llm.out.status_text).toBe("6 flows, 8 steps match");
    expect(llm.out.result_count).toEqual({ flows: 6, steps: 8 });
    expect(flowIds(llm.out)).toEqual(llm.rec.results.map((r: any) => r.flow_id));
    const author = llm.out.results
      .find((r) => r.flow_id === "leafcutter/retrieval-query-build")!
      .step_rows.find((s) => s.node_id === "author")!;
    expect(author.label).toBe("Build a candidate query");
    expect(author.href).toBe("/flows/leafcutter/retrieval-query-build?step=author");
  });

  it("AC-3: the chip reads 'I/O not yet defined' and never 'I/O: I/O not yet defined'", async () => {
    // covers: UXP-617-1-iv
    // angle: real_artifact
    for (const id of ["finder-io-gap", "finder-io-gap-ai-agent"]) {
      const { rec, out } = await replay(id);
      expect(out.applied_chips, id).toEqual(rec.applied_chips);
      const io = out.applied_chips.find((c) => c.facet === "io")!;
      expect(io.label).toBe("I/O not yet defined");
      expect(out.applied_chips.map((c) => c.label).join("|")).not.toContain("I/O: I/O");
      expect(out.clear_all_href).toBe(rec.clear_all_href);
    }
  });
});

describe("a flow's matching steps are exactly its undefined-I/O nodes", () => {
  it("AC-2: each flow's matching steps equal its io-gap nodes, none more and none fewer", async () => {
    // covers: UXP-617-1-iv
    // angle: discrimination
    const index = await frozenIndex();
    const out = await run(index, stateOf(null, { io: ["gap"] }));

    const gapOf = new Map<string, number>();
    const totalOf = new Map<string, number>();
    for (const n of index.nodes) {
      totalOf.set(n.flowId, (totalOf.get(n.flowId) ?? 0) + 1);
      if (n.ioGap === true) gapOf.set(n.flowId, (gapOf.get(n.flowId) ?? 0) + 1);
    }
    // the data tells the wrong versions apart: a flow with SOME but not all nodes undefined
    const partial = [...gapOf].filter(([id, g]) => g < totalOf.get(id)!);
    expect(partial.length).toBeGreaterThan(0);

    expect(new Set(flowIds(out))).toEqual(new Set(gapOf.keys()));
    for (const r of out.results) {
      expect(r.matching_steps, r.flow_id).toBe(gapOf.get(r.flow_id));
      for (const row of r.step_rows) {
        const node = index.nodes.find((n: any) => n.flowId === r.flow_id && n.nodeId === row.node_id);
        expect(node.ioGap, `${r.flow_id}#${row.node_id}`).toBe(true);
      }
    }
    expect(out.result_count.steps).toBe([...gapOf.values()].reduce((a, b) => a + b, 0));
    expect(out.facet_counts.io.gap).toBe(gapOf.size);
  });
});

describe("the option on the finder screen", () => {
  it("AC-1/AC-2: on the live store /flows?io=gap lists exactly the loaded nodes that declare missing_bindings", async () => {
    // covers: UXP-617-1-iv
    // angle: reachability
    await renderFinderPage({ io: "gap" });

    // expectation read straight from the stored flow files, no loader and no pinned number
    const perFlow = new Map<string, number>();
    for (const { id, doc } of rawFlowFiles()) {
      const gaps = [...(doc.steps ?? []), ...(doc.branches ?? [])].filter(
        (n: any) =>
          Array.isArray(n.io_contracts?.missing_bindings) && n.io_contracts.missing_bindings.length > 0,
      ).length;
      if (gaps > 0) perFlow.set(id, gaps);
    }
    const steps = [...perFlow.values()].reduce((a, b) => a + b, 0);
    expect(perFlow.size).toBeGreaterThan(0);

    expect(statusText()).toBe(
      `${perFlow.size} ${perFlow.size === 1 ? "flow" : "flows"}, ${steps} ${steps === 1 ? "step" : "steps"} match`,
    );
    expect(flowLinks().map((a) => a.getAttribute("href")!.replace("/flows/", "")).sort()).toEqual(
      [...perFlow.keys()].sort(),
    );
    expect(optionBox(facetGroup("I/O not yet defined"), "I/O not yet defined").checked).toBe(true);
  });

  it("AC-3/AC-5: the chip reads 'I/O not yet defined' and the 'Build a candidate query' row links /flows/leafcutter/retrieval-query-build?step=author", async () => {
    // covers: UXP-617-1-iv
    // angle: criterion
    await renderFinderPage({ actor: "llm", io: "gap" });

    expect(screen.getByRole("button", { name: "Remove filter I/O not yet defined" })).toBeTruthy();
    expect(screen.getByText("Actor: AI agent")).toBeTruthy();
    expect(document.body.textContent).not.toContain("I/O: I/O not yet defined");

    const rows = rowsInCard(cardOf("leafcutter/retrieval-query-build"));
    const author = rows.find((r) => r.text.includes("Build a candidate query"))!;
    expect(author, "the 'Build a candidate query' row").toBeTruthy();
    expect(author.link!.getAttribute("href")).toBe("/flows/leafcutter/retrieval-query-build?step=author");
    expect(author.text).toContain("AI agent");
    expect(author.text).toContain("I/O not yet defined"); // the reason it matched
  });

  it("AC-1: ticking 'I/O not yet defined' on the overview lists the gap flows and edits the address in place", async () => {
    // covers: UXP-617-1-iv
    // angle: criterion
    await renderFinderPage({});
    const replaceState = vi.spyOn(window.history, "replaceState");
    const pushState = vi.spyOn(window.history, "pushState");

    fireEvent.click(optionBox(facetGroup("I/O not yet defined"), "I/O not yet defined"));

    const live = await run(await storeIndex(), stateOf(null, { io: ["gap"] }));
    expect(statusText()).toBe(live.status_text);
    expect(screen.getByRole("button", { name: "Remove filter I/O not yet defined" })).toBeTruthy();
    const url = new URL(String(replaceState.mock.calls.at(-1)?.[2]), window.location.href);
    expect(url.pathname + url.search).toBe("/flows?io=gap");
    expect(pushState).not.toHaveBeenCalled();
  });
});
