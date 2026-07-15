import * as React from "react";
import { Boxes, Layers, FileText, GitBranch } from "lucide-react";
import { getAtlas } from "@/lib/data/atlas";
import { componentTypes } from "@/lib/data/components";
import { PageHeader, SectionHeader, StatCard, Panel, Meter, Legend } from "@/components/ui/kit";
import { pct } from "@/lib/utils";
import {
  buildClusters,
  buildNamespaceFacets,
  buildOverview,
  typeColorMap,
} from "@/components/architecture/lib";
import { ComponentMap } from "@/components/architecture/component-map";
import { TypeBarChart } from "@/components/architecture/type-bar-chart";
import { AcFacet } from "@/components/architecture/ac-facet";

export const metadata = {
  title: "Architecture — Leafcutter Atlas",
  description: "The component map: 36 components clustered by type, cross-linked to the AC store.",
};

export default function ArchitecturePage() {
  const { components, acComponents, acs } = getAtlas();

  const types = componentTypes(components);
  const colors = typeColorMap(types);
  const clusters = buildClusters(components, acComponents, acs, colors);
  const facets = buildNamespaceFacets(acComponents, acs, components);
  const overview = buildOverview(clusters, components, acComponents, acs);

  const docPct = pct(overview.documented, overview.totalComponents);

  return (
    <div className="animate-fade-in">
      <PageHeader
        eyebrow="Leafcutter Atlas · Architecture"
        title="The component map"
        description="Every code component in the system, clustered by its role. A C4-container-style
          view read live from docs/components.json — filter by type, search, and open any node to
          trace its code, docs, and the acceptance criteria that specify it."
      >
        <div className="flex items-center gap-2 rounded-lg border border-border/70 bg-card/50 px-3.5 py-2 text-xs text-muted-foreground">
          <span className="tabular-nums text-foreground">{overview.totalComponents}</span> components
          <span className="text-muted-foreground/40">·</span>
          <span className="tabular-nums text-foreground">{overview.totalTypes}</span> types
        </div>
      </PageHeader>

      {/* Overview stats */}
      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="Components"
          value={overview.totalComponents}
          sub="registered in the architecture map"
          icon={<Boxes className="h-4 w-4" />}
          accent="150 64% 52%"
        />
        <StatCard
          label="Component types"
          value={overview.totalTypes}
          sub="distinct roles / clusters"
          icon={<Layers className="h-4 w-4" />}
          accent="168 60% 46%"
        />
        <StatCard
          label="Documented"
          value={`${overview.documented}/${overview.totalComponents}`}
          sub={
            <span className="flex items-center gap-2">
              <Meter value={docPct} className="w-16" />
              {docPct}% have an arch doc
            </span>
          }
          icon={<FileText className="h-4 w-4" />}
          accent="38 92% 58%"
        />
        <StatCard
          label="AC namespaces"
          value={overview.totalNamespaces}
          sub="spec vocabularies (a different axis)"
          icon={<GitBranch className="h-4 w-4" />}
          accent="265 60% 66%"
        />
      </div>

      {/* Breakdown + coverage */}
      <div className="mb-8 grid grid-cols-1 gap-4 lg:grid-cols-5">
        <Panel className="lg:col-span-3">
          <SectionHeader
            eyebrow="Distribution"
            title="Components by type"
            description="How the 36 components spread across the seven architectural roles."
          />
          <TypeBarChart data={overview.typeStats} />
        </Panel>

        <Panel className="lg:col-span-2">
          <SectionHeader
            eyebrow="Coverage"
            title="Documentation by type"
            description="Share of each cluster with a linked architecture doc."
          />
          <div className="space-y-3.5">
            {overview.typeStats.map((t) => {
              const p = pct(t.documented, t.count);
              return (
                <div key={t.type}>
                  <div className="mb-1 flex items-center justify-between text-xs">
                    <span className="inline-flex items-center gap-1.5 text-foreground">
                      <span className="h-2 w-2 rounded-[3px]" style={{ background: `hsl(${t.hsl})` }} />
                      {t.label}
                    </span>
                    <span className="tabular-nums text-muted-foreground">
                      {t.documented}/{t.count}
                    </span>
                  </div>
                  <Meter value={p} color={t.hsl} />
                </div>
              );
            })}
          </div>
        </Panel>
      </div>

      {/* Component map */}
      <section className="mb-10">
        <SectionHeader
          eyebrow="C4 · Container map"
          title="Component clusters"
          description="Grouped by type. Each node shows a live status dot; the doc glyph marks a
            documented component and the branch glyph shows its acceptance-criteria count. Click a
            node for the full detail."
          action={
            <Legend
              items={clusters.map((c) => ({ label: c.label, hsl: c.hsl }))}
              className="max-w-md justify-end"
            />
          }
        />
        <ComponentMap clusters={clusters} />
      </section>

      {/* AC-namespace facet */}
      <section>
        <SectionHeader
          eyebrow="The other axis"
          title="Acceptance-criteria namespaces"
          description="Where the specs live. These 13 AC-store namespaces are a separate vocabulary
            from the code components above — a few line up 1:1, most don't. Each bar breaks the
            namespace's ACs down by work status."
        />
        <AcFacet facets={facets} />
      </section>
    </div>
  );
}
