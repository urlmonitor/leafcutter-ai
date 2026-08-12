import "server-only";
import { repoRoot, repoPath, walk, readFileSafe, rel } from "./repo";
import { isLeafAc } from "./backlog";
import type { AC, TraceabilityHealth, Ticket } from "./types";

/**
 * Bidirectional traceability health — the honest quality signal.
 *
 *  1. Guard coverage over DONE ACs (shipped work should have tests) — the
 *     logical denominator, NOT "% over all 2000 ACs" (most of which are unbuilt).
 *  2. Orphan tests — test files/functions that name no AC (untraceable).
 *  3. Untraced code — source functions/classes in files no AC links to.
 *
 * Algorithms + counts established by the traceability audit (2026-07-10).
 */

const AC_ID = /\b[A-Z]{2,4}-\d+[a-z]?(?:-\d+)*\b/g;

function realIdSet(acs: AC[]): Set<string> {
  return new Set(acs.map((a) => a.id));
}

function idsInText(text: string, real: Set<string>): boolean {
  AC_ID.lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = AC_ID.exec(text)) !== null) {
    if (real.has(m[0])) return true;
  }
  return false;
}

/* ---------- 1. Guard over DONE ACs (uses enriched testCount) ---------- */
function doneGuard(acs: AC[]): TraceabilityHealth["doneGuard"] {
  const done = acs.filter((a) => a.workStatus === "done" && a.status === "active");
  const guarded = done.filter((a) => (a.testCount ?? 0) > 0);
  const leaves = done.filter((a) => isLeafAc(a));
  const leafGuarded = leaves.filter((a) => (a.testCount ?? 0) > 0);
  const pctOf = (n: number, d: number) => (d ? Math.round((n / d) * 100) : 0);
  return {
    total: done.length,
    guarded: guarded.length,
    unguarded: done.length - guarded.length,
    pct: pctOf(guarded.length, done.length),
    leafTotal: leaves.length,
    leafGuarded: leafGuarded.length,
    leafUnguarded: leaves.length - leafGuarded.length,
    leafPct: pctOf(leafGuarded.length, leaves.length),
  };
}

/* ---------- 2. Orphan tests ---------- */
function orphanTests(real: Set<string>): TraceabilityHealth["orphanTests"] {
  const files = [
    ...walk(repoPath("tests"), ".py"),
    ...walk(repoPath("unit_tests"), ".py"),
  ].filter((f) => !f.includes("__pycache__") && /^test_.*\.py$/.test(f.split("/").pop()!));

  let linkedFiles = 0;
  const orphanSamples: string[] = [];
  let fns = 0, linkedFns = 0;

  for (const file of files) {
    const content = readFileSafe(file);
    if (content === null) continue;
    if (idsInText(content, real)) linkedFiles++;
    else if (orphanSamples.length < 12) orphanSamples.push(rel(file));

    // function-level: split on def/class boundaries by indent
    const lines = content.split("\n");
    const boundaries: { line: number; indent: number; name: string; isTest: boolean }[] = [];
    lines.forEach((ln, i) => {
      const def = ln.match(/^(\s*)(?:async\s+)?def\s+(\w+)\s*\(/);
      const cls = ln.match(/^(\s*)class\s+(\w+)/);
      if (def) boundaries.push({ line: i, indent: def[1].length, name: def[2], isTest: /^test_/.test(def[2]) });
      else if (cls) boundaries.push({ line: i, indent: cls[1].length, name: cls[2], isTest: false });
    });
    for (let b = 0; b < boundaries.length; b++) {
      const cur = boundaries[b];
      if (!cur.isTest) continue;
      fns++;
      // body extends until the next boundary at indent <= cur.indent
      let end = lines.length;
      for (let n = b + 1; n < boundaries.length; n++) {
        if (boundaries[n].indent <= cur.indent) { end = boundaries[n].line; break; }
      }
      const body = lines.slice(cur.line, end).join("\n");
      if (idsInText(body, real)) linkedFns++;
    }
  }

  const pctOf = (n: number, d: number) => (d ? Math.round((n / d) * 100) : 0);
  return {
    files: files.length,
    linkedFiles,
    orphanFiles: files.length - linkedFiles,
    orphanFilePct: pctOf(files.length - linkedFiles, files.length),
    orphanFileSamples: orphanSamples,
    fns,
    linkedFns,
    orphanFns: fns - linkedFns,
    orphanFnPct: pctOf(fns - linkedFns, fns),
  };
}

/* ---------- 3. Untraced code ---------- */
function countSymbols(content: string): number {
  let n = 0;
  for (const ln of content.split("\n")) {
    if (/^\s*(?:async\s+)?def\s/.test(ln) || /^\s*class\s/.test(ln)) n++;
  }
  return n;
}

function linkedByPathset(r: string, exact: Set<string>, dirs: string[]): boolean {
  if (exact.has(r)) return true;
  return dirs.some((d) => r.startsWith(d));
}

function scanScope(
  key: string,
  label: string,
  roots: string[],
  acExact: Set<string>,
  acDirs: string[],
  ticketExact: Set<string>,
  ticketDirs: string[],
  real: Set<string>,
) {
  const files = roots
    .flatMap((root) => walk(repoPath(root), ".py"))
    .filter(
      (f) =>
        !f.includes("__pycache__") &&
        !/\/(tests|unit_tests)\//.test(f) &&
        !/^test_.*\.py$/.test(f.split("/").pop()!),
    );

  let linkedFiles = 0, symbols = 0, symbolsInUntraced = 0;
  const untraced: { path: string; symbols: number }[] = [];

  for (const file of files) {
    const content = readFileSafe(file);
    if (content === null) continue;
    const r = rel(file);
    const sym = countSymbols(content);
    symbols += sym;
    const linked =
      linkedByPathset(r, acExact, acDirs) ||
      linkedByPathset(r, ticketExact, ticketDirs) ||
      idsInText(content, real);
    if (linked) linkedFiles++;
    else {
      symbolsInUntraced += sym;
      untraced.push({ path: r, symbols: sym });
    }
  }

  untraced.sort((a, b) => b.symbols - a.symbols);
  const pctOf = (n: number, d: number) => (d ? Math.round((n / d) * 100) : 0);
  return {
    key, label,
    files: files.length,
    linkedFiles,
    untracedFiles: files.length - linkedFiles,
    untracedFilePct: pctOf(files.length - linkedFiles, files.length),
    symbols,
    symbolsInUntraced,
    symbolsUntracedPct: pctOf(symbolsInUntraced, symbols),
    topUntraced: untraced.slice(0, 10),
  };
}

// Keyed by repoRoot() so mock and real roots don't share traceability health data.
const _traceabilityByRoot = new Map<string, TraceabilityHealth>();

export function computeTraceability(acs: AC[], tickets: Ticket[]): TraceabilityHealth {
  const root = repoRoot();
  const hit = _traceabilityByRoot.get(root);
  if (hit) return hit;
  const real = realIdSet(acs);

  // AC-linked source paths (exact files + directory entries ending in "/")
  const acExact = new Set<string>();
  const acDirs: string[] = [];
  for (const a of acs) {
    for (const p of [...a.implementedBy, ...a.docLinks]) {
      const t = p.trim().replace(/^\.\//, "");
      if (t.endsWith("/")) acDirs.push(t);
      else acExact.add(t);
    }
  }
  // ticket files_touched (only tickets carrying ac_traceability)
  const ticketExact = new Set<string>();
  const ticketDirs: string[] = [];
  let ticketsWithTrace = 0;
  for (const t of tickets) {
    if (!t.acTraceability) continue;
    ticketsWithTrace++;
    for (const p of t.filesTouched) {
      const s = p.trim().replace(/^\.\//, "");
      if (s.endsWith("/")) ticketDirs.push(s);
      else ticketExact.add(s);
    }
  }

  const untracedCode = {
    scopes: [
      scanScope("scripts", "scripts/ only", ["scripts"], acExact, acDirs, ticketExact, ticketDirs, real),
      scanScope("all", "scripts/ + templates/*.py", ["scripts", "templates"], acExact, acDirs, ticketExact, ticketDirs, real),
    ],
  };

  const result: TraceabilityHealth = {
    doneGuard: doneGuard(acs),
    orphanTests: orphanTests(real),
    untracedCode,
    ticketsWithTraceability: ticketsWithTrace,
    ticketsTotal: tickets.length,
  };
  _traceabilityByRoot.set(root, result);
  return result;
}
