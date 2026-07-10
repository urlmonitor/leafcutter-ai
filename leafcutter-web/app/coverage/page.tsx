import * as React from "react";
import {
  ShieldCheck,
  ShieldAlert,
  Layers,
  FlaskConical,
  TriangleAlert,
} from "lucide-react";
import { getAtlas } from "@/lib/data/atlas";
import { LEVEL_TONE } from "@/lib/status";
import { fmt, humanize } from "@/lib/utils";
import {
  PageHeader,
  Panel,
  SectionHeader,
  StatCard,
  Badge,
} from "@/components/ui/kit";
import { Reveal } from "@/components/pulse/reveal";
import { CoverageHistogram } from "@/components/coverage/coverage-histogram";
import { LevelCoverage } from "@/components/coverage/level-coverage";
import { ComponentCoverage } from "@/components/coverage/component-coverage";
import { CoverageExplorer } from "@/components/coverage/coverage-explorer";
import { GapsCallout } from "@/components/coverage/gaps-callout";
import {
  coverageToneHsl,
  guardedPct,
  type CoverageBar,
  type CoverageRow,
  type HistogramDatum,
} from "@/components/coverage/shared";
import type { AcLevel } from "@/lib/data/types";

// Green ramp for the histogram; the "0" bucket is red — an unguarded population.
const HIST_HSL: Record<string, string> = {
  "0": "356 72% 56%",
  "1": "168 60% 46%",
  "2": "150 64% 52%",
  "3+": "150 60% 40%",
};

export default function CoveragePage() {
  const { acs, coverage } = getAtlas();

  const { totalAcs, guarded, guardedPct: gp, rolledUpGuarded, totalTestFiles } = coverage;
  const unguarded = totalAcs - guarded;

  // ---- Distribution ----
  const histogram: HistogramDatum[] = coverage.histogram.map((h) => ({
    bucket: h.bucket,
    count: h.count,
    hsl: HIST_HSL[h.bucket] ?? "150 64% 52%",
  }));
  const zeroCount = coverage.histogram.find((h) => h.bucket === "0")?.count ?? 0;

  // ---- By level ----
  const levelBars: CoverageBar[] = coverage.byLevel.map((l) => ({
    key: l.level,
    label: LEVEL_TONE[l.level as AcLevel].label,
    total: l.total,
    guarded: l.guarded,
    pct: guardedPct(l.guarded, l.total),
    hsl: LEVEL_TONE[l.level as AcLevel].hsl,
  }));

  // ---- By component (drop empty namespaces; tint by coverage health) ----
  const componentBars: CoverageBar[] = coverage.byComponent
    .filter((c) => c.total > 0)
    .map((c) => {
      const p = guardedPct(c.guarded, c.total);
      return {
        key: c.component,
        label: humanize(c.component),
        total: c.total,
        guarded: c.guarded,
        pct: p,
        hsl: coverageToneHsl(p),
      };
    });

  // ---- Explorer rows (trim each AC to the coverage shape) ----
  const rows: CoverageRow[] = acs.map((a) => ({
    id: a.id,
    title: a.title || a.id,
    component: a.component,
    level: a.level,
    workStatus: a.workStatus,
    workStatusRaw: a.workStatusRaw,
    testCount: a.testCount ?? 0,
    testRolledUpCount: a.testRolledUpCount ?? 0,
    testRefs: a.testRefs ?? [],
    isLeaf: a.isLeaf ?? true,
  }));
  const componentIds = Array.from(new Set(rows.map((r) => r.component))).sort();

  // ---- Coverage gaps: DONE ACs with zero direct guards ----
  const doneUnguarded = rows
    .filter((r) => r.workStatus === "done" && r.testCount === 0)
    .sort((a, b) => {
      // leaves first (direct risk), then by level depth, then id
      if (a.isLeaf !== b.isLeaf) return a.isLeaf ? -1 : 1;
      if (a.level !== b.level) return b.level.localeCompare(a.level);
      return a.id.localeCompare(b.id);
    });

  const stats = [
    {
      label: "Directly guarded",
      value: `${gp}%`,
      sub: `${fmt(guarded)} of ${fmt(totalAcs)} criteria`,
      icon: <ShieldCheck className="h-4 w-4" />,
      accent: coverageToneHsl(gp),
    },
    {
      label: "Unguarded",
      value: fmt(unguarded),
      sub: `${guardedPct(unguarded, totalAcs)}% have zero direct tests`,
      icon: <ShieldAlert className="h-4 w-4" />,
      accent: "356 72% 56%",
    },
    {
      label: "Guarded incl. children",
      value: fmt(rolledUpGuarded),
      sub: "rolled up through descendants",
      icon: <Layers className="h-4 w-4" />,
      accent: "265 60% 66%",
    },
    {
      label: "Test files",
      value: fmt(totalTestFiles),
      sub: "scanned for AC ids",
      icon: <FlaskConical className="h-4 w-4" />,
      accent: "168 60% 46%",
    },
  ];

  return (
    <div className="animate-fade-in space-y-12">
      <PageHeader
        eyebrow="Coverage · test guarding"
        title="How many tests guard each AC"
        description="Coverage here means a test that names an acceptance criterion by id. Only a small fraction of the store is guarded — this view exists to show exactly where the gaps are, not to reassure."
      >
        <div className="flex flex-col items-end gap-1.5">
          <Badge
            className="!border-destructive/40 !bg-destructive/10 !text-destructive"
            dot
          >
            <TriangleAlert className="h-3 w-3" />
            {gp}% guarded
          </Badge>
          <span className="eyebrow">Coverage is low</span>
        </div>
      </PageHeader>

      {/* ---- Headline stats ---- */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {stats.map((s, i) => (
          <Reveal key={s.label} delay={0.04 * i} className="h-full">
            <StatCard
              className="h-full"
              label={s.label}
              value={s.value}
              sub={s.sub}
              icon={s.icon}
              accent={s.accent}
            />
          </Reveal>
        ))}
      </div>

      {/* ---- Distribution ---- */}
      <Reveal>
        <Panel>
          <SectionHeader
            eyebrow="Distribution"
            title="Tests per acceptance criterion"
            description="Every criterion counted by how many tests directly guard it."
            action={
              <span className="hidden items-center gap-1.5 text-xs text-muted-foreground sm:inline-flex">
                <Layers className="h-3.5 w-3.5" />
                {fmt(totalAcs)} criteria
              </span>
            }
          />
          <CoverageHistogram data={histogram} />
          <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
            <span className="font-semibold text-destructive">{fmt(zeroCount)} criteria</span> have{" "}
            zero guarding tests — {guardedPct(zeroCount, totalAcs)}% of the entire store. Of the
            guarded remainder, most carry just a single test; only{" "}
            {fmt((coverage.histogram.find((h) => h.bucket === "3+")?.count ?? 0))} have three or more.
          </p>
        </Panel>
      </Reveal>

      {/* ---- By level + by component ---- */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Reveal delay={0.05}>
          <Panel className="h-full">
            <SectionHeader
              eyebrow="By level"
              title="Where in the pyramid coverage lives"
              description="Guarded share from customer value (L0) down to edge cases (L3)."
            />
            <LevelCoverage bars={levelBars} />
          </Panel>
        </Reveal>

        <Reveal delay={0.1}>
          <Panel className="h-full">
            <SectionHeader
              eyebrow="By component"
              title="Which surfaces are exposed"
              description="Guarded percentage per component — several sit at zero."
            />
            <ComponentCoverage bars={componentBars} />
          </Panel>
        </Reveal>
      </div>

      {/* ---- Coverage gaps callout ---- */}
      <Reveal>
        <Panel>
          <SectionHeader
            eyebrow="Coverage gaps"
            title="Done, but shipped without a guard"
            description="Criteria marked done that carry zero directly-guarding tests — the actionable risk list."
            action={
              <Badge className="!border-destructive/40 !bg-destructive/10 !text-destructive" dot>
                {fmt(doneUnguarded.length)} at risk
              </Badge>
            }
          />
          <GapsCallout rows={doneUnguarded} total={doneUnguarded.length} cap={12} />
        </Panel>
      </Reveal>

      {/* ---- AC coverage explorer ---- */}
      <Reveal>
        <Panel>
          <SectionHeader
            eyebrow="Explorer"
            title="Every criterion, by coverage"
            description="Search, filter, and sort all criteria by how many tests guard them. Expand a row to see the guarding test files."
          />
          <CoverageExplorer rows={rows} components={componentIds} />
        </Panel>
      </Reveal>
    </div>
  );
}
