/**
 * The ONE listing function (UXP-617-1-iii): which flows a finder state lists, with
 * their matching steps and the order. Facet counts and empty-state suggestions
 * call it again with a changed state, so there is no second counting rule.
 *
 * Facets combine with OR within a facet and AND across facets. Product, kind,
 * realization, level and entity are flow facets; actor, uses, produces, io and
 * screen are step facets that one node must meet all at once. A flow is listed
 * when it meets every flow facet and either nothing else is asked, or one of its
 * nodes meets every step facet and q, or q matches the flow's own targets and
 * (no step facet is chosen or one of its nodes meets them all).
 */
import { ACTOR_KIND_LABEL } from "@/lib/data/actor-kind";
import { facetDef, optionLabel } from "./facets";
import { flowMatch, nodeMatch, wordsOf } from "./search";
import type { FinderFacets, FinderFlow, FinderIndex, FinderNode, FinderState } from "./types";

export interface MatchedNode {
  node: FinderNode;
  reason: string;
}

export interface Listed {
  flow: FinderFlow;
  flowMatch: string | null;
  matches: MatchedNode[];
}

const chosen = (facets: FinderFacets, name: keyof FinderFacets) => facets[name].length > 0;
const hasStepFacet = (f: FinderFacets) =>
  chosen(f, "actor") || chosen(f, "uses") || chosen(f, "produces") || chosen(f, "io") || chosen(f, "screen");

function meetsFlowFacets(flow: FinderFlow, f: FinderFacets): boolean {
  return (
    (!chosen(f, "product") || f.product.includes(flow.product)) &&
    (!chosen(f, "kind") || f.kind.includes(flow.kind)) &&
    (!chosen(f, "realization") || f.realization.includes(flow.realization)) &&
    (!chosen(f, "level") || f.level.includes(flow.level)) &&
    (!chosen(f, "entity") || flow.entities.some((e) => f.entity.includes(e)))
  );
}

function meetsStepFacets(node: FinderNode, f: FinderFacets): boolean {
  return (
    (!chosen(f, "actor") || (node.actorKind !== null && f.actor.includes(node.actorKind))) &&
    (!chosen(f, "uses") || node.uses.some((k) => f.uses.includes(k))) &&
    (!chosen(f, "produces") || node.produces.some((k) => f.produces.includes(k))) &&
    (!chosen(f, "io") || (f.io.includes("gap") && node.ioGap)) &&
    (!chosen(f, "screen") || (node.screen !== null && f.screen.includes(node.screen.id)))
  );
}

/** Without a search, a row names the chosen step facet the node meets (produces, uses, io, screen, actor). */
function facetReason(index: FinderIndex, node: FinderNode, f: FinderFacets): string {
  const out = node.produces.find((k) => f.produces.includes(k));
  if (out) return `Output · ${optionLabel(index, "produces", out)}`;
  const inp = node.uses.find((k) => f.uses.includes(k));
  if (inp) return `Input · ${optionLabel(index, "uses", inp)}`;
  if (chosen(f, "io")) return optionLabel(index, "io", "gap");
  if (node.screen && chosen(f, "screen")) return `Screen · ${node.screen.title}`;
  return node.actorKind ? ACTOR_KIND_LABEL[node.actorKind] : "";
}

const byFlow = new WeakMap<FinderIndex, Map<string, FinderNode[]>>();

/** Each flow's nodes: steps in step order, then branches in stored order. */
function nodesByFlow(index: FinderIndex): Map<string, FinderNode[]> {
  const hit = byFlow.get(index);
  if (hit) return hit;
  const map = new Map<string, FinderNode[]>();
  for (const n of index.nodes) {
    const list = map.get(n.flowId) ?? [];
    list.push(n);
    map.set(n.flowId, list);
  }
  for (const [id, list] of map) {
    const steps = list.filter((n) => n.nodeKind === "step").sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
    map.set(id, [...steps, ...list.filter((n) => n.nodeKind === "branch")]);
  }
  byFlow.set(index, map);
  return map;
}

const productRank = (p: string) => {
  const i = facetDef("product").options!.findIndex((o) => o.value === p);
  return i < 0 ? 1000 : i;
};
const lc = (s: string) => s.toLowerCase();
const cmp = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);

export function listFlows(index: FinderIndex, state: FinderState): Listed[] {
  const queryWords = state.q ? wordsOf(state.q) : [];
  const asked = queryWords.length > 0;
  const f = state.facets;
  const stepFacets = hasStepFacet(f);
  const nodes = nodesByFlow(index);
  const out: Listed[] = [];

  for (const flow of index.flows) {
    if (!meetsFlowFacets(flow, f)) continue;
    if (!asked && !stepFacets) {
      out.push({ flow, flowMatch: null, matches: [] });
      continue;
    }
    const own = asked ? flowMatch(flow, queryWords) : null;
    const mine = nodes.get(flow.id) ?? [];
    const matches: MatchedNode[] = [];
    let anyMeetsFacets = false;
    for (const node of mine) {
      if (!meetsStepFacets(node, f)) continue;
      anyMeetsFacets = true;
      if (!asked) {
        matches.push({ node, reason: facetReason(index, node, f) });
      } else {
        const reason = nodeMatch(index, node, queryWords);
        if (reason) matches.push({ node, reason });
      }
    }
    if (matches.length > 0 || (own !== null && (!stepFacets || anyMeetsFacets))) {
      out.push({ flow, flowMatch: own, matches });
    }
  }

  return out.sort((a, b) =>
    asked
      ? Number(b.flowMatch !== null) - Number(a.flowMatch !== null) ||
        b.matches.length - a.matches.length ||
        cmp(lc(a.flow.name), lc(b.flow.name)) ||
        cmp(a.flow.id, b.flow.id)
      : productRank(a.flow.product) - productRank(b.flow.product) ||
        cmp(a.flow.product, b.flow.product) ||
        cmp(lc(a.flow.name), lc(b.flow.name)) ||
        cmp(a.flow.id, b.flow.id),
  );
}
