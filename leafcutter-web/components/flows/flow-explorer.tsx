"use client";

/**
 * The Flows view — an interactive graph of one product-truth flow.
 *
 * Steps lay out left-to-right by order; a branch drops below the step it forks
 * from; each step's acceptance criteria hang beneath it, wired by "implements"
 * edges. Step cards are coloured by their LIVE derived implementation status
 * (rolled up from the AC store), so the graph is an at-a-glance build tracker.
 * Click a step to open a drawer with its plain-language description, acceptance
 * scenario, entity reads/writes, the actual mock records, and its ACs as
 * status-coloured chips that link through to the AC Atlas.
 */
import * as React from "react";
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlowProvider,
  MarkerType,
  type Node,
  type Edge,
} from "reactflow";
import "reactflow/dist/style.css";
import { buildFlowGraph } from "@/lib/data/graph";
import { WORK_STATUS_TONE } from "@/lib/status";
import type { Flow, MockData, WorkStatus } from "@/lib/data/types";

interface XY {
  x: number;
  y: number;
}
import { flowNodeTypes } from "./flow-nodes";
import { edgeStyle } from "@/components/atlas/edges";
import { FlowDrawer, type StepView } from "./flow-drawer";

const COL_GAP = 340;
const AC_DROP = 210;
const BRANCH_DROP = 430;

const STATUS_LEGEND: WorkStatus[] = ["done", "in_progress", "not_started"];
const EDGE_LEGEND = ["flow", "implements"] as const;

function ExplorerInner({
  flow,
  mock,
  flowNames,
  onDrill,
}: {
  flow: Flow;
  mock: MockData | null;
  flowNames: Record<string, string>;
  onDrill?: (childFlowId: string) => void;
}) {
  const [selectedId, setSelectedId] = React.useState<string | null>(null);

  const graph = React.useMemo(() => buildFlowGraph(flow), [flow]);

  const nameFor = React.useCallback(
    (id: string | null) => (id ? flowNames[id] ?? null : null),
    [flowNames],
  );

  // Step-view lookup for the drawer, keyed by the graph node id (`step:<id>`).
  const stepViews = React.useMemo(() => {
    const m = new Map<string, StepView>();
    for (const s of flow.steps) {
      m.set(`step:${s.id}`, {
        id: s.id,
        label: s.label,
        human: s.human,
        screen: s.screen,
        variant: "step",
        status: s.implStatus,
        agent: s.agent,
        produces: s.produces,
        consumes: s.consumes,
        reads: s.reads,
        writes: s.writes,
        acs: s.acs,
        scenarios: flow.scenarios.filter((sc) => sc.for === s.id),
        expandsTo: s.expandsTo,
        expandsToName: nameFor(s.expandsTo),
      });
    }
    for (const b of flow.branches) {
      m.set(`step:${b.id}`, {
        id: b.id,
        label: b.label,
        human: b.human,
        screen: b.screen,
        variant: "branch",
        condition: b.condition,
        status: b.implStatus,
        agent: b.agent,
        produces: b.produces,
        consumes: b.consumes,
        reads: b.reads,
        writes: b.writes,
        acs: b.acs,
        scenarios: flow.scenarios.filter((sc) => sc.for === b.id),
        expandsTo: b.expandsTo,
        expandsToName: nameFor(b.expandsTo),
      });
    }
    return m;
  }, [flow, nameFor]);

  /* ---------- positions ---------- */
  const positions = React.useMemo(() => {
    const pos = new Map<string, XY>();
    for (const n of graph.nodes) {
      if (n.kind !== "phase") continue;
      const col = (n.meta?.col as number) ?? 0;
      const y = n.meta?.variant === "branch" ? BRANCH_DROP : 0;
      pos.set(n.id, { x: col * COL_GAP, y });
    }
    // AC nodes drop beneath the step/branch that implements them.
    const acSource = new Map<string, string>();
    for (const e of graph.edges) {
      if (e.kind === "implements") acSource.set(e.target, e.source);
    }
    const acSeen = new Map<string, number>(); // owner -> how many ACs placed
    for (const n of graph.nodes) {
      if (n.kind !== "ac") continue;
      const src = acSource.get(n.id);
      const base = src ? pos.get(src) ?? { x: 0, y: 0 } : { x: 0, y: 0 };
      const idx = acSeen.get(src ?? "") ?? 0;
      acSeen.set(src ?? "", idx + 1);
      pos.set(n.id, { x: base.x + idx * 240, y: base.y + AC_DROP });
    }
    return pos;
  }, [graph]);

  /* ---------- nodes + edges ---------- */
  const nodes = React.useMemo<Node[]>(
    () =>
      graph.nodes.map((n) => {
        const p = positions.get(n.id) ?? { x: 0, y: 0 };
        if (n.kind === "ac") {
          return {
            id: n.id,
            type: "acNode",
            position: p,
            data: {
              id: (n.meta?.acId as string) ?? n.label,
              title: (n.meta?.title as string) ?? "",
              level: n.level ?? "L2",
              status: (n.status as WorkStatus) ?? "unknown",
            },
            draggable: false,
          };
        }
        const acIds = (n.meta?.acIds as string[]) ?? [];
        const expandsTo = (n.meta?.expandsTo as string | null) ?? null;
        return {
          id: n.id,
          type: "flowStepNode",
          position: p,
          data: {
            label: n.label,
            order: n.meta?.order as number | undefined,
            screen: (n.meta?.screen as string | null) ?? null,
            status: (n.status as WorkStatus) ?? "unknown",
            variant: (n.meta?.variant as "step" | "branch") ?? "step",
            acCount: acIds.length,
            drillable: Boolean(expandsTo && flowNames[expandsTo]),
            selected: n.id === selectedId,
          },
          draggable: false,
        };
      }),
    [graph, positions, selectedId, flowNames],
  );

  const edges = React.useMemo<Edge[]>(
    () =>
      graph.edges.map((e) => {
        const spec = edgeStyle(e.kind);
        const isFlow = e.kind === "flow";
        return {
          id: e.id,
          source: e.source,
          target: e.target,
          animated: isFlow,
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: `hsl(${spec.hsl})`,
            width: 15,
            height: 15,
          },
          style: {
            stroke: `hsl(${spec.hsl})`,
            strokeWidth: isFlow ? 2 : 1.4,
            opacity: isFlow ? 0.85 : 0.55,
            strokeDasharray: spec.dashed ? "5 4" : undefined,
          },
        };
      }),
    [graph],
  );

  const onNodeClick = React.useCallback(
    (evt: React.MouseEvent, node: Node) => {
      if (node.type !== "flowStepNode") return;
      const view = stepViews.get(node.id);
      const childId = view?.expandsTo ?? null;
      const canDrill = Boolean(childId && view?.expandsToName && onDrill);
      // Clicking the drill affordance drills in; clicking elsewhere opens the drawer.
      const hitDrill = (evt.target as HTMLElement | null)?.closest?.("[data-flow-drill]");
      if (canDrill && hitDrill) {
        onDrill!(childId!);
        return;
      }
      setSelectedId(node.id);
    },
    [stepViews, onDrill],
  );

  const selectedStep = selectedId ? stepViews.get(selectedId) ?? null : null;

  return (
    <div className="panel relative h-[calc(100svh-20rem)] min-h-[560px] overflow-hidden p-0">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodeClick={onNodeClick}
        onPaneClick={() => setSelectedId(null)}
        nodeTypes={flowNodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.2}
        maxZoom={2.2}
        nodesDraggable={false}
        nodesConnectable={false}
        proOptions={{ hideAttribution: true }}
        className="bg-transparent"
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={26}
          size={1}
          color="hsl(156 16% 18%)"
        />
        <Controls showInteractive={false} className="!bottom-4 !left-4" />
        <MiniMap
          pannable
          zoomable
          className="!bottom-4 !right-4 !bg-card/80 !border !border-border/70"
          maskColor="hsl(160 26% 6% / 0.7)"
          nodeColor={(n) => {
            const status = (n.data?.status as WorkStatus) ?? "unknown";
            return `hsl(${(WORK_STATUS_TONE[status] ?? WORK_STATUS_TONE.unknown).hsl})`;
          }}
          nodeStrokeWidth={0}
        />
      </ReactFlow>

      {/* legend */}
      <div className="pointer-events-none absolute right-4 top-4 z-10">
        <div className="pointer-events-auto panel max-w-xs p-3.5">
          <div className="eyebrow mb-2">Legend</div>
          <div className="mb-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground/80">
            Step status
          </div>
          <div className="mb-3 flex flex-wrap gap-x-3 gap-y-1.5">
            {STATUS_LEGEND.map((st) => {
              const tone = WORK_STATUS_TONE[st];
              return (
                <span
                  key={st}
                  className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground"
                >
                  <span
                    className="h-2 w-2 rounded-full"
                    style={{ background: `hsl(${tone.hsl})` }}
                  />
                  {tone.label}
                </span>
              );
            })}
          </div>
          <div className="mb-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground/80">
            Edge type
          </div>
          <div className="flex flex-wrap gap-x-3 gap-y-1.5">
            {EDGE_LEGEND.map((kind) => {
              const spec = edgeStyle(kind);
              return (
                <span
                  key={kind}
                  className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground"
                >
                  <svg width="20" height="6" className="overflow-visible">
                    <line
                      x1="0"
                      y1="3"
                      x2="20"
                      y2="3"
                      stroke={`hsl(${spec.hsl})`}
                      strokeWidth="2"
                      strokeDasharray={spec.dashed ? "4 3" : undefined}
                    />
                  </svg>
                  {spec.label}
                </span>
              );
            })}
          </div>
        </div>
      </div>

      <FlowDrawer
        step={selectedStep}
        mock={mock}
        onClose={() => setSelectedId(null)}
        onDrill={onDrill}
      />
    </div>
  );
}

export function FlowExplorer({
  flow,
  mock,
  flowNames = {},
  onDrill,
}: {
  flow: Flow;
  mock: MockData | null;
  flowNames?: Record<string, string>;
  onDrill?: (childFlowId: string) => void;
}) {
  return (
    <ReactFlowProvider>
      <ExplorerInner flow={flow} mock={mock} flowNames={flowNames} onDrill={onDrill} />
    </ReactFlowProvider>
  );
}
