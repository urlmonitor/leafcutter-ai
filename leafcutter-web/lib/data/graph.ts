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
  ArtifactGraphNode,
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
 *   - one "phase" node per step (col by order) and per branch (col of its decision
 *     diamond), coloured by the step's LIVE derived implStatus.
 *   - one "phase" node (variant "decision") per branch, synthesized between the
 *     branching step and the next step. Multiple branches off the same step produce
 *     a CHAIN of diamonds: step → ◇ → ◇ → next step, one diamond per branch.
 *     Each diamond's "yes" handle points to its branch outcome; the "no" handle
 *     passes to the next diamond (or to the happy-path next step for the last one).
 *   - one "ac" node per referenced acceptance criterion, coloured by live workStatus.
 *   - "flow" edges chain consecutive steps and link decision outcomes.
 *   - "implements" edges link each step/branch to its AC node(s).
 * The AC status is carried on both the AC node and the step node data so the
 * step colour always reflects live AC state.
 *
 * ADR-025 chaining semantics (derived from branch data — no schema change):
 *   For each step S with branches [B0, B1, …, BN-1] and a next step T:
 *     S → D0 → (yes) B0 ; D0 → (no) D1 → (yes) B1 ; … ; DN-1 → (no) T
 */
export function buildFlowGraph(flow: Flow, showAcNodes = false): Graph {
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

  // ------------------------------------------------------------------
  // Column assignment: each step occupies 1 column; each branch off that
  // step reserves an additional column for its decision diamond.
  // Example: step A (2 branches) → step B gives cols: A=0, D0=1, D1=2, B=3.
  // ------------------------------------------------------------------
  const stepColMap = new Map<string, number>(); // stepId → col
  // Group branches by the step they fork from (preserving declaration order).
  const stepBranchesMap = new Map<string, (typeof flow.branches[number])[]>();
  for (const b of flow.branches) {
    const arr = stepBranchesMap.get(b.from) ?? [];
    arr.push(b);
    stepBranchesMap.set(b.from, arr);
  }

  let nextCol = 0;
  for (const s of steps) {
    stepColMap.set(s.id, nextCol);
    nextCol++;
    const stepBranches = stepBranchesMap.get(s.id);
    if (stepBranches && stepBranches.length > 0) {
      nextCol += stepBranches.length; // reserve N cols for N decision diamonds
    }
  }

  // branchDecisionCol: branchId → the col of the diamond that routes to it.
  // Populated in the flow-edge loop; consumed in the branch-node loop.
  const branchDecisionCol = new Map<string, number>();

  // ------------------------------------------------------------------
  // Step nodes
  // ------------------------------------------------------------------
  for (const s of steps) {
    const col = stepColMap.get(s.id) ?? 0;
    nodes.push({
      id: `step:${s.id}`,
      kind: "phase",
      label: s.label,
      group: flow.component,
      status: s.implStatus,
      meta: {
        variant: "step",
        col,
        order: s.order,
        screen: s.screen,
        human: s.human,
        reads: s.reads,
        writes: s.writes,
        acIds: s.implements,
        acDone: s.acs.filter((a) => a.workStatus === "done").length,
        expandsTo: s.expandsTo,
      },
    });
    if (showAcNodes) {
      addAcNodes(s.acs);
      for (const a of s.acs) {
        edges.push({
          id: `implements:step:${s.id}->${a.id}`,
          source: `step:${s.id}`,
          target: `ac:${a.id}`,
          kind: "implements",
        });
      }
    }
  }

  // ------------------------------------------------------------------
  // Flow edges: direct for steps without branches; diamond chain otherwise.
  // ------------------------------------------------------------------
  for (let i = 0; i < steps.length - 1; i++) {
    const curr = steps[i];
    const next = steps[i + 1];
    const branches = stepBranchesMap.get(curr.id);

    if (!branches || branches.length === 0) {
      // Simple happy-path edge: step → next step.
      edges.push({
        id: `flow:${curr.id}->${next.id}`,
        source: `step:${curr.id}`,
        target: `step:${next.id}`,
        kind: "flow",
      });
      continue;
    }

    // Synthesize a chain of decision diamonds.
    const currCol = stepColMap.get(curr.id) ?? 0;

    for (let j = 0; j < branches.length; j++) {
      const branch = branches[j];
      const dCol = currCol + 1 + j;
      const dId = `decision:${curr.id}:${j}`;

      // Remember which col this branch's diamond lands on (for branch positioning).
      branchDecisionCol.set(branch.id, dCol);

      // Decision diamond node (variant "decision", kind "phase" for layout compat).
      // status is derived from the branch this diamond gates (UXP-601).
      nodes.push({
        id: dId,
        kind: "phase",
        label: branch.condition,
        group: flow.component,
        status: branch.implStatus,
        meta: {
          variant: "decision",
          col: dCol,
          condition: branch.condition,
          yesLabel: branch.label,
          noLabel: j < branches.length - 1 ? "else" : "continue",
        },
      });

      // Wire the INCOMING edge to this diamond.
      if (j === 0) {
        // First diamond: previous node is the step itself.
        edges.push({
          id: `flow:step:${curr.id}->${dId}`,
          source: `step:${curr.id}`,
          target: dId,
          kind: "flow",
        });
      } else {
        // Subsequent diamonds: previous node is the prior diamond's "no" handle.
        const prevDId = `decision:${curr.id}:${j - 1}`;
        edges.push({
          id: `flow:${prevDId}->${dId}`,
          source: prevDId,
          target: dId,
          kind: "flow",
          label: "else",
          sourceHandle: "no",
        });
      }

      // Yes edge: diamond → branch outcome (sourceHandle "yes", goes downward).
      edges.push({
        id: `flow:${dId}->step:${branch.id}`,
        source: dId,
        target: `step:${branch.id}`,
        kind: "flow",
        label: branch.label,
        sourceHandle: "yes",
      });

      // For the LAST diamond: no edge → next step (happy path).
      if (j === branches.length - 1) {
        edges.push({
          id: `flow:${dId}->step:${next.id}`,
          source: dId,
          target: `step:${next.id}`,
          kind: "flow",
          label: "continue",
          sourceHandle: "no",
        });
      }
    }
  }

  // ------------------------------------------------------------------
  // Branch nodes (positioned at their decision diamond's col).
  // NOTE: the flow edge from step → branch is now handled by the decision
  // diamond's yes-edge; do NOT re-add the old direct edge here.
  // ------------------------------------------------------------------
  for (const b of flow.branches) {
    const bCol = branchDecisionCol.get(b.id) ?? (stepColMap.get(b.from) ?? 0);
    nodes.push({
      id: `step:${b.id}`,
      kind: "phase",
      label: b.label,
      group: flow.component,
      status: b.implStatus,
      meta: {
        variant: "branch",
        col: bCol,
        from: b.from,
        condition: b.condition,
        screen: b.screen,
        human: b.human,
        reads: b.reads,
        writes: b.writes,
        acIds: b.implements,
        acDone: b.acs.filter((a) => a.workStatus === "done").length,
        expandsTo: b.expandsTo,
      },
    });
    if (showAcNodes) {
      addAcNodes(b.acs);
      for (const a of b.acs) {
        edges.push({
          id: `implements:step:${b.id}->${a.id}`,
          source: `step:${b.id}`,
          target: `ac:${a.id}`,
          kind: "implements",
        });
      }
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

/**
 * Artifact knowledge-graph: turn the authored nodes/edges JSON into a React Flow
 * graph where every artifact type is a node and every field-level relationship is
 * an edge. Nodes are positioned by `rank` (column) and row index within that rank.
 * Only emits nodes/edges when the flow has graphNodes/graphEdges attached.
 */
export function buildArtifactGraph(flow: Flow): Graph {
  if (!flow.graphNodes || !flow.graphEdges) return { nodes: [], edges: [] };

  // Group nodes by rank so we can assign row indices within each column.
  const nodesByRank = new Map<number, ArtifactGraphNode[]>();
  for (const n of flow.graphNodes) {
    const arr = nodesByRank.get(n.rank) ?? [];
    arr.push(n);
    nodesByRank.set(n.rank, arr);
  }

  const rowIndexOf = new Map<string, number>();
  for (const arr of nodesByRank.values()) {
    arr.forEach((n, i) => rowIndexOf.set(n.id, i));
  }

  const nodes: GraphNode[] = flow.graphNodes.map((n) => ({
    id: n.id,
    kind: "artifact",
    label: n.label,
    group: n.group,
    meta: {
      rank: n.rank,
      row: rowIndexOf.get(n.id) ?? 0,
      path: n.path,
      key: n.key,
      note: n.note,
    },
  }));

  const nodeIds = new Set(nodes.map((n) => n.id));

  const edges: GraphEdge[] = flow.graphEdges
    .filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target))
    .map((e): GraphEdge => ({
      id: e.id,
      source: e.source,
      target: e.target,
      kind: "flow",
      label: e.rel,
      enforcement: e.enforcement,
      rel: e.rel,
      // Carry the full authored payload. `shape` is required to evaluate the
      // store's own ingestable_rule (enforcement AND shape), and `field` is
      // the most actionable datum on the map — dropping either made the
      // rendered graph claim more trust than the data supports.
      field: e.field,
      shape: e.shape,
      cardinality: e.cardinality,
      note: e.note,
    }));

  return { nodes, edges };
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
