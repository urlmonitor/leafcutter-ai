/**
 * Shared helpers for the UXP-617-3 tests (step and branch cards). Not a test
 * file (no .test suffix); vitest does not collect it.
 *
 * The card contract pinned here (UXP-617-3 criteria):
 *  - a step card's accessible name is 'Step <order> of <step count>: <label> (<actor>)';
 *  - a branch card's is 'Branch: <label> (<actor>)';
 *  - a node with no stored actor has the same name without the ' (<actor>)' part;
 *  - the actor shows as a badge inside the card, in the four words Code,
 *    AI agent, Person, Jev (Jev is never shown as AI agent).
 * The expected names are derived here from the loaded flow, independently of any
 * production function, so a wrong production formula cannot agree with itself.
 */
import { expect } from "vitest";
import { screen } from "@testing-library/react";
import { getFlows } from "@/lib/data/flows";

export const ACTOR_WORD: Record<string, string> = {
  deterministic: "Code",
  llm: "AI agent",
  human: "Person",
  jev: "Jev",
};

export type CardNode = {
  flowId: string;
  nodeId: string;
  kind: "step" | "branch";
  label: string;
  actorKind: string | null;
  name: string;
  badge: string | null;
};

/** Every step and branch of a loaded flow with the card name the criteria give it. */
export function cardsOf(flowId: string, flows = getFlows()): CardNode[] {
  const flow = flows.find((f) => f.id === flowId)!;
  const count = flow.steps.length;
  const make = (n: any, kind: "step" | "branch"): CardNode => {
    const badge = n.actorKind ? ACTOR_WORD[n.actorKind] : null;
    const head = kind === "step" ? `Step ${n.order} of ${count}: ${n.label}` : `Branch: ${n.label}`;
    return {
      flowId,
      nodeId: n.id,
      kind,
      label: n.label,
      actorKind: n.actorKind ?? null,
      name: badge ? `${head} (${badge})` : head,
      badge,
    };
  };
  return [...flow.steps.map((s) => make(s, "step")), ...flow.branches.map((b) => make(b, "branch"))];
}

/** The one element that carries this accessible name. */
export function cardByName(name: string): HTMLElement {
  const found = screen.queryAllByLabelText(name);
  expect(found, `exactly one card named "${name}"`).toHaveLength(1);
  return found[0];
}

/** True when a leaf element inside the card reads exactly the badge word. */
export function hasBadge(card: HTMLElement, word: string): boolean {
  return Array.from(card.querySelectorAll("*")).some(
    (e) => e.children.length === 0 && (e.textContent ?? "").trim() === word,
  );
}
