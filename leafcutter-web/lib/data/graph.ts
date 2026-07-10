/**
 * Graph derivation — pure functions turning normalized data into node/edge sets.
 * No fs / no server-only: safe to import in client components too.
 *
 * Edge semantics for ACs:
 *   depends_on   AC  -> prerequisite AC
 *   delivers_to  AC  -> downstream AC (contract output)
 *   expects_from AC  -> upstream AC   (contract input)
 *   covers       parentAC -> child AC (covered_by / decomposition)
 */
import type {
  AC,
  AcRef,
  AgentDef,
  Component,
  Flow,
  Graph,
  GraphEdge,
  GraphNode,
} from "./types";

/** Build the AC relationship graph from a (possibly filtered) list of ACs. */
export function buildAcGraph(acs: AC[]): Graph {
  const ids = new Set(acs.map((a) => a.id));
  const nodes: GraphNode[] = acs.map((a) => ({
    id: a.id,
    kind: "ac",
    label: a.id,
    group: a.component,
    status: a.workStatus,
    level: a.level,
    priority: a.priority,
    meta: {
      title: a.title,
      assignedAgent: a.assignedAgent,
      readiness: a.readiness,
      complexity: a.complexity,
    },
  }));

  const edges: GraphEdge[] = [];
  const seen = new Set<string>();
  const add = (source: string, target: string, kind: GraphEdge["kind"]) => {
    if (!ids.has(source) || !ids.has(target) || source === target) return;
    const id = `${kind}:${source}->${target}`;
    if (seen.has(id)) return;
    seen.add(id);
    edges.push({ id, source, target, kind });
  };

  for (const a of acs) {
    for (const d of a.dependsOn) add(a.id, d, "depends_on");
    if (a.deliversTo) add(a.id, a.deliversTo, "delivers_to");
    for (const e of a.expectsFrom) add(a.id, e.id, "expects_from");
    for (const c of a.coveredBy) add(a.id, c, "covers");
  }

  return { nodes, edges };
}

/**
 * Build a product-truth flow graph.
 *   - one "phase" node per step (col by order) and per branch (col of its `from`),
 *     coloured by the step's LIVE derived implStatus.
 *   - one "ac" node per referenced acceptance criterion, coloured by live workStatus.
 *   - "flow" edges chain consecutive steps and link branch.from -> branch.
 *   - "implements" edges link each step/branch to its AC node(s).
 * The AC status is carried on both the AC node and the step node data so the
 * step colour always reflects live AC state.
 */
export function buildFlowGraph(flow: Flow): Graph {
  const nodes: GraphNode[] = [];
  const edges: GraphEdge[] = [];
  const seenAc = new Set<string>();

  const addAcNodes = (acs: AcRef[]) => {
    for (const a of acs) {
      const nodeId = `ac:${a.id}`;
      if (seenAc.has(nodeId)) continue;
      seenAc.add(nodeId);
      nodes.push({
        id: nodeId,
        kind: "ac",
        label: a.id,
        group: flow.component,
        status: a.workStatus,
        level: a.level,
        meta: { acId: a.id, title: a.title, resolved: a.resolved },
      });
    }
  };

  const steps = [...flow.steps].sort((a, b) => a.order - b.order);
  const colOf = new Map<string, number>();
  steps.forEach((s, i) => colOf.set(s.id, i));

  steps.forEach((s, i) => {
    nodes.push({
      id: `step:${s.id}`,
      kind: "phase",
      label: s.label,
      group: flow.component,
      status: s.implStatus,
      meta: {
        variant: "step",
        col: i,
        order: s.order,
        screen: s.screen,
        human: s.human,
        reads: s.reads,
        writes: s.writes,
        acIds: s.implements,
      },
    });
    addAcNodes(s.acs);
    for (const a of s.acs) {
      edges.push({
        id: `implements:step:${s.id}->${a.id}`,
        source: `step:${s.id}`,
        target: `ac:${a.id}`,
        kind: "implements",
      });
    }
  });

  for (let i = 0; i < steps.length - 1; i++) {
    edges.push({
      id: `flow:${steps[i].id}->${steps[i + 1].id}`,
      source: `step:${steps[i].id}`,
      target: `step:${steps[i + 1].id}`,
      kind: "flow",
    });
  }

  for (const b of flow.branches) {
    nodes.push({
      id: `step:${b.id}`,
      kind: "phase",
      label: b.label,
      group: flow.component,
      status: b.implStatus,
      meta: {
        variant: "branch",
        col: colOf.get(b.from) ?? 0,
        from: b.from,
        condition: b.condition,
        screen: b.screen,
        human: b.human,
        reads: b.reads,
        writes: b.writes,
        acIds: b.implements,
      },
    });
    addAcNodes(b.acs);
    if (colOf.has(b.from)) {
      edges.push({
        id: `flow:${b.from}->${b.id}`,
        source: `step:${b.from}`,
        target: `step:${b.id}`,
        kind: "flow",
      });
    }
    for (const a of b.acs) {
      edges.push({
        id: `implements:step:${b.id}->${a.id}`,
        source: `step:${b.id}`,
        target: `ac:${a.id}`,
        kind: "implements",
      });
    }
  }

  return { nodes, edges };
}

/**
 * Component-level rollup graph: one node per AC-store component, edges weighted
 * by the number of cross-component AC dependencies. Good for a zoomed-out map.
 */
export function buildComponentDepGraph(acs: AC[]): Graph {
  const byId = new Map(acs.map((a) => [a.id, a]));
  const compOf = (id: string) => byId.get(id)?.component;
  const comps = new Set(acs.map((a) => a.component));
  const weight = new Map<string, number>();

  const bump = (from: string, to: string) => {
    if (!from || !to || from === to) return;
    const k = `${from}=>${to}`;
    weight.set(k, (weight.get(k) ?? 0) + 1);
  };

  for (const a of acs) {
    const link = (targetId: string) => {
      const to = compOf(targetId);
      if (to) bump(a.component, to);
    };
    a.dependsOn.forEach(link);
    if (a.deliversTo) link(a.deliversTo);
    a.expectsFrom.forEach((e) => link(e.id));
  }

  const nodes: GraphNode[] = Array.from(comps).map((c) => ({
    id: c,
    kind: "component",
    label: c,
    group: c,
    meta: { acCount: acs.filter((a) => a.component === c).length },
  }));

  const edges: GraphEdge[] = Array.from(weight.entries()).map(([k, w]) => {
    const [source, target] = k.split("=>");
    return { id: `dep:${k}`, source, target, kind: "depends_on", weight: w };
  });

  return { nodes, edges };
}

/** Architecture component graph: nodes grouped by type, edges from shared AC components. */
export function buildComponentGraph(components: Component[]): Graph {
  const nodes: GraphNode[] = components.map((c) => ({
    id: c.id,
    kind: "component",
    label: c.name,
    group: c.type,
    meta: {
      description: c.description,
      detailRef: c.detailRef,
      status: c.status,
      primaryCode: c.primaryCode,
    },
  }));
  return { nodes, edges: [] };
}

/** Agent spawn-topology graph from the registry (who dispatches whom). */
export function buildAgentTopology(agents: AgentDef[]): Graph {
  const ids = new Set(agents.map((a) => a.id));
  const nodes: GraphNode[] = agents.map((a) => ({
    id: a.id,
    kind: "agent",
    label: a.name,
    group: a.category ?? a.tier ?? "other",
    meta: {
      role: a.role,
      tier: a.tier,
      model: a.model,
      deprecated: a.deprecated,
      isTicketPhase: a.isTicketPhase,
    },
  }));
  const edges: GraphEdge[] = [];
  const seen = new Set<string>();
  for (const a of agents) {
    for (const t of a.spawnAllowlist) {
      if (!ids.has(t)) continue; // skip sentinels like __ticket_phase_agents__
      const id = `spawn:${a.id}->${t}`;
      if (seen.has(id)) continue;
      seen.add(id);
      edges.push({ id, source: a.id, target: t, kind: "flow" });
    }
  }
  return { nodes, edges };
}
