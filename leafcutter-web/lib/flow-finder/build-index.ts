/**
 * buildFinderIndex(flows): the flat, JSON-serialisable index the finder searches
 * (UXP-617-1). Built from the flow set the Flows view already loads; the server
 * builds it once per request and the client recomputes from it, so a search never
 * asks the server.
 */
import type { Flow, FlowBranch, FlowStep } from "@/lib/data/types";
import { byCodepoint } from "./facets";
import { fieldRefs } from "./field-keys";
import type { FinderFlow, FinderIndex, FinderNode, FinderScreen } from "./types";

type Node = FlowStep | FlowBranch;

const unique = (xs: string[]) => [...new Set(xs)];

function toNode(
  flow: Flow,
  node: Node,
  nodeKind: "step" | "branch",
  titles: Record<string, string>,
  fields: Record<string, string>,
): FinderNode {
  const consumes = fieldRefs(node.ioContracts?.consumes);
  const produces = fieldRefs(node.ioContracts?.produces);
  for (const ref of [...consumes, ...produces]) fields[ref.key] = ref.label;
  const gaps = node.ioContracts?.missing_bindings;
  return {
    flowId: flow.id,
    nodeId: node.id,
    nodeKind,
    order: nodeKind === "step" ? (node as FlowStep).order : null,
    label: node.label,
    text: node.description,
    condition: nodeKind === "branch" ? (node as FlowBranch).condition || null : null,
    actorKind: node.actorKind,
    acIds: unique(node.implements),
    uses: consumes.map((r) => r.key),
    produces: produces.map((r) => r.key),
    screen: node.screen ? { id: node.screen, title: titles[node.screen] ?? node.screen } : null,
    entities: unique([...node.reads, ...node.writes]),
    ioGap: Array.isArray(gaps) && gaps.length > 0,
  };
}

export function buildFinderIndex(
  flows: Flow[],
  screenTitles: Record<string, string> = {},
): FinderIndex {
  const fields: Record<string, string> = {};
  const nodes: FinderNode[] = [];
  const outFlows: FinderFlow[] = [];

  for (const flow of flows) {
    const mine = [
      ...flow.steps.map((s) => toNode(flow, s, "step", screenTitles, fields)),
      ...flow.branches.map((b) => toNode(flow, b, "branch", screenTitles, fields)),
    ];
    nodes.push(...mine);

    const screens = new Map<string, FinderScreen>();
    for (const n of mine) if (n.screen) screens.set(n.screen.id, n.screen);

    outFlows.push({
      id: flow.id,
      name: flow.name,
      product: flow.id.split("/")[0], // the stored flow.product is a display label
      kind: flow.kind,
      realization: flow.realization,
      level: flow.level,
      entities: unique([...flow.entities, ...mine.flatMap((n) => n.entities)]).sort(byCodepoint),
      declaredEntities: unique(flow.entities),
      screens: [...screens.values()].sort((a, b) => byCodepoint(a.id, b.id)),
      stepCount: flow.steps.length,
      branchCount: flow.branches.length,
    });
  }
  return { flows: outFlows, nodes, fields };
}
