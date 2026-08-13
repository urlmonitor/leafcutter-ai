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
  useNodesState,
  type Node,
  type Edge,
} from "reactflow";
import "reactflow/dist/style.css";
import { buildFlowGraph, buildArtifactGraph } from "@/lib/data/graph";
import { layoutArtifactGraph } from "@/lib/data/artifact-layout";
import {
  renderGraphPng,
  copyBlobToClipboard,
  downloadBlob,
  type PngNode,
  type PngEdge,
} from "@/lib/png-export";
import { WORK_STATUS_TONE } from "@/lib/status";
import { cn } from "@/lib/utils";
import type { Flow, GraphEdge, MockData, SelfRel, WorkStatus } from "@/lib/data/types";

interface XY {
  x: number;
  y: number;
}
import { flowNodeTypes } from "./flow-nodes";
import {
  edgeStyle,
  artifactEdgeStyle,
  INGESTABILITY_LEGEND,
  ARTIFACT_GROUP_HSL,
  ARTIFACT_GROUP_LABEL,
} from "@/components/atlas/edges";
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

// ---------------------------------------------------------------------------
// ArtifactExplorerInner — React Flow canvas for the authored artifact graph.
// Nodes are positioned by `rank` (column index) and `row` (index within rank).
// Edge stroke/dash is keyed on enforcement level rather than GraphEdgeKind.
// ---------------------------------------------------------------------------
function ArtifactExplorerInner({ flow }: { flow: Flow }) {
  const graph = React.useMemo(() => buildArtifactGraph(flow), [flow]);

  // Crossing-reduced layered layout. Self-referencing edges (AC -> AC) are
  // lifted out and badged on the card instead of drawn as degenerate loops.
  const layout = React.useMemo(
    () => layoutArtifactGraph(graph.nodes, graph.edges),
    [graph],
  );

  // Nodes are stateful (useNodesState) so the user can DRAG them to refine the
  // view; positions reset to the computed layout on flow change or Reset click.
  const initialNodes = React.useMemo<Node[]>(
    () =>
      graph.nodes.map((n) => ({
        id: n.id,
        type: "artifactNode",
        position: layout.positions.get(n.id) ?? { x: 0, y: 0 },
        data: {
          label: n.label,
          group: n.group,
          path: (n.meta?.path as string) ?? "",
          key: (n.meta?.key as string) ?? "",
          note: (n.meta?.note as string | undefined),
          selfRels: layout.selfRels.get(n.id),
        },
        draggable: true,
      })),
    [graph, layout],
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  // Re-seed positions when the underlying graph changes (e.g. switching flows).
  React.useEffect(() => {
    setNodes(initialNodes);
  }, [initialNodes, setNodes]);

  const resetLayout = React.useCallback(() => setNodes(initialNodes), [initialNodes, setNodes]);

  // Selected edge — surfaces `note` and `cardinality`, the caveats that make
  // an "enforced" edge safe or unsafe to actually build on.
  const [selectedEdge, setSelectedEdge] = React.useState<GraphEdge | null>(null);
  const onEdgeClick = React.useCallback(
    (_evt: React.MouseEvent, edge: Edge) => {
      setSelectedEdge(layout.edges.find((e) => e.id === edge.id) ?? null);
    },
    [layout],
  );

  // --- PNG export -------------------------------------------------------
  // Redraws from the CURRENT node positions, so the image matches what the
  // user sees (including any dragging) rather than the pristine layout.
  const [exportMsg, setExportMsg] = React.useState<string | null>(null);

  const buildPng = React.useCallback(async () => {
    const pngNodes: PngNode[] = nodes.map((n) => ({
      id: n.id,
      label: (n.data as { label: string }).label,
      group: (n.data as { group: string }).group,
      x: n.position.x,
      y: n.position.y,
      selfRels: (n.data as { selfRels?: SelfRel[] }).selfRels,
    }));
    // layout.edges (not graph.edges) so the PNG matches the canvas: self-edges
    // are badged on their card, not drawn.
    const pngEdges: PngEdge[] = layout.edges.map((e) => ({
      source: e.source,
      target: e.target,
      rel: e.rel ?? e.label,
      field: e.field,
      enforcement: e.enforcement,
      shape: e.shape,
      status: e.status,
    }));
    const selfCount = Array.from(layout.selfRels.values()).reduce(
      (sum, arr) => sum + arr.length,
      0,
    );
    return await renderGraphPng(pngNodes, pngEdges, flow.name, {
      sourceDoc: flow.filePath,
      nodeCount: graph.nodes.length,
      edgeCount: pngEdges.length,
      selfCount,
    });
  }, [nodes, graph, layout, flow.name, flow.filePath]);

  const flash = (msg: string) => {
    setExportMsg(msg);
    window.setTimeout(() => setExportMsg(null), 2600);
  };

  const handleCopyPng = React.useCallback(async () => {
    try {
      await copyBlobToClipboard(await buildPng());
      flash("Copied PNG to clipboard");
    } catch (err) {
      // Clipboard image writes are Chromium-only — fall back to a download so
      // the user still gets the image instead of a dead button.
      try {
        downloadBlob(await buildPng(), `${flow.id.replace(/\//g, "-")}.png`);
        flash("Clipboard unavailable — downloaded instead");
      } catch {
        flash(err instanceof Error ? err.message : "PNG export failed");
      }
    }
  }, [buildPng, flow.id]);

  const handleDownloadPng = React.useCallback(async () => {
    try {
      downloadBlob(await buildPng(), `${flow.id.replace(/\//g, "-")}.png`);
      flash("PNG downloaded");
    } catch (err) {
      flash(err instanceof Error ? err.message : "PNG export failed");
    }
  }, [buildPng, flow.id]);

  const edges = React.useMemo<Edge[]>(() => {
    // Edges sharing a node pair land their labels at the same point and paint
    // over each other — this previously erased TRACES_TO (enforced+clean)
    // under TICKET_DEPENDS_ON (unenforced). Stagger each duplicate's label
    // along the curve so every relationship stays readable.
    const pairSeen = new Map<string, number>();

    return layout.edges.map((e) => {
      const enforcement = e.enforcement ?? "none";
      const status = e.status ?? "present";
      const spec = artifactEdgeStyle(enforcement, e.shape ?? "clean", status);
      const pairKey = [e.source, e.target].sort().join("::");
      const nth = pairSeen.get(pairKey) ?? 0;
      pairSeen.set(pairKey, nth + 1);

      // Field first (what you grep for), relationship second (the abstraction).
      // An absent edge has no field to grep, so it captions the relation it
      // WOULD encode, marked as missing rather than as a weak link.
      const caption = status === "absent"
        ? `${spec.warnGlyph} ${e.rel ?? e.label ?? ""} — missing`
        : e.field && e.field !== "—"
          ? `${e.field}${spec.warnGlyph ? ` ${spec.warnGlyph}` : ""}`
          : `${e.rel ?? e.label ?? ""}${spec.warnGlyph ? ` ${spec.warnGlyph}` : ""}`;

      return {
        id: e.id,
        source: e.source,
        target: e.target,
        animated: false,
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: `hsl(${spec.hsl})`,
          width: 13,
          height: 13,
        },
        style: {
          stroke: `hsl(${spec.hsl})`,
          strokeWidth: spec.ingestability === "ingestable" ? 1.7 : 1.3,
          opacity: spec.ingestability === "untrusted" ? 0.55 : 0.85,
          // A long open dash reads as "this line isn't really there" — a
          // second, non-colour channel so the gap survives greyscale printing
          // and the PNG export.
          strokeDasharray: spec.ingestability === "absent"
            ? "2 7"
            : spec.dashed
              ? "5 4"
              : undefined,
        },
        label: caption,
        labelShowBg: true,
        labelStyle: {
          fill: `hsl(${spec.hsl})`,
          fontSize: 9,
          fontWeight: 600,
        },
        labelBgStyle: {
          fill: "hsl(158 12% 11%)",
          // Semi-transparent so residual overlap is visible rather than
          // silently destructive.
          fillOpacity: 0.75,
        },
        labelBgPadding: [3, 4] as [number, number],
        pathOptions: { curvature: 0.25 + nth * 0.22 },
        data: {
          rel: e.rel,
          field: e.field,
          enforcement,
          shape: e.shape,
          status,
          cardinality: e.cardinality,
          note: e.note,
          ingestability: spec.ingestability,
        },
        labelBgBorderRadius: 3,
        interactionWidth: 18,
        selectable: true,
      } as Edge;
    });
  }, [layout]);

  return (
    <div className="panel relative h-[calc(100svh-20rem)] min-h-[560px] overflow-hidden p-0">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgeClick={onEdgeClick}
        onPaneClick={() => setSelectedEdge(null)}
        nodeTypes={flowNodeTypes}
        fitView
        fitViewOptions={{ padding: 0.18, minZoom: 0.3 }}
        minZoom={0.15}
        maxZoom={2.5}
        nodesDraggable
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
          nodeStrokeWidth={0}
        />
      </ReactFlow>

      {/* Export / layout toolbar */}
      <div className="absolute left-4 top-4 z-10 flex items-center gap-2">
        <button
          type="button"
          onClick={handleCopyPng}
          className="rounded-lg border border-border/70 bg-card/90 px-2.5 py-1.5 text-[11px] font-medium text-foreground/90 backdrop-blur transition-colors hover:bg-card"
          title="Copy the graph as a PNG image to your clipboard"
        >
          Copy PNG
        </button>
        <button
          type="button"
          onClick={handleDownloadPng}
          className="rounded-lg border border-border/70 bg-card/90 px-2.5 py-1.5 text-[11px] font-medium text-foreground/90 backdrop-blur transition-colors hover:bg-card"
          title="Download the graph as a PNG file"
        >
          Download
        </button>
        <button
          type="button"
          onClick={resetLayout}
          className="rounded-lg border border-border/70 bg-card/90 px-2.5 py-1.5 text-[11px] font-medium text-muted-foreground transition-colors hover:bg-card hover:text-foreground"
          title="Restore the computed layout, discarding any dragging"
        >
          Reset layout
        </button>
        {exportMsg && (
          <span className="rounded-md bg-card/90 px-2 py-1 text-[10px] text-muted-foreground backdrop-blur">
            {exportMsg}
          </span>
        )}
      </div>

      {/* Artifact graph legend */}
      <div className="pointer-events-none absolute right-4 top-4 z-10">
        <div className="pointer-events-auto panel max-w-xs p-3.5">
          <div className="eyebrow mb-2">Legend</div>
          <div className="mb-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground/80">
            Node group
          </div>
          <div className="mb-3 flex flex-wrap gap-x-3 gap-y-1.5">
            {Object.entries(ARTIFACT_GROUP_LABEL).map(([group, label]) => (
              <span
                key={group}
                className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground"
              >
                <span
                  className="h-2 w-[3px] rounded-full"
                  style={{ background: `hsl(${ARTIFACT_GROUP_HSL[group]})` }}
                />
                {label}
              </span>
            ))}
          </div>
          <div className="mb-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground/80">
            Edge trust
          </div>
          <div className="flex flex-col gap-1">
            {INGESTABILITY_LEGEND.map((row) => (
              <span
                key={row.key}
                className="inline-flex items-baseline gap-1.5 text-[11px] text-muted-foreground"
              >
                <svg width="20" height="6" className="shrink-0 overflow-visible">
                  <line
                    x1="0" y1="3" x2="20" y2="3"
                    stroke={`hsl(${row.hsl})`}
                    strokeWidth="2"
                    strokeDasharray={
                      row.key === "absent"
                        ? "2 7"
                        : row.key === "untrusted"
                          ? "4 3"
                          : undefined
                    }
                  />
                </svg>
                <span className="text-foreground/85">{row.label}</span>
                <span className="text-[9px] text-muted-foreground/70">{row.hint}</span>
              </span>
            ))}
          </div>
          <p className="mt-2.5 text-[9px] leading-relaxed text-muted-foreground/70">
            Labels show the <span className="font-mono">field</span> that encodes each edge.
            ⚠ ambiguous · ~ freetext · ∅ often-empty — these need partitioning before
            ingestion even when enforced. Dashes mark derived or untrusted links.
            A red ✗ line is a relation the repo does NOT have — recorded so a gap
            is distinguishable from an omission, never traversable.
            Click an edge for its full trust record; ↺ on a card lists
            self-referencing relationships.
          </p>

          {selectedEdge && (() => {
            const spec = artifactEdgeStyle(
              selectedEdge.enforcement ?? "none",
              selectedEdge.shape ?? "clean",
              selectedEdge.status ?? "present",
            );
            return (
              <div className="mt-3 border-t border-border/40 pt-2.5">
                <div className="mb-1.5 flex items-center justify-between gap-2">
                  <span
                    className="text-[11px] font-semibold"
                    style={{ color: `hsl(${spec.hsl})` }}
                  >
                    {selectedEdge.rel}
                  </span>
                  <button
                    type="button"
                    onClick={() => setSelectedEdge(null)}
                    className="text-[10px] text-muted-foreground hover:text-foreground"
                  >
                    close
                  </button>
                </div>
                <dl className="space-y-1 text-[9.5px] leading-relaxed">
                  <div>
                    <dt className="inline text-muted-foreground/70">field </dt>
                    <dd className="inline font-mono text-foreground/85">
                      {selectedEdge.field ?? "—"}
                    </dd>
                  </div>
                  <div>
                    <dt className="inline text-muted-foreground/70">trust </dt>
                    <dd className="inline text-foreground/85">
                      {selectedEdge.status === "absent"
                        ? "no such link"
                        : `${selectedEdge.enforcement} · ${selectedEdge.shape}`}{" "}
                      <span style={{ color: `hsl(${spec.hsl})` }}>
                        ({spec.ingestability})
                      </span>
                    </dd>
                  </div>
                  <div>
                    <dt className="inline text-muted-foreground/70">cardinality </dt>
                    <dd className="inline text-foreground/85">
                      {selectedEdge.cardinality ?? "—"}
                    </dd>
                  </div>
                  {selectedEdge.note && (
                    <div className="pt-0.5 text-muted-foreground">
                      {selectedEdge.note}
                    </div>
                  )}
                </dl>
              </div>
            );
          })()}
        </div>
      </div>
    </div>
  );
}

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
  // Authored artifact graphs have graphNodes/graphEdges attached; use a dedicated
  // renderer that lays out by rank/row instead of the step/branch/AC column layout.
  const isArtifact = Boolean(flow.graphNodes && flow.graphNodes.length > 0);
  return (
    <ReactFlowProvider>
      {isArtifact ? (
        <ArtifactExplorerInner flow={flow} />
      ) : (
        <ExplorerInner
          flow={flow}
          mock={mock}
          flowNames={flowNames}
          screenTitles={screenTitles}
          onDrill={onDrill}
        />
      )}
    </ReactFlowProvider>
  );
}
