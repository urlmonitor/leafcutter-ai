import { Workflow, Waypoints, ListTree, Users } from "lucide-react";
import { getAtlas } from "@/lib/data/atlas";
import { PageHeader, Panel, SectionHeader, StatCard } from "@/components/ui/kit";
import { StageFlow } from "@/components/pipeline/stage-flow";
import { PhaseChain, type ChainTicket } from "@/components/pipeline/phase-chain";
import { Constellation } from "@/components/pipeline/constellation";
import { Roster } from "@/components/pipeline/roster";

/** Rich, representative DONE tickets to showcase the real phase chain. */
function pickChainTickets(atlas: ReturnType<typeof getAtlas>): ChainTicket[] {
  const activeCount = (t: { agents: { status: string }[] }) =>
    t.agents.filter((a) => a.status !== "not_needed").length;

  return atlas.tickets
    .filter((t) => t.status === "done" && activeCount(t) >= 5)
    .sort((a, b) => activeCount(b) - activeCount(a) || (b.created ?? "").localeCompare(a.created ?? ""))
    .slice(0, 12)
    .map((t) => ({ slug: t.slug, title: t.title, epic: t.epic, agents: t.agents }));
}

export default function PipelinePage() {
  const atlas = getAtlas();
  const agents = atlas.agents;

  const phaseAgents = agents.filter((a) => a.isTicketPhase && !a.deprecated).length;
  const opusAgents = agents.filter((a) => a.model === "opus").length;
  const spawnEdges = agents.reduce(
    (n, a) => n + a.spawnAllowlist.filter((t) => agents.some((x) => x.id === t)).length,
    0,
  );
  const chainTickets = pickChainTickets(atlas);

  return (
    <div className="animate-fade-in space-y-12">
      <PageHeader
        eyebrow="The Pipeline"
        title="How Leafcutter builds software"
        description="Leafcutter is an AC-driven, agent-orchestrated dev workflow. Every change flows through four stages — Plan, Select, Build, Finalize — driven by a roster of specialized agents. This view maps that flow, then lets you go deep."
      >
        <div className="hidden items-center gap-2 rounded-lg border border-border/70 bg-card/60 px-3 py-2 text-xs text-muted-foreground sm:flex">
          <Workflow className="h-4 w-4 text-primary" />
          Read live from the agent registry
        </div>
      </PageHeader>

      {/* stat strip */}
      <section className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Agents in the roster" value={agents.length} icon={<Users className="h-4 w-4" />} accent="150 64% 52%" sub="specialized, single-purpose" />
        <StatCard label="Ticket phase agents" value={phaseAgents} icon={<ListTree className="h-4 w-4" />} accent="168 60% 46%" sub="run inside a build" />
        <StatCard label="Spawn relationships" value={spawnEdges} icon={<Waypoints className="h-4 w-4" />} accent="200 78% 60%" sub="who may dispatch whom" />
        <StatCard label="Opus-tier agents" value={opusAgents} icon={<Workflow className="h-4 w-4" />} accent="265 60% 66%" sub="deep-reasoning work" />
      </section>

      {/* 1 — four-stage flow */}
      <section>
        <SectionHeader
          eyebrow="The 60-second version"
          title="Four stages, end to end"
          description="An idea becomes acceptance criteria, a ranked AC becomes a ticket, the ticket is built through a TDD phase chain, then the feature is merged, verified, and archived."
        />
        <StageFlow agents={agents} />
      </section>

      {/* 2 — ticket phase chain */}
      <section>
        <SectionHeader
          eyebrow="Stage 3, on real data"
          title="A ticket's phase chain"
          description="Inside /build-feature, ticket-supervisor drives a single ticket through its ordered phase agents. Here is that sequence on real, completed tickets — colored by each phase's recorded sign-off status."
        />
        <Panel>
          {chainTickets.length > 0 ? (
            <PhaseChain tickets={chainTickets} agents={agents} />
          ) : (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No completed tickets with a rich phase chain were found in this repo.
            </p>
          )}
        </Panel>
      </section>

      {/* 3 — agent constellation */}
      <section>
        <SectionHeader
          eyebrow="Who dispatches whom"
          title="The agent constellation"
          description="Every agent, clustered by category. Edges are spawn relationships (arrowheads point to the spawned agent). Click a node to inspect its role, model, skills, and its place in the topology. Per ADR-006, all dispatch is one hop deep."
        />
        <Constellation agents={agents} />
      </section>

      {/* 4 — roster */}
      <section>
        <SectionHeader
          eyebrow="The full roster"
          title={`All ${agents.length} agents`}
          description="Search and filter the complete registry. A ✦ marks ticket-phase agents; deprecated agents are struck through."
        />
        <Roster agents={agents} />
      </section>
    </div>
  );
}
