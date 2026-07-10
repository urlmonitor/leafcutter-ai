"use client";

/**
 * The AC Atlas — a two-level interactive graph explorer.
 *
 *   Galaxy mode (default): one glowing disc per AC-store component, sized by AC
 *   count, wired by weighted cross-component dependency edges. Click a disc to
 *   drill in.
 *
 *   Detail mode: the selected component's ACs laid out as a left-to-right
 *   layered DAG (column per level), coloured by work-status, edged by relation
 *   kind. Click a node to open the detail drawer.
 *
 * Performance: only ~13 discs mount in galaxy mode; detail mode mounts a single
 * component's ACs (filterable by level / status / search), never the full 2k.
 */
import * as React from "react";
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  useReactFlow,
  ReactFlowProvider,
  MarkerType,
  type Node,
  type Edge,
} from "reactflow";
import "reactflow/dist/style.css";
import { ChevronRight, ArrowLeft, Sparkles, GitBranch } from "lucide-react";
import { buildAcGraph, buildComponentDepGraph } from "@/lib/data/graph";
import { colorForKey, LEVEL_TONE } from "@/lib/status";
import { cn, humanize } from "@/lib/utils";
import { EmptyState } from "@/components/ui/kit";
import type { AC, AcLevel, FlowAppearance, WorkStatus } from "@/lib/data/types";
import { nodeTypes } from "./nodes";
import { dagPositions, galaxyPositions } from "./layout";
import { edgeStyle } from "./edges";
import {
  AtlasLegend,
  FilterPanel,
  FILTER_LEVELS,
  FILTER_STATUSES,
  type FilterState,
} from "./controls";
import { DetailDrawer } from "./detail-drawer";

function defaultFilters(): FilterState {
  return {
    levels: new Set<AcLevel>(FILTER_LEVELS),
    statuses: new Set<WorkStatus>(FILTER_STATUSES),
    search: "",
    colorByCoverage: false,
  };
}

/** Node dot colour when "color by coverage" is on: 0 red, 1–2 amber, 3+ green. */
function coverageHslFor(testCount: number): string {
  if (testCount === 0) return "356 72% 56%";
  if (testCount < 3) return "38 92% 58%";
  return "150 60% 48%";
}

function ExplorerInner({
  acs,
  flowIndex,
}: {
  acs: AC[];
  flowIndex?: Record<string, FlowAppearance[]>;
}) {
  const rf = useReactFlow();
  const [selectedComponent, setSelectedComponent] = React.useState<string | null>(
    null,
  );
  const [selectedNodeId, setSelectedNodeId] = React.useState<string | null>(null);
  const [filters, setFilters] = React.useState<FilterState>(defaultFilters);

  const detailMode = selectedComponent !== null;

  const acById = React.useMemo(() => {
    const m = new Map<string, AC>();
    for (const a of acs) m.set(a.id, a);
    return m;
  }, [acs]);

  // Per-component roll-up stats (count + done) for galaxy disc sizing / ring.
  const compStats = React.useMemo(() => {
    const m = new Map<string, { count: number; done: number }>();
    for (const a of acs) {
      const s = m.get(a.component) ?? { count: 0, done: 0 };
      s.count += 1;
      if (a.workStatus === "done") s.done += 1;
      m.set(a.component, s);
    }
    return m;
  }, [acs]);

  const maxCount = React.useMemo(
    () => Math.max(1, ...Array.from(compStats.values()).map((s) => s.count)),
    [compStats],
  );

  const galaxyGraph = React.useMemo(() => buildComponentDepGraph(acs), [acs]);

  // ACs belonging to the drilled-in component, then filtered for the DAG.
  const componentAcs = React.useMemo(
    () => (selectedComponent ? acs.filter((a) => a.component === selectedComponent) : []),
    [acs, selectedComponent],
  );

  const detailAcs = React.useMemo(() => {
    if (!detailMode) return [];
    const q = filters.search.trim().toLowerCase();
    return componentAcs.filter((a) => {
      if (!filters.levels.has(a.level)) return false;
      if (!filters.statuses.has(a.workStatus)) return false;
      if (q && !(a.id.toLowerCase().includes(q) || a.title.toLowerCase().includes(q)))
        return false;
      return true;
    });
  }, [detailMode, componentAcs, filters]);

  const detailGraph = React.useMemo(
    () => (detailMode ? buildAcGraph(detailAcs) : { nodes: [], edges: [] }),
    [detailMode, detailAcs],
  );

  const presentIds = React.useMemo(
    () => new Set(detailAcs.map((a) => a.id)),
    [detailAcs],
  );

  /* ---------- structural nodes + edges (drives fitView) ---------- */
  const { baseNodes, baseEdges } = React.useMemo(() => {
    if (!detailMode) {
      const q = filters.search.trim().toLowerCase();
      const visible = galaxyGraph.nodes.filter(
        (n) => !q || n.id.toLowerCase().includes(q) || humanize(n.id).toLowerCase().includes(q),
      );
      const visibleIds = new Set(visible.map((n) => n.id));
      const centers = galaxyPositions(
        visible.map((n) => ({ id: n.id, weight: compStats.get(n.id)?.count ?? 0 })),
      );
      const nodes: Node[] = visible.map((n) => {
        const stats = compStats.get(n.id) ?? { count: 0, done: 0 };
        const diameter =
          96 + (Math.sqrt(stats.count) / Math.sqrt(maxCount)) * 120;
        const c = centers.get(n.id) ?? { x: 0, y: 0 };
        return {
          id: n.id,
          type: "componentNode",
          position: { x: c.x - diameter / 2, y: c.y - diameter / 2 },
          data: {
            label: humanize(n.id),
            hsl: colorForKey(n.id),
            count: stats.count,
            done: stats.done,
            diameter,
          },
          draggable: true,
        };
      });
      const edges: Edge[] = galaxyGraph.edges
        .filter((e) => visibleIds.has(e.source) && visibleIds.has(e.target))
        .map((e) => {
          const w = e.weight ?? 1;
          // Visual flip: data models dependent -> prerequisite, but the graph
          // reads better prerequisite -> dependent (arrowhead lands on the
          // thing that builds on the other). Swap endpoints for these dep edges.
          return {
            id: e.id,
            source: e.target,
            target: e.source,
            animated: w >= 4,
            markerEnd: {
              type: MarkerType.ArrowClosed,
              color: "hsl(150 64% 52%)",
              width: 16,
              height: 16,
            },
            style: {
              stroke: "hsl(150 64% 52%)",
              strokeWidth: 1 + Math.min(w, 8) * 0.7,
              opacity: 0.28 + Math.min(w, 10) * 0.05,
            },
          };
        });
      return { baseNodes: nodes, baseEdges: edges };
    }

    // detail (DAG) mode
    const pos = dagPositions(detailGraph);
    const nodes: Node[] = detailGraph.nodes.map((n) => {
      const p = pos.get(n.id) ?? { x: 0, y: 0 };
      const coverageHsl = filters.colorByCoverage
        ? coverageHslFor(acById.get(n.id)?.testCount ?? 0)
        : undefined;
      return {
        id: n.id,
        type: "acNode",
        position: p,
        data: {
          id: n.id,
          title: (n.meta?.title as string) ?? "",
          level: (n.level as AcLevel) ?? "L2",
          status: (n.status as WorkStatus) ?? "unknown",
          coverageHsl,
        },
        draggable: true,
      };
    });
    const edges: Edge[] = detailGraph.edges.map((e) => {
      const spec = edgeStyle(e.kind);
      // depends_on / expects_from point dependent -> prerequisite in the data;
      // flip them so every arrowhead visually lands on the child / dependent.
      // covers (parent -> child) and delivers_to (upstream -> downstream)
      // already flow that way, so leave them untouched.
      const flip = e.kind === "depends_on" || e.kind === "expects_from";
      return {
        id: e.id,
        source: flip ? e.target : e.source,
        target: flip ? e.source : e.target,
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: `hsl(${spec.hsl})`,
          width: 14,
          height: 14,
        },
        style: {
          stroke: `hsl(${spec.hsl})`,
          strokeWidth: e.kind === "depends_on" ? 1.8 : 1.4,
          opacity: e.kind === "covers" ? 0.35 : 0.7,
          strokeDasharray: spec.dashed ? "5 4" : undefined,
        },
      };
    });
    return { baseNodes: nodes, baseEdges: edges };
  }, [
    detailMode,
    galaxyGraph,
    detailGraph,
    compStats,
    maxCount,
    filters.search,
    filters.colorByCoverage,
    acById,
  ]);

  /* ---------- apply selection styling without refitting ---------- */
  const displayNodes = React.useMemo<Node[]>(
    () =>
      baseNodes.map((n) => ({
        ...n,
        data: { ...n.data, selected: n.id === selectedNodeId },
      })),
    [baseNodes, selectedNodeId],
  );

  // Nodes/edges are passed directly as controlled props (mirrors the proven
  // Pipeline constellation). The <ReactFlow key> below changes on every mode /
  // component switch, which remounts the flow so its built-in `fitView` prop
  // frames the new node set from scratch — no manual fitView effect needed.
  // Selection styling flows through `displayNodes` without remounting (the key
  // is stable within a mode), so re-selecting never refits the viewport.

  /* ---------- interactions ---------- */
  const onNodeClick = React.useCallback(
    (_evt: React.MouseEvent, node: Node) => {
      if (node.type === "componentNode") {
        setSelectedComponent(node.id);
        setSelectedNodeId(null);
        setFilters(defaultFilters());
      } else {
        setSelectedNodeId(node.id);
      }
    },
    [],
  );

  const selectAc = React.useCallback(
    (id: string) => {
      if (!presentIds.has(id)) return;
      setSelectedNodeId(id);
      const n = rf.getNode(id);
      if (n) {
        rf.setCenter(
          n.position.x + (n.width ?? 106),
          n.position.y + (n.height ?? 29),
          { zoom: 1.1, duration: 500 },
        );
      }
    },
    [presentIds, rf],
  );

  const goGalaxy = React.useCallback(() => {
    setSelectedComponent(null);
    setSelectedNodeId(null);
    setFilters(defaultFilters());
  }, []);

  const selectedAc = selectedNodeId ? acById.get(selectedNodeId) ?? null : null;
  const overCap = detailMode && detailAcs.length > 300;

  return (
    <div className="flex flex-col">
      {/* breadcrumb + stats bar */}
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <nav className="flex items-center gap-1.5 text-sm">
          <button
            type="button"
            onClick={goGalaxy}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md px-2 py-1 transition-colors",
              detailMode
                ? "text-muted-foreground hover:bg-secondary/60 hover:text-foreground"
                : "font-medium text-foreground",
            )}
          >
            <Sparkles className="h-3.5 w-3.5 text-primary" />
            Component galaxy
          </button>
          {detailMode && (
            <>
              <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/60" />
              <span className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 font-medium text-foreground">
                <GitBranch className="h-3.5 w-3.5 text-primary" />
                {humanize(selectedComponent!)}
              </span>
            </>
          )}
        </nav>

        <div className="flex items-center gap-3">
          {overCap && (
            <span className="rounded-md border border-warning/40 bg-warning/10 px-2 py-1 text-[11px] text-warning">
              {detailAcs.length} ACs — narrow with filters for clarity
            </span>
          )}
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span>
              <span className="font-mono tabular-nums text-foreground">
                {displayNodes.length}
              </span>{" "}
              nodes
            </span>
            <span className="h-3 w-px bg-border" />
            <span>
              <span className="font-mono tabular-nums text-foreground">
                {baseEdges.length}
              </span>{" "}
              edges
            </span>
          </div>
          {detailMode && (
            <button
              type="button"
              onClick={goGalaxy}
              className="inline-flex items-center gap-1.5 rounded-md border border-border bg-card/60 px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Back
            </button>
          )}
        </div>
      </div>

      {/* canvas — explicit height (React Flow needs a sized parent to paint) */}
      <div className="panel relative h-[calc(100svh-16rem)] min-h-[600px] overflow-hidden p-0">
        {baseNodes.length === 0 ? (
          <div className="flex h-full items-center justify-center p-8">
            <EmptyState
              icon={<GitBranch className="h-6 w-6" />}
              title={
                detailMode ? "No ACs match the current filters" : "No components to map"
              }
              hint={
                detailMode
                  ? "Loosen the level or status filters, or clear the search."
                  : "The AC store appears to be empty."
              }
            />
          </div>
        ) : (
          <ReactFlow
            key={detailMode ? `detail:${selectedComponent}` : "galaxy"}
            nodes={displayNodes}
            edges={baseEdges}
            onNodeClick={onNodeClick}
            onPaneClick={() => setSelectedNodeId(null)}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.22 }}
            minZoom={0.15}
            maxZoom={2.5}
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
            <Controls
              showInteractive={false}
              className="!bottom-4 !left-4"
            />
            <MiniMap
              pannable
              zoomable
              className="!bottom-4 !right-4 !bg-card/80 !border !border-border/70"
              maskColor="hsl(160 26% 6% / 0.7)"
              nodeColor={(n) => {
                if (n.type === "componentNode")
                  return `hsl(${(n.data?.hsl as string) ?? "150 64% 52%"})`;
                const lvl = (n.data?.level as AcLevel) ?? "L2";
                return `hsl(${LEVEL_TONE[lvl]?.hsl ?? "150 64% 52%"})`;
              }}
              nodeStrokeWidth={0}
            />
          </ReactFlow>
        )}

        {/* floating controls */}
        <div className="pointer-events-none absolute left-4 top-4 z-10">
          <div className="pointer-events-auto">
            <FilterPanel
              filters={filters}
              onChange={setFilters}
              detailMode={detailMode}
              onReset={() => setFilters(defaultFilters())}
            />
          </div>
        </div>
        <div className="pointer-events-none absolute right-4 top-4 z-10">
          <div className="pointer-events-auto">
            <AtlasLegend detailMode={detailMode} />
          </div>
        </div>

        {/* detail drawer */}
        <DetailDrawer
          ac={selectedAc}
          presentIds={presentIds}
          onSelect={selectAc}
          onClose={() => setSelectedNodeId(null)}
          flowAppearances={selectedAc ? flowIndex?.[selectedAc.id] : undefined}
        />
      </div>
    </div>
  );
}

export function AtlasExplorer({
  acs,
  flowIndex,
}: {
  acs: AC[];
  flowIndex?: Record<string, FlowAppearance[]>;
}) {
  return (
    <ReactFlowProvider>
      <ExplorerInner acs={acs} flowIndex={flowIndex} />
    </ReactFlowProvider>
  );
}
