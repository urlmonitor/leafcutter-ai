"use client";

import * as React from "react";
import {
  ReactFlow,
  Background,
  Controls,
  Handle,
  Position,
  MarkerType,
  ReactFlowProvider,
  type Node,
  type Edge,
  type NodeProps,
} from "reactflow";
import "reactflow/dist/style.css";
import { X, Cpu, Sparkles, GitBranch, Skull } from "lucide-react";
import type { AgentDef } from "@/lib/data/types";
import { buildAgentTopology } from "@/lib/data/graph";
import { CATEGORY_ORDER, CATEGORY_TONE, catKey, catTone, agentLabel } from "./shared";
import { Legend } from "@/components/ui/kit";
import { cn } from "@/lib/utils";

/* ---------- layout ---------- */
const COL_W = 210;
const ROW_H = 76;
const GROUP_GAP = 56;
const MAX_ROWS = 8;

interface NodeData {
  agent: AgentDef;
  dim: boolean;
}

function computeNodes(agents: AgentDef[], selectedId: string | null, neighbors: Set<string>): Node<NodeData>[] {
  const byCat = new Map<string, AgentDef[]>();
  for (const a of agents) {
    const k = catKey(a);
    (byCat.get(k) ?? byCat.set(k, []).get(k)!).push(a);
  }
  const nodes: Node<NodeData>[] = [];
  let x = 0;
  for (const cat of CATEGORY_ORDER) {
    const members = (byCat.get(cat) ?? []).sort(
      (a, b) => (a.tier ?? "").localeCompare(b.tier ?? "") || a.name.localeCompare(b.name),
    );
    if (!members.length) continue;
    const subcols = Math.max(1, Math.ceil(members.length / MAX_ROWS));
    members.forEach((agent, idx) => {
      const sub = Math.floor(idx / MAX_ROWS);
      const row = idx % MAX_ROWS;
      const dim = selectedId != null && agent.id !== selectedId && !neighbors.has(agent.id);
      nodes.push({
        id: agent.id,
        type: "agent",
        position: { x: x + sub * COL_W, y: row * ROW_H + 44 },
        data: { agent, dim },
        selected: agent.id === selectedId,
      });
    });
    x += subcols * COL_W + GROUP_GAP;
  }
  return nodes;
}

/* ---------- custom node ---------- */
function AgentNode({ data, selected }: NodeProps<NodeData>) {
  const { agent, dim } = data;
  const tone = catTone(agent);
  return (
    <div
      className={cn(
        "group relative w-[176px] rounded-lg border bg-card/95 px-2.5 py-2 shadow-md transition-all",
        selected ? "ring-2" : "hover:border-primary/40",
        dim && "opacity-25",
      )}
      style={{
        borderColor: selected ? `hsl(${tone.hsl})` : "hsl(var(--border))",
        boxShadow: selected ? `0 0 0 4px hsl(${tone.hsl} / 0.12)` : undefined,
      }}
    >
      <Handle type="target" position={Position.Left} className="!h-1.5 !w-1.5 !border-0 !bg-border" />
      <div className="flex items-center gap-2">
        <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: `hsl(${tone.hsl})` }} />
        <span className="truncate text-xs font-medium text-foreground">{agent.name}</span>
      </div>
      <div className="mt-0.5 flex items-center gap-1.5 pl-4">
        <span className="text-[9px] uppercase tracking-wide text-muted-foreground">
          {agent.model ?? "—"}
        </span>
        {agent.deprecated && <span className="text-[9px] text-destructive">deprecated</span>}
      </div>
      <Handle type="source" position={Position.Right} className="!h-1.5 !w-1.5 !border-0 !bg-border" />
    </div>
  );
}

const nodeTypes = { agent: AgentNode };

/* ---------- side panel ---------- */
function DetailRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="border-t border-border/50 py-2.5">
      <div className="eyebrow mb-1">{label}</div>
      <div className="text-xs text-foreground/90">{children}</div>
    </div>
  );
}

function AgentPanel({
  agent,
  agents,
  onClose,
  onSelect,
}: {
  agent: AgentDef;
  agents: AgentDef[];
  onClose: () => void;
  onSelect: (id: string) => void;
}) {
  const tone = catTone(agent);
  const chip = (id: string) => (
    <button
      key={id}
      onClick={() => onSelect(id)}
      className="inline-flex items-center rounded-full border border-border/70 bg-secondary/40 px-2 py-0.5 text-[11px] text-foreground/85 transition-colors hover:border-primary/50 hover:text-foreground"
    >
      {agentLabel(agents, id)}
    </button>
  );
  return (
    <div className="absolute right-3 top-3 z-20 flex max-h-[calc(100%-1.5rem)] w-[19rem] flex-col overflow-hidden rounded-xl border border-border bg-popover/95 shadow-2xl backdrop-blur">
      <div
        className="flex items-start justify-between gap-2 border-b border-border/60 p-4"
        style={{ background: `hsl(${tone.hsl} / 0.08)` }}
      >
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: `hsl(${tone.hsl})` }} />
            <span className="truncate text-sm font-semibold text-foreground">{agent.name}</span>
          </div>
          <div className="mt-1 font-mono text-[11px] text-muted-foreground">{agent.id}</div>
        </div>
        <button
          onClick={onClose}
          className="shrink-0 rounded-md p-1 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
          aria-label="Close"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="overflow-y-auto px-4 pb-4">
        <div className="flex flex-wrap gap-1.5 py-3">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-border/70 bg-secondary/40 px-2 py-0.5 text-[11px] text-foreground/85">
            <span className="h-1.5 w-1.5 rounded-full" style={{ background: `hsl(${tone.hsl})` }} />
            {tone.label}
          </span>
          {agent.tier && (
            <span className="inline-flex items-center rounded-full border border-border/70 bg-secondary/40 px-2 py-0.5 text-[11px] text-foreground/85">
              {agent.tier}
            </span>
          )}
          {agent.model && (
            <span className="inline-flex items-center gap-1 rounded-full border border-border/70 bg-secondary/40 px-2 py-0.5 text-[11px] text-foreground/85">
              <Cpu className="h-3 w-3" />
              {agent.model}
            </span>
          )}
          {agent.isTicketPhase && (
            <span className="inline-flex items-center gap-1 rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 text-[11px] text-primary">
              <Sparkles className="h-3 w-3" />
              ticket phase
            </span>
          )}
          {agent.deprecated && (
            <span className="inline-flex items-center gap-1 rounded-full border border-destructive/30 bg-destructive/10 px-2 py-0.5 text-[11px] text-destructive">
              <Skull className="h-3 w-3" />
              deprecated
            </span>
          )}
        </div>

        {agent.description && (
          <p className="pb-1 text-xs leading-relaxed text-muted-foreground">{agent.description}</p>
        )}

        {agent.role && <DetailRow label="Role">{agent.role}</DetailRow>}
        {agent.produces && <DetailRow label="Produces">{agent.produces}</DetailRow>}

        <DetailRow label={`Spawns (${agent.spawnAllowlist.length})`}>
          {agent.spawnAllowlist.length ? (
            <div className="flex flex-wrap gap-1.5">{agent.spawnAllowlist.map(chip)}</div>
          ) : (
            <span className="text-muted-foreground">— leaf agent, spawns nothing</span>
          )}
        </DetailRow>

        <DetailRow label={`Spawned by (${agent.spawnedBy.length})`}>
          {agent.spawnedBy.length ? (
            <div className="flex flex-wrap gap-1.5">{agent.spawnedBy.map(chip)}</div>
          ) : (
            <span className="text-muted-foreground">—</span>
          )}
        </DetailRow>

        {agent.skillsUsed.length > 0 && (
          <DetailRow label={`Skills used (${agent.skillsUsed.length})`}>
            <div className="flex flex-wrap gap-1.5">
              {agent.skillsUsed.map((s) => (
                <span
                  key={s}
                  className="inline-flex items-center gap-1 rounded-full border border-border/70 bg-muted/40 px-2 py-0.5 font-mono text-[10px] text-muted-foreground"
                >
                  <GitBranch className="h-2.5 w-2.5" />
                  {s}
                </span>
              ))}
            </div>
          </DetailRow>
        )}
      </div>
    </div>
  );
}

/* ---------- main graph ---------- */
function Graph({ agents }: { agents: AgentDef[] }) {
  const [selectedId, setSelectedId] = React.useState<string | null>(null);

  const topo = React.useMemo(() => buildAgentTopology(agents), [agents]);

  const neighbors = React.useMemo(() => {
    const set = new Set<string>();
    if (!selectedId) return set;
    for (const e of topo.edges) {
      if (e.source === selectedId) set.add(e.target);
      if (e.target === selectedId) set.add(e.source);
    }
    return set;
  }, [selectedId, topo.edges]);

  const nodes = React.useMemo(
    () => computeNodes(agents, selectedId, neighbors),
    [agents, selectedId, neighbors],
  );

  const edges: Edge[] = React.useMemo(() => {
    return topo.edges.map((e) => {
      const on = selectedId != null && (e.source === selectedId || e.target === selectedId);
      const off = selectedId != null && !on;
      const srcAgent = agents.find((a) => a.id === e.source);
      const hsl = srcAgent ? catTone(srcAgent).hsl : "150 8% 55%";
      return {
        id: e.id,
        source: e.source,
        target: e.target,
        type: "smoothstep",
        animated: on,
        style: {
          stroke: `hsl(${hsl} / ${off ? 0.08 : on ? 0.9 : 0.28})`,
          strokeWidth: on ? 2 : 1.2,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 14,
          height: 14,
          color: `hsl(${hsl} / ${off ? 0.1 : on ? 0.9 : 0.35})`,
        },
      } satisfies Edge;
    });
  }, [topo.edges, selectedId, agents]);

  const selected = selectedId ? agents.find((a) => a.id === selectedId) ?? null : null;

  return (
    <div className="relative h-[560px] w-full overflow-hidden rounded-xl border border-border/80 bg-background/40">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={(_, n) => setSelectedId(n.id)}
        onPaneClick={() => setSelectedId(null)}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        minZoom={0.2}
        maxZoom={1.75}
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
      >
        <Background color="hsl(156 16% 16%)" gap={22} size={1} />
        <Controls showInteractive={false} />
      </ReactFlow>

      {/* legend */}
      <div className="pointer-events-none absolute left-3 top-3 z-10 rounded-lg border border-border/70 bg-popover/85 px-3 py-2 backdrop-blur">
        <Legend
          items={CATEGORY_ORDER.filter((c) => agents.some((a) => catKey(a) === c)).map((c) => ({
            label: CATEGORY_TONE[c].label,
            hsl: CATEGORY_TONE[c].hsl,
          }))}
        />
      </div>

      {selected && (
        <AgentPanel
          agent={selected}
          agents={agents}
          onClose={() => setSelectedId(null)}
          onSelect={(id) => setSelectedId(id)}
        />
      )}
    </div>
  );
}

export function Constellation({ agents }: { agents: AgentDef[] }) {
  return (
    <ReactFlowProvider>
      <Graph agents={agents} />
    </ReactFlowProvider>
  );
}
