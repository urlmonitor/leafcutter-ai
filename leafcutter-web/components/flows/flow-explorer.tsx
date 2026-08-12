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
import { cn } from "@/lib/utils";
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
// Vertical lane per sibling branch forking from the SAME step. Two branches off
// one step share a column, so without this they (and their AC nodes) would stack
// at identical coordinates and hide each other. A lane clears the branch card
// plus its AC row (AC_DROP) beneath it.
const BRANCH_LANE = AC_DROP + 180;

const STATUS_LEGEND: WorkStatus[] = ["done", "in_progress", "not_started"];
const EDGE_LEGEND_ALL = ["flow", "implements"] as const;
type EdgeLegendKind = (typeof EDGE_LEGEND_ALL)[number];

function ExplorerInner({
  flow,
  mock,
  flowNames,
  screenTitles,
  onDrill,
}: {
  flow: Flow;
  mock: MockData | null;
  flowNames: Record<string, string>;
  screenTitles: Record<string, string>;
  onDrill?: (childFlowId: string) => void;
}) {
  const [selectedId, setSelectedId] = React.useState<string | null>(null);

  // "Show ACs in graph" toggle — default OFF; persisted as a simple view preference.
  const [showAcNodes, setShowAcNodes] = React.useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    try { return localStorage.getItem("flows:showAcNodes") === "1"; } catch { return false; }
  });
  const handleToggleShowAcNodes = React.useCallback(() => {
    setShowAcNodes((prev) => {
      const next = !prev;
      try { localStorage.setItem("flows:showAcNodes", next ? "1" : "0"); } catch {}
      return next;
    });
  }, []);

  const graph = React.useMemo(() => buildFlowGraph(flow, showAcNodes), [flow, showAcNodes]);

  const nameFor = React.useCallback(
    (id: string | null) => (id ? flowNames[id] ?? null : null),
    [flowNames],
  );

  const screenTitleFor = React.useCallback(
    (slug: string | null) => (slug ? screenTitles[slug] ?? null : null),
    [screenTitles],
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
        screenTitle: screenTitleFor(s.screen),
        realization: flow.realization,
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
        screenTitle: screenTitleFor(b.screen),
        realization: flow.realization,
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
  }, [flow, nameFor, screenTitleFor]);

  /* ---------- positions ---------- */
  const positions = React.useMemo(() => {
    const pos = new Map<string, XY>();
    // Track how many branches have already been placed in each column so that
    // sibling branches off the same step drop into successive vertical lanes
    // instead of colliding at one point.
    const branchesInCol = new Map<number, number>();
    for (const n of graph.nodes) {
      if (n.kind !== "phase") continue;
      const col = (n.meta?.col as number) ?? 0;
      if (n.meta?.variant === "branch") {
        const lane = branchesInCol.get(col) ?? 0;
        branchesInCol.set(col, lane + 1);
        pos.set(n.id, { x: col * COL_GAP, y: BRANCH_DROP + lane * BRANCH_LANE });
      } else {
        pos.set(n.id, { x: col * COL_GAP, y: 0 });
      }
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
        // Decision diamond nodes (ADR-025 synthesized from branch data)
        if (n.meta?.variant === "decision") {
          return {
            id: n.id,
            type: "flowDecisionNode",
            position: p,
            data: {
              condition: (n.meta?.condition as string) ?? n.label,
              yesLabel: (n.meta?.yesLabel as string) ?? "yes",
              noLabel: (n.meta?.noLabel as string) ?? "no",
              // UXP-601: pass derived status so the diamond tints by impl_status
              status: (n.status as WorkStatus) ?? "unknown",
            },
            draggable: false,
          };
        }
        const acIds = (n.meta?.acIds as string[]) ?? [];
        const acDone = (n.meta?.acDone as number) ?? 0;
        const expandsTo = (n.meta?.expandsTo as string | null) ?? null;
        const screen = (n.meta?.screen as string | null) ?? null;
        return {
          id: n.id,
          type: "flowStepNode",
          position: p,
          data: {
            label: n.label,
            order: n.meta?.order as number | undefined,
            screen,
            screenTitle: screenTitleFor(screen),
            realization: flow.realization,
            status: (n.status as WorkStatus) ?? "unknown",
            variant: (n.meta?.variant as "step" | "branch") ?? "step",
            acCount: acIds.length,
            acDone,
            drillable: Boolean(expandsTo && flowNames[expandsTo]),
            selected: n.id === selectedId,
          },
          draggable: false,
        };
      }),
    [graph, positions, selectedId, flowNames, screenTitleFor, flow.realization],
  );

  const edges = React.useMemo<Edge[]>(
    () =>
      graph.edges.map((e) => {
        const spec = edgeStyle(e.kind);
        const isFlow = e.kind === "flow";
        const base: Edge = {
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
        // Decision edge label (yes / no / else / continue)
        if (e.label) {
          base.label = e.label;
          base.labelStyle = {
            fill: "hsl(155 7% 78%)",
            fontSize: 10,
            fontWeight: 600,
          };
          base.labelBgStyle = {
            fill: "hsl(158 12% 11%)",
            fillOpacity: 0.88,
          };
          base.labelBgPadding = [3, 5] as [number, number];
        }
        // Source handle routing for decision diamond edges ("yes" | "no")
        if (e.sourceHandle) base.sourceHandle = e.sourceHandle;
        return base;
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
        // Floor the initial fit zoom so large graphs (e.g. how-acs-are-built,
        // 19 nodes) open at a legible zoom and the user pans, instead of the
        // default fitView shrinking every label to specks. Small flows already
        // fit above this floor, so they are unaffected. The interaction minZoom
        // below stays low so users can still manually zoom out to see everything.
        fitViewOptions={{ padding: 0.2, minZoom: 0.62 }}
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
          <div className="mb-3 flex flex-wrap gap-x-3 gap-y-1.5">
            {(showAcNodes ? EDGE_LEGEND_ALL : (["flow"] as EdgeLegendKind[])).map((kind) => {
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
          {/* Feature-level AC rollup + "Show ACs in graph" toggle */}
          <div className="border-t border-border/50 pt-2.5">
            {flow.implSummary.acTotal > 0 && (
              <div className="mb-2 text-[11px] text-muted-foreground">
                Feature:{" "}
                <span
                  className="font-mono font-semibold tabular-nums"
                  style={{ color: `hsl(${WORK_STATUS_TONE.done.hsl})` }}
                >
                  {flow.implSummary.acDone}
                </span>
                <span className="font-mono tabular-nums">
                  /{flow.implSummary.acTotal}
                </span>{" "}
                ACs done
              </div>
            )}
            <button
              type="button"
              onClick={handleToggleShowAcNodes}
              className={cn(
                "inline-flex w-full items-center justify-between gap-2 rounded-md px-2.5 py-1.5 text-[11px] transition-colors",
                showAcNodes
                  ? "bg-primary/15 text-primary"
                  : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground",
              )}
              title={showAcNodes ? "Hide AC nodes from graph" : "Show AC nodes in graph"}
            >
              <span>Show ACs in graph</span>
              <span
                className={cn(
                  "h-2.5 w-2.5 rounded-full border transition-colors",
                  showAcNodes
                    ? "border-primary/60 bg-primary"
                    : "border-muted-foreground/40 bg-transparent",
                )}
              />
            </button>
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
  screenTitles = {},
  onDrill,
}: {
  flow: Flow;
  mock: MockData | null;
  flowNames?: Record<string, string>;
  screenTitles?: Record<string, string>;
  onDrill?: (childFlowId: string) => void;
}) {
  return (
    <ReactFlowProvider>
      <ExplorerInner
        flow={flow}
        mock={mock}
        flowNames={flowNames}
        screenTitles={screenTitles}
        onDrill={onDrill}
      />
    </ReactFlowProvider>
  );
}
