/**
 * UXP-617-3 - every step and branch card carries an actor badge (Code, AI
 * agent, Person, Jev) and an accessible name that includes its position and
 * actor. (Ticket names test_uxp_617_3.py; vitest only collects *.test.{ts,tsx}.)
 */
import React from "react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render } from "@testing-library/react";
import { cardByName, cardsOf, hasBadge } from "../helpers/flow-cards";
import { openTab, type NavState } from "../helpers/flow-history-nav";
import { core, dataset } from "../helpers/flow-finder";

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

import { getFlows, getScreenTitles, mockById } from "@/lib/data/flows";
import { FlowsView } from "@/components/flows/flows-view";
import type { MockData } from "@/lib/data/types";

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
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const RETR = "leafcutter/decision-retrieval";

function mountView(flows: ReturnType<typeof getFlows>, flowId: string) {
  const mocks: Record<string, MockData | null> = {};
  for (const f of flows) mocks[f.id] = f.mockDataRef ? mockById(f.mockDataRef) ?? null : null;
  const f = flows.find((x) => x.id === flowId)!;
  const View = FlowsView as unknown as React.ComponentType<Record<string, unknown>>;
  return render(
    <View
      flows={flows}
      mocks={mocks}
      screenTitles={getScreenTitles()}
      flowId={flowId}
      crumbs={[flowId]}
      filters={{ source: f.source, kind: f.kind, realization: "all" }}
      step={null}
    />,
  );
}

describe("actor badges and card names", () => {
  it("decision-retrieval: Jev, Person and Code badges, and the card names the criteria give", async () => {
    // covers: UXP-617-3
    // angle: criterion
    await openTab(nav, `/flows/${RETR}`);

    const step = (label: string) => cardsOf(RETR).find((c) => c.label === label)!;
    const reuse = cardByName("Step 4 of 5: Reuse it, or decide anew? (Person)");
    expect(hasBadge(reuse, "Person")).toBe(true);

    const judge = cardByName(step("Ask Jev whether each applies").name);
    expect(hasBadge(judge, "Jev")).toBe(true);
    expect(judge.textContent).not.toContain("AI agent"); // a step Jev runs is never badged AI agent

    const lookup = cardByName(step("Look up matching records").name);
    expect(hasBadge(lookup, "Code")).toBe(true);

    // a branch card's name has the form 'Branch: <label> (<actor>)'
    const branches = cardsOf(RETR).filter((c) => c.kind === "branch");
    expect(branches.length).toBeGreaterThan(0);
    for (const b of branches) {
      expect(b.name).toMatch(/^Branch: .+ \((Code|AI agent|Person|Jev)\)$/);
      expect(hasBadge(cardByName(b.name), b.badge!)).toBe(true);
    }
  });

  it("every step and branch card of a drawn flow carries a badge, branch cards included", async () => {
    // covers: UXP-617-3
    // angle: boundary
    for (const flowId of [RETR, "fern-and-fig/checkout-and-pay", "leafcutter/flow-render-pipeline"]) {
      await openTab(nav, `/flows/${flowId}`);
      const cards = cardsOf(flowId);
      expect(cards.length).toBeGreaterThan(0);
      for (const c of cards) {
        const el = cardByName(c.name);
        expect(hasBadge(el, c.badge!), `${c.name} carries its badge`).toBe(true);
      }
      cleanup();
    }
    expect(cardsOf("fern-and-fig/checkout-and-pay").some((c) => c.kind === "branch")).toBe(true);
  });

  it("a node with no stored actor gets no badge and no '(…)' in its name", () => {
    // covers: UXP-617-3
    // angle: boundary
    const flows = getFlows().map((f) =>
      f.id === RETR
        ? { ...f, steps: f.steps.map((s) => (s.id === "lookup" ? { ...s, actorKind: null } : s)) }
        : f,
    );
    mountView(flows as ReturnType<typeof getFlows>, RETR);

    const nameless = cardsOf(RETR, flows as ReturnType<typeof getFlows>).find((c) => c.nodeId === "lookup")!;
    expect(nameless.name).toBe("Step 1 of 5: Look up matching records");
    const card = cardByName(nameless.name);
    expect(card.textContent).not.toMatch(/\b(Code|AI agent|Person|Jev)\b/);
    // the neighbours keep theirs
    const other = cardsOf(RETR, flows as ReturnType<typeof getFlows>).find((c) => c.nodeId !== "lookup" && c.kind === "step")!;
    expect(hasBadge(cardByName(other.name), other.badge!)).toBe(true);
  });
});

describe("the shared actor words", () => {
  it("actorLabel maps the four stored kinds and never returns 'AI agent' for jev", async () => {
    // covers: UXP-617-3
    // angle: discrimination
    const c = await core();
    expect(typeof c.actorLabel, "lib/flow-finder exports actorLabel()").toBe("function");
    expect(c.actorLabel("deterministic")).toBe("Code");
    expect(c.actorLabel("llm")).toBe("AI agent");
    expect(c.actorLabel("human")).toBe("Person");
    expect(c.actorLabel("jev")).toBe("Jev");
    expect(c.actorLabel("jev")).not.toBe(c.actorLabel("llm"));
  });

  it.each([
    RETR,
    "leafcutter/deliver-a-feature",
    "leafcutter/flow-render-pipeline",
    "leafcutter/retrieval-query-build",
  ])("%s: every FlowNode record's card_label and actor_label are what its card shows", async (flowId) => {
    // covers: UXP-617-3
    // angle: real_artifact
    const recs = (dataset().entities.FlowNode.records as any[]).filter((r) => r.flow_id === flowId);
    expect(recs.length).toBeGreaterThan(0);
    await openTab(nav, `/flows/${flowId}`);
    for (const r of recs) {
      const card = cardByName(r.card_label);
      expect(hasBadge(card, r.actor_label), `${r.id} badge`).toBe(true);
      if (r.actor_kind === "jev") expect(card.textContent).not.toContain("AI agent");
    }
  });
});
