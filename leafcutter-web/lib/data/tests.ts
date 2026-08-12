import "server-only";
import { repoRoot, repoPath, walk, readFileSafe, rel } from "./repo";
import { loadAcs } from "./ac-store";

/**
 * Test coverage per AC — "how many tests guard this AC".
 *
 * Ground truth (established by investigation of the real store):
 *  - The dominant signal is AC ids written INTO test files (docstrings/comments/
 *    code/fixtures), matched by exact id. `doc_links` rarely points at tests and
 *    `covered_by` is overwhelmingly the parent->child AC hierarchy (not tests).
 *  - So: direct guard = { test files naming the AC id } ∪ { covered_by/doc_links
 *    entries that are themselves test paths }.
 *  - Rolled-up guard (for composite L0/L1 parents) = union over descendants via
 *    the covered_by child hierarchy.
 * Only ~16% of ACs are directly guarded — coverage is NOT high, which is the point.
 */

export interface AcCoverage {
  count: number;
  testRefs: string[];
  rolledUpCount: number;
  rolledUpRefs: string[];
}

// Matches AC ids like BP-006a-3, ACD-1200a-9-i, ACS-500. Greedy trailing groups
// so a full id is captured as one token (won't also fire the parent on the same match).
const AC_ID = /\b([A-Z]{2,4}-\d+[a-z]?(?:-\d+)*)\b/g;
// True when a string looks like a test-file reference.
const IS_TEST_REF = /(test_[\w/]*\.py|[\w/]*_test\.py|tests\/|unit_tests\/)/i;

function isChildRef(entry: string): boolean {
  // An AC-id child reference: looks like an id, no path separator, not a .py file.
  return /^[A-Z]{2,4}-\d/.test(entry) && !entry.includes("/") && !entry.endsWith(".py");
}

// Outer key = repoRoot(), inner key = AC id.
// Per-root keying prevents a mock-mode toggle from serving stale coverage data.
const _coverageByRoot = new Map<string, Map<string, AcCoverage>>();
const _testFileCountByRoot = new Map<string, number>();

export function loadCoverage(): Map<string, AcCoverage> {
  const root = repoRoot();
  const hit = _coverageByRoot.get(root);
  if (hit) return hit;

  const acs = loadAcs();
  const validIds = new Set(acs.map((a) => a.id));

  // 1. direct refs from AC fields (rare, but authoritative when present)
  const direct = new Map<string, Set<string>>();
  for (const id of validIds) direct.set(id, new Set());
  for (const ac of acs) {
    const set = direct.get(ac.id)!;
    for (const v of [...ac.coveredBy, ...ac.docLinks]) {
      if (IS_TEST_REF.test(v)) set.add(v.trim());
    }
  }

  // 2. the dominant signal: AC ids named inside test files
  const testDirs = [repoPath("tests"), repoPath("unit_tests")];
  let testFileCount = 0;
  for (const dir of testDirs) {
    for (const file of walk(dir, ".py")) {
      if (file.includes("__pycache__")) continue;
      const content = readFileSafe(file);
      if (!content) continue;
      testFileCount++;
      const relPath = rel(file);
      const seen = new Set<string>();
      let m: RegExpExecArray | null;
      AC_ID.lastIndex = 0;
      while ((m = AC_ID.exec(content)) !== null) {
        const id = m[1];
        if (seen.has(id) || !validIds.has(id)) continue;
        seen.add(id);
        direct.get(id)!.add(relPath);
      }
    }
  }

  // 3. child hierarchy for rollup
  const children = new Map<string, string[]>();
  for (const ac of acs) {
    children.set(
      ac.id,
      ac.coveredBy.filter((c) => isChildRef(c) && validIds.has(c)),
    );
  }

  // 4. memoized DFS rollup (cycle-guarded)
  const rollupCache = new Map<string, Set<string>>();
  const visiting = new Set<string>();
  function rollup(id: string): Set<string> {
    const cached = rollupCache.get(id);
    if (cached) return cached;
    if (visiting.has(id)) return direct.get(id) ?? new Set();
    visiting.add(id);
    const acc = new Set<string>(direct.get(id) ?? []);
    for (const c of children.get(id) ?? []) {
      for (const r of rollup(c)) acc.add(r);
    }
    visiting.delete(id);
    rollupCache.set(id, acc);
    return acc;
  }

  const out = new Map<string, AcCoverage>();
  for (const id of validIds) {
    const d = direct.get(id)!;
    const r = rollup(id);
    out.set(id, {
      count: d.size,
      testRefs: [...d].sort(),
      rolledUpCount: r.size,
      rolledUpRefs: [...r].sort(),
    });
  }

  // Stash the test-file count alongside the coverage map, keyed by root.
  _testFileCountByRoot.set(root, testFileCount);
  _coverageByRoot.set(root, out);
  return out;
}

export function totalTestFiles(): number {
  loadCoverage(); // ensures _testFileCountByRoot is populated for the current root
  return _testFileCountByRoot.get(repoRoot()) ?? 0;
}
