/**
 * Coverage view — shared types & helpers.
 *
 * The Coverage view answers one honest question: "how many tests guard each
 * acceptance criterion?" Ground truth from lib/data/tests.ts is that only a
 * minority of ACs are DIRECTLY guarded — this module keeps the vocabulary for
 * framing that gap consistently across every coverage component.
 *
 * All shapes here are plain-serializable so a Server Component can compute them
 * from getAtlas() and hand them to the client charts/table untouched.
 */
import type { AcLevel, WorkStatus } from "@/lib/data/types";

/** A single AC, trimmed to only what the coverage explorer needs (2068 rows). */
export interface CoverageRow {
  id: string;
  title: string;
  component: string;
  level: AcLevel;
  workStatus: WorkStatus;
  workStatusRaw: string;
  testCount: number;        // tests DIRECTLY guarding this AC
  testRolledUpCount: number; // incl. descendant ACs (composites)
  testRefs: string[];       // the guarding test files
  isLeaf: boolean;
}

/** One test-count histogram bucket ("0" | "1" | "2" | "3+"). */
export interface HistogramDatum {
  bucket: string;
  count: number;
  hsl: string;
}

/** Guarded-vs-total for a level or component. */
export interface CoverageBar {
  key: string;
  label: string;
  total: number;
  guarded: number;
  pct: number;
  hsl: string;
}

/** Percent guarded, guarding divide-by-zero. */
export function guardedPct(guarded: number, total: number): number {
  if (!total) return 0;
  return Math.round((guarded / total) * 100);
}

/**
 * A coverage-health tone for a percentage where HIGH is GOOD (guard %, adoption):
 * red under 10%, amber to 33%, then leaf-green. HSL channels for inline styling.
 */
export function coverageToneHsl(percent: number): string {
  if (percent <= 0) return "356 72% 56%"; // destructive — a true hole
  if (percent < 10) return "356 72% 56%";
  if (percent < 33) return "38 92% 58%"; // warning
  return "150 64% 52%"; // leaf green
}

/**
 * The INVERSE grading for a risk metric where HIGH is BAD (orphan tests,
 * untraced code): red at/above 50%, amber at/above 25%, else leaf-green.
 */
export function riskToneHsl(percent: number): string {
  if (percent >= 50) return "356 72% 56%"; // destructive
  if (percent >= 25) return "38 92% 58%"; // warning
  return "150 64% 52%"; // leaf green
}

/** A short honest grade word for a tone HSL (drives the scorecard pills). */
export function gradeLabel(hsl: string): string {
  if (hsl.startsWith("356")) return "Critical";
  if (hsl.startsWith("38")) return "At risk";
  return "Healthy";
}

/** One health scorecard tile — computed server-side, rendered by HealthScorecard. */
export interface ScoreTile {
  key: string;
  label: string;
  value: string;        // display string, e.g. "31%"
  meter: number;        // 0-100 fill for the meter
  hsl: string;          // graded tone (channels)
  sub: string;          // one-line honest caption
  detail?: string;      // optional secondary caption
}

/** One untraced-code scope, trimmed to what the UntracedCode panel renders. */
export interface ScopeStat {
  key: string;
  label: string;
  files: number;
  linkedFiles: number;
  untracedFiles: number;
  untracedFilePct: number;
  symbols: number;
  symbolsInUntraced: number;
  symbolsUntracedPct: number;
  topUntraced: { path: string; symbols: number }[];
}

/** Orphan-tests figures, trimmed for the OrphanTests panel. */
export interface OrphanStat {
  files: number;
  linkedFiles: number;
  orphanFiles: number;
  orphanFilePct: number;
  orphanFileSamples: string[];
  fns: number;
  linkedFns: number;
  orphanFns: number;
  orphanFnPct: number;
}
