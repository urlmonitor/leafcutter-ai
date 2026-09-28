---
title: "KI-CG-034 — `check_output_drift` examines every output file and compares none of them: the scanner and the installer key paths in two namespaces that never intersect"
description: "KI-CG-034 — `check_output_drift` examines every output file and compares none of them: the scanner and the installer key paths in two namespaces that never intersect"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-034 — `check_output_drift` examines every output file and compares none of them: the scanner and the installer key paths in two namespaces that never intersect

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../../commit-guardian.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** **resolved — and it was already resolved when this entry was filed.** See
  "Correction" immediately below before reading anything else here.
- **Occurrences:** 1
- **First seen:** 2026-08-26 · **Last seen:** 2026-08-26 (fixed by `ab9e91c41`, PR #593)
- **Where:** `scripts/commit_guardian/check_output_drift.py` — the directory scan and the
  `not in output_mappings` branch; `scripts/build_helpers.py::write_build_manifest` supplies
  the mapping it is compared against

**Correction, 2026-08-26.** This entry was filed against a worktree pinned at `18c8e10a`. PR
#593 (`ab9e91c41`, "gates that could not check stop reporting passes") had already rewritten
the scanner by then — and `ab9e91c41` is an **ancestor** of the commit that added this entry.
So the defect was fixed on `main` before the entry describing it reached `main`. Re-run
against `d0fa881c`:

```
$ python scripts/commit_guardian/check_output_drift.py ; echo "exit: $?"
exit: 0
check-output-drift: RESULT verified=466 uncomparable=5 exempt=5 gaps=0 drifted=0 missing=0 unreadable=0
```

466 files hash-compared against the manifest, zero skipped into the fail-open branch, and the
five uncomparables are declared exemptions that name their ground (`CLAUDE.md`, the glossary
seeds, `roadmap.json`, `vision.md` — write-if-absent scaffolds whose content is human-owned
from creation). `_derive_scan_dirs()` now derives the scan set from the manifest's own
`output_mappings` keys, which is precisely the fix direction recorded below.

**How this happened, since it is the more useful half.** The evidence was gathered in a
long-lived worktree and never re-checked against current `main` before landing. Everything
downstream inherited that: the severity argument, the `ACD-2100d-2` framing, the commit
message. A stale baseline does not announce itself — the run really did print 169 skips and
zero comparisons, so every check of the *evidence* passed. Only a check of the *baseline*
would have caught it. Pin the commit you measured, and re-measure on `origin/main`
immediately before you land.

**The reverse error is the one worth guarding against.** The `ACD-2100d-2` coder read this
entry, found production already correct, and refused to write a no-op edit to manufacture a
diff. That was right. An entry like this one — confident, evidenced, wrong — is exactly what
pressures an agent into "fixing" working code.

The original report follows unchanged, because the mechanism it describes was real at
`18c8e10a` and is worth keeping as a pattern.

**Symptom (as of `18c8e10a`; no longer reproducible).** The Direction-B drift guard passes on
every working copy because it never performs a comparison. Run against a freshly built
worktree at `18c8e10a`:

```
$ python scripts/commit_guardian/check_output_drift.py ; echo "exit: $?"
exit: 0
$ grep -c  "not in output_mappings" <output>   → 169
$ grep -vc "not in output_mappings" <output>   → 0
```

**169 files examined, 169 skipped, zero compared, and not one line of any other kind.** The
`grep -vc` is the load-bearing half of that evidence: it establishes that the skip branch is
not merely common but *total*. A count of skips alone would be consistent with a check that
also did some real work.

**Cause.** The scanner walks a hardcoded list of directory names and keys each result
relative to the repository root — `.claude/agents/README.md`. The installer keys every
manifest entry under the *configured output root* — `<output_root>/agents/README.md`. The two
key namespaces are disjoint, so every lookup misses and every file takes the fail-open
`not in output_mappings → INFO → continue` path.

**Why this is high rather than medium.** The severity is not the missing coverage, it is that
the missing coverage is **shaped like success**:

- An unmapped file prints an informational line and is skipped. From outside, that is
  indistinguishable from a file that was checked and found clean. The hook exits 0 either way.
- This is the fourth distinct route to "exit 0 having checked nothing" in this hook family
  (`KI-CG-012`@380, `KI-CG-012`@800, `KI-CG-019`). Unlike the other three, this one has
  **never** worked — there is no regression to point at, which is why nothing noticed.
- It is the guard that `ACD-2100d-2` is written to strengthen. An acceptance criterion built
  on the assumption that the check works, when it has never run a comparison, would be
  satisfied by an implementation that leaves it inert. *(Superseded: `ab9e91c41` landed the
  comparison, so `ACD-2100d-2` found its premise already satisfied.)*
- The registration compounds it: the hook's `files` trigger in
  `scripts/commit_guardian/commit_guardian.json` carries the same stale path prefixes, so a
  deployed file under a differently-configured output root does not match and the hook does
  not fire at all. Repairing the script alone leaves a gate that computes the right answer
  and is never invoked.

**Fix direction — implemented by `ab9e91c41` before this entry was written.** Derive both the
set of files to check and the key each is looked up under from the installer's mapping itself,
rather than from a hardcoded directory list, so a newly deployed directory is covered the day
it appears. Make the unmapped case report rather than skip — a deployed file with no mapping
entry is either a mapping defect or an untracked output, and both are findings. Cover it with
a test that asserts a run examining files while checking none of them **fails**; a test
written without that assertion passes against the defect.

`ab9e91c41` did all of that: `_derive_scan_dirs()` reads the manifest keys, the unmapped case
reports `GAP`/`EXEMPT` instead of skipping, and the `verified == 0` floor treats an empty
`output_mappings` as INDETERMINATE rather than clean. Recorded here as the shape of the fix,
not as outstanding work.

**Caution for whoever fixes this.** `_compute_output_mappings`'s docstring says it enumerates
four template directories by hand and therefore cannot see the route file. **That docstring is
stale and the claim is false** — the generated manifest contains nine `workflows-js` entries
including the deployed `plan-feature.js`. The mapping side is installer-derived and already
correct; the defect is entirely on the scan side. An agent working from the docstring during
the `ACD-2100d-2` enrichment pass reached the wrong conclusion and caught it only by running
the check. Run it; do not read it.

**Related.** `ACD-2100d-2` (written to repair this; found it already repaired). `KI-CG-019`,
`KI-CG-012` (the sibling exit-0-having-checked-nothing routes — those are still open, and
unlike this one they have regressed from working states). `KI-BP-016` (the same output-root
confusion in the build's doc-index phase).

**Pattern:** `docs/reference/false-green-mechanisms.md` → M5 (a validator that validates
nothing and reports success).

---
