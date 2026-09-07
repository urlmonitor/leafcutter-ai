---
title: "ADR-034 resolves to one decision again: the uniqueness pass moves to 037"
date: "2026-08-26"
time: "11:00"
type: manual
components:
  - documentation_system
  - guardrail_engine
  - commit_guardian
summary: "Renumbers ADR-034-whole-collection-uniqueness-pass to ADR-037 and repoints the 49 citations that meant it, so the number 034 resolves solely to main's knowledge-write-ownership decision and the branch's own uniqueness pass reports clean over the decisions namespace."
description: "Two ADRs claimed 034. Main minted ADR-034-knowledge-write-ownership while this branch's ADR-034-whole-collection-uniqueness-pass was in flight; the filenames differ, so git saw no conflict, and check_adr_collision is diff-scoped, so each side was clean in isolation. The branch's own whole-collection uniqueness pass caught it — a true positive on the exact defect it exists to catch — and failed two tests in unit_tests/commit_guardian/test_ge_122e_3.py, the epic's exit gate. The uniqueness pass moves; knowledge-write-ownership, already merged and cited from main, keeps 034. The target number is 037, taken from scripts/adr_refs.py's Unclaimed-numbers audit rather than max+1, per ADR-029's rule that a number is free only when it owns neither a file nor a citation: main holds 034 through 036, and 037 owns neither. The rename and the 23 slug-qualified citations were rewritten mechanically by adr_refs.py --apply, which never touches a bare ADR-NNN because a bare citation stops identifying one decision the moment a number splits. All 68 bare citations were classified by hand: 26 meant the uniqueness pass and were retargeted through adr_refs.py --disambiguate under an explicit per-file glob list; 16 mean knowledge-write-ownership and were left; 14 are synthetic test fixtures in test_ge_122a_1_ii.py and its AC that model a two-claimant merge and are not citations of either decision; 5 are dated narratives about the collision itself (this repo's own changelog, check_adr_collision.py's decision history, and an architect-review note recording the highest number on disk that day) and are left because repointing them would falsify the record; 5 sit in gitignored build output and logs; and the last 2 are the docs/INDEX.md rows, regenerated. The one sentence whose meaning the rename broke — the PR #495 reconciliation changelog naming both claimants at 034 — is reworded rather than renumbered. Both index surfaces are regenerated rather than hand-edited: docs/INDEX.md, and docs/architecture/adrs/README.md, which had gone stale at ADR-033 and now lists 034 through 037. The ADR carries a Renumbered row in its Status table so a reader arriving from an old citation learns what happened. After the repair, adr_refs.py reports 0 duplicates and 0 gaps across 37 ADRs, the uniqueness pass exits 0 over all four namespaces (acceptance-criteria 3513, decisions 38, diagrams 24, work-items 297), and the two test_ge_122e_3.py failures clear."
breaking: false
---

## Entry

The collision was invisible to every mechanism that exists to prevent it, and visible
to the one this branch adds.

`check_adr_collision` compares the numbers a commit stages against `origin/main` and
against in-flight remote branches. Each side of this collision was clean when it was
committed: main's ADR-034 did not exist when the branch authored its own, and the
branch's ADR-034 was never staged in a commit that also staged main's. Git itself sees
two different filenames and merges them without complaint. What caught it is
`check_identifier_uniqueness.py`'s whole-collection pass — inspection over the entire
`docs/architecture/adrs/` directory rather than over one commit's diff — which is
precisely the difference ADR-037 §3 records as the reason to build it.

### Which ADR moved, and why

Knowledge-write-ownership is merged, live on main, and cited from main-side ACs, docs
and tests. The uniqueness pass exists only on this branch. Moving the branch-side
claimant is the change with the smaller blast radius and no effect on anything already
merged.

### How 037 was chosen

Not `max + 1`. `scripts/adr_refs.py` reports the numbers that own neither a file nor a
citation, which is the rule ADR-029 states and the rule a directory listing cannot
enforce — a retired or dangling number still owns citations and must not be reused.
The audit named 037 as the first genuinely unclaimed number; 000 and 077 appear as
dangling in the same report and are deliberately left alone (a `DOC_LINKS` placeholder
and a test fixture respectively).

### What was NOT repointed

A bare `ADR-034` is not automatically a citation of a decision. Three groups of them
survive this change on purpose, and a future reader should not read them as misses:
the citations that genuinely mean knowledge-write-ownership; the synthetic
`ADR-034-committed.md` / `ADR-034-authored-by-me.md` fixtures in
`test_ge_122a_1_ii.py` and `GE-122a-1-ii.yaml`, which model a two-claimant merge and
name no real decision; and four dated narratives that describe the collision itself,
where the number is the subject rather than the reference.
