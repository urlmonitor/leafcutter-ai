import * as React from "react";
import {
  Layers,
  TriangleAlert,
  Unlink,
  FileCode2,
  GitBranch,
  Info,
} from "lucide-react";
import { getAtlas } from "@/lib/data/atlas";
import { LEVEL_TONE } from "@/lib/status";
import { fmt, humanize, pct } from "@/lib/utils";
import { PageHeader, Panel, SectionHeader, Badge } from "@/components/ui/kit";
import { Reveal } from "@/components/pulse/reveal";
import { CoverageHistogram } from "@/components/coverage/coverage-histogram";
import { LevelCoverage } from "@/components/coverage/level-coverage";
import { ComponentCoverage } from "@/components/coverage/component-coverage";
import { CoverageExplorer } from "@/components/coverage/coverage-explorer";
import { GapsCallout } from "@/components/coverage/gaps-callout";
import { HeadlineGuard, HealthScorecard } from "@/components/coverage/health-scorecard";
import { OrphanTests } from "@/components/coverage/orphan-tests";
import { UntracedCode } from "@/components/coverage/untraced-code";
import {
  coverageToneHsl,
  riskToneHsl,
  guardedPct,
  type CoverageBar,
  type CoverageRow,
  type HistogramDatum,
  type OrphanStat,
  type ScopeStat,
  type ScoreTile,
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
  const { acs, coverage, traceability } = getAtlas();
  const { doneGuard: dg, orphanTests, untracedCode } = traceability;

  // ---- Whole-store (all-AC) coverage — DEMOTED to a footnote, kept honest ----
  const { totalAcs, guardedPct: allPct, totalTestFiles } = coverage;

  // ---- Scorecard tiles (mostly red/amber — this view exists to show gaps) ----
  const wideScope = untracedCode.scopes.find((s) => s.key === "all") ?? untracedCode.scopes[0];
  const adoptionPct = pct(traceability.ticketsWithTraceability, traceability.ticketsTotal);
  const tiles: ScoreTile[] = [
    {
      key: "guard",
      label: "Shipped-AC guard",
      value: `${dg.pct}%`,
      meter: dg.pct,
      hsl: coverageToneHsl(dg.pct),
      sub: `${fmt(dg.guarded)} of ${fmt(dg.total)} done ACs guarded`,
      detail: `Leaves ${dg.leafPct}% · ${fmt(dg.leafGuarded)}/${fmt(dg.leafTotal)}`,
    },
    {
      key: "orphan",
      label: "Orphan tests",
      value: `${orphanTests.orphanFilePct}%`,
      meter: orphanTests.orphanFilePct,
      hsl: riskToneHsl(orphanTests.orphanFilePct),
      sub: `${fmt(orphanTests.orphanFiles)} of ${fmt(orphanTests.files)} test files name no AC`,
      detail: `${orphanTests.orphanFnPct}% of test functions are orphaned`,
    },
    {
      key: "untraced",
      label: "Untraced code",
      value: `${wideScope.untracedFilePct}%`,
      meter: wideScope.untracedFilePct,
      hsl: riskToneHsl(wideScope.untracedFilePct),
      sub: `${fmt(wideScope.untracedFiles)} of ${fmt(wideScope.files)} src files (scripts+templates)`,
      detail: `${wideScope.symbolsUntracedPct}% of functions/classes untraced`,
    },
    {
      key: "adoption",
      label: "Traceability adoption",
      value: `${adoptionPct}%`,
      meter: adoptionPct,
      hsl: coverageToneHsl(adoptionPct),
      sub: `${fmt(traceability.ticketsWithTraceability)} of ${fmt(traceability.ticketsTotal)} tickets carry ac_traceability`,
      detail: "the root cause of thin source→AC linkage",
    },
  ];

  // ---- Orphan + untraced view models ----
  const orphanStat: OrphanStat = {
    files: orphanTests.files,
    linkedFiles: orphanTests.linkedFiles,
    orphanFiles: orphanTests.orphanFiles,
    orphanFilePct: orphanTests.orphanFilePct,
    orphanFileSamples: orphanTests.orphanFileSamples,
    fns: orphanTests.fns,
    linkedFns: orphanTests.linkedFns,
    orphanFns: orphanTests.orphanFns,
    orphanFnPct: orphanTests.orphanFnPct,
  };
  const scopeStats: ScopeStat[] = untracedCode.scopes.map((s) => ({
    key: s.key,
    label: s.label,
    files: s.files,
    linkedFiles: s.linkedFiles,
    untracedFiles: s.untracedFiles,
    untracedFilePct: s.untracedFilePct,
    symbols: s.symbols,
    symbolsInUntraced: s.symbolsInUntraced,
    symbolsUntracedPct: s.symbolsUntracedPct,
    topUntraced: s.topUntraced,
  }));

  // ---- Distribution (over ALL criteria — explicitly the misleading framing) ----
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

  // ---- By component ----
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

  // ---- Explorer rows ----
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

  // ---- Coverage gaps: DONE ACs with zero direct guards — the actionable risk ----
  const doneUnguarded = rows
    .filter((r) => r.workStatus === "done" && r.testCount === 0)
    .sort((a, b) => {
      if (a.isLeaf !== b.isLeaf) return a.isLeaf ? -1 : 1;
      if (a.level !== b.level) return b.level.localeCompare(a.level);
      return a.id.localeCompare(b.id);
    });

  return (
    <div className="animate-fade-in space-y-12">
      <PageHeader
        eyebrow="Traceability · bidirectional health"
        title="Traceability & coverage health"
        description="Does shipped work have tests, do those tests trace to requirements, and does the code trace back too? This view measures guard coverage over what's DONE — not the whole store — and both directions of drift: orphan tests and untraced code. It exists to show gaps honestly, not to reassure."
      >
        <div className="flex flex-col items-end gap-1.5">
          <Badge className="!border-destructive/40 !bg-destructive/10 !text-destructive" dot>
            <TriangleAlert className="h-3 w-3" />
            {dg.pct}% of shipped guarded
          </Badge>
          <span className="eyebrow">Traceability is thin</span>
        </div>
      </PageHeader>

      {/* ---- Headline: guard over the logical (shipped) denominator ---- */}
      <Reveal>
        <HeadlineGuard
          pct={dg.pct}
          guarded={dg.guarded}
          unguarded={dg.unguarded}
          total={dg.total}
          leafPct={dg.leafPct}
          leafGuarded={dg.leafGuarded}
          leafTotal={dg.leafTotal}
          hsl={coverageToneHsl(dg.pct)}
        />
      </Reveal>

      {/* ---- Health scorecard ---- */}
      <Reveal delay={0.05}>
        <HealthScorecard tiles={tiles} />
      </Reveal>

      {/* ---- Orphan tests ---- */}
      <Reveal>
        <Panel>
          <SectionHeader
            eyebrow="Direction 1 · tests → requirements"
            title="Orphan tests"
            description="Test files and functions that reference no acceptance criterion. They exist but can't be traced back to a requirement — a green run proves nothing you can point at."
            action={
              <Badge className="!border-destructive/40 !bg-destructive/10 !text-destructive" dot>
                <Unlink className="h-3 w-3" />
                {orphanTests.orphanFilePct}% of files orphaned
              </Badge>
            }
          />
          <OrphanTests stat={orphanStat} />
        </Panel>
      </Reveal>

      {/* ---- Untraced code ---- */}
      <Reveal>
        <Panel>
          <SectionHeader
            eyebrow="Direction 2 · code → requirements"
            title="Untraced code"
            description="Source functions and classes living in files that no acceptance criterion (and no traceability-carrying ticket) links to. Two scopes, because “the code” is ambiguous — toggle scripts-only vs incl. templates."
            action={
              <Badge className="!border-destructive/40 !bg-destructive/10 !text-destructive" dot>
                <FileCode2 className="h-3 w-3" />
                {wideScope.untracedFilePct}% untraced
              </Badge>
            }
          />
          <UntracedCode
            scopes={scopeStats}
            ticketsWithTraceability={traceability.ticketsWithTraceability}
            ticketsTotal={traceability.ticketsTotal}
          />
        </Panel>
      </Reveal>

      {/* ---- Coverage gaps callout — the actionable risk tied to the headline ---- */}
      <Reveal>
        <Panel>
          <SectionHeader
            eyebrow="Actionable risk"
            title="Done, but shipped without a guard"
            description="The unguarded slice of the headline, itemised: criteria marked done that carry zero directly-guarding tests. This is the list to work down."
            action={
              <Badge className="!border-destructive/40 !bg-destructive/10 !text-destructive" dot>
                {fmt(doneUnguarded.length)} at risk
              </Badge>
            }
          />
          <GapsCallout rows={doneUnguarded} total={doneUnguarded.length} cap={12} />
        </Panel>
      </Reveal>

      {/* ---- Distribution — the DEMOTED all-AC number ---- */}
      <Reveal>
        <Panel>
          <SectionHeader
            eyebrow="Context · over ALL criteria (misleading)"
            title="Tests per acceptance criterion — whole store"
            description="Every criterion counted by how many tests directly guard it. Read this with care."
            action={
              <span className="hidden items-center gap-1.5 text-xs text-muted-foreground sm:inline-flex">
                <Layers className="h-3.5 w-3.5" />
                {fmt(totalAcs)} criteria
              </span>
            }
          />
          <div className="mb-5 flex items-start gap-3 rounded-lg border border-warning/30 bg-warning/[0.07] p-4">
            <Info className="mt-0.5 h-5 w-5 shrink-0 text-warning" />
            <p className="text-sm leading-relaxed text-muted-foreground">
              Guarding tests exist for just{" "}
              <span className="font-semibold text-warning">{allPct}%</span> of all{" "}
              {fmt(totalAcs)} criteria — but this number is{" "}
              <span className="font-semibold text-foreground">misleading</span>: most criteria
              aren&apos;t built yet, so they were never expected to have a test. The honest metric is
              the{" "}
              <span className="font-semibold text-success">{dg.pct}% guard over shipped work</span>{" "}
              at the top of this page.
            </p>
          </div>
          <CoverageHistogram data={histogram} />
          <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
            <span className="font-semibold text-destructive">{fmt(zeroCount)} criteria</span> have
            zero guarding tests — {guardedPct(zeroCount, totalAcs)}% of the entire store. Of the
            guarded remainder, most carry just a single test; only{" "}
            {fmt(coverage.histogram.find((h) => h.bucket === "3+")?.count ?? 0)} have three or more.
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
              description="Guarded share from customer value (L0) down to edge cases (L3), over all criteria."
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

      {/* ---- AC coverage explorer ---- */}
      <Reveal>
        <Panel>
          <SectionHeader
            eyebrow="Explorer"
            title="Every criterion, by coverage"
            description="Search, filter, and sort all criteria by how many tests guard them. Expand a row to see the guarding test files."
            action={
              <span className="hidden items-center gap-1.5 text-xs text-muted-foreground sm:inline-flex">
                <GitBranch className="h-3.5 w-3.5" />
                {fmt(totalTestFiles)} test files scanned
              </span>
            }
          />
          <CoverageExplorer rows={rows} components={componentIds} />
        </Panel>
      </Reveal>
    </div>
  );
}
