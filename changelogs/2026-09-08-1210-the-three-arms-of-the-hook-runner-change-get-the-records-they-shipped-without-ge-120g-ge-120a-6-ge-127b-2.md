---
title: "The three arms of the hook-runner change get the records they shipped without (GE-120g, GE-120a-6, GE-127b-2)"
date: "2026-09-08"
time: "12:10"
type: manual
components:
  - commit_guardian
  - precommit_hooks
  - ac_store
  - build_pipeline
summary: "Wrote the missing specification for guardrail behaviour that was already live in production — an undocumented commit-runner safeguard and a merge-time file-size fix built elsewhere both now have acceptance criteria a test can hold them to, a stale phantom-done citation was removed, and two known issues (a merge-blocking ratchet bug, now resolved, and an unresolved build gap that can silently break commits in any project that installs this tooling) were filed for the next reader."
description: "Three commits (76f16c752, e7ebd25b4, 6ae4010f9) plus merge commits pulling in origin/main. (1) New L1 GE-120g and its children GE-120g-1/-1-i/-2/-3, plus L2 GE-120a-6, specify the three arms of PR #728's run_hook.py change after the fact — the behaviour shipped with no AC, was wrongly claimed against GE-127a-1, and that false implemented_by citation is removed here. All new records are readiness: draft / work_status: todo, green-on-arrival. (2) GE-127b-2 records the merge-aware file-size ratchet that shipped independently via PR #752 on main; rather than duplicate the implementation, covered_by points at main's own real-git test (test_ki_cg_20260908_file_size_ratchet_merge_aware.py). (3) docs/known-issues/commit-guardian.md's KI-CG-20260908-ratchet-reads-pre-merge-head moves open -> RESOLVED, with an ID-reconciliation note: the fixing commit and its own test docstring cite an id (KI-CG-20260908-file-size-ratchet-refuses-merge-commits) that no register ever contained. (4) docs/known-issues/build-pipeline.md gains KI-BP-20260907-no-gitignore-for-consumers: build.py deploys no .gitignore, so a fresh consumer install tracks compiled .pyc beside deployed modules and any tool importing one re-fails the next commit; PR #728's PYTHONDONTWRITEBYTECODE=1 suppresses the trigger for commit-guardian's own hooks but does not remove the underlying condition. (5) docs/acceptance-criteria/guardrail-engine/PROJECT_CONTEXT.md gains the context these new records rely on."
commits:
  - 76f16c752
  - e7ebd25b4
  - 6ae4010f9
pr: "750"
breaking: false
---

## Entry

### The problem: behaviour shipped, specification didn't

PR #728 registered `check-file-size` and, in the same diff, changed `run_hook.py` to
stop leaving tracked `.pyc` files behind. The `run_hook.py` change had **no AC**. It was
claimed against `GE-127a-1` — a BA judged that claim and rejected it: grepping all four
`GE-127a-1*` test files for `run_hook|pyc|pycache|gitignore` returns zero hits, so the
citation named a criterion that neither constrained the runner nor was exercised by it.
That is the phantom-done shape this repo's own `implemented_by`-drives-the-surface
discipline exists to catch. The false `implemented_by` line is removed from
`GE-127a-1.yaml` in this change.

### New records — GE-120g and GE-120a-6

**`GE-120g`** (L1) — *"Being looked at leaves your work untouched, and only an objection
stops you."* Placed under `GE-120` on a polarity argument: every existing sibling tests
whether a check's **answer** is right; this is a check whose answer was right and did not
decide the outcome — the gate printed `PASSED` and the commit was still refused by the
act of checking. No existing sibling can see that shape.

Beneath it:
- `GE-120g-1` — an ordinary commit leaves the working copy holding exactly the content it
  held before, whether checks let it through or refuse it.
- `GE-120g-1-i` — that rule binds by **declared role**: a check declared to fix as it goes
  is not caught by it, and no judging check can be let off it.
- `GE-120g-2` — a commit is refused only because a check objected; a set of verdicts that
  objects to nothing always lets it through.
- `GE-120g-3` — the guidance a check author reads states what declaring a role commits the
  check to, and states that a refusal comes from an objection.

**`GE-120a-6`** (L2) — an interpreter that cannot be started at all is reported, in the
reader's own words, rather than the commit crashing out of the run. `GE-120a` carries a
`child_limit_override: 6` for it, authorised by BrainCandy on 2026-09-07 and recorded in
the file alongside the alternatives that were checked and closed.

All new records are `readiness: draft`, `work_status: todo`, and green-on-arrival —
nothing here claims to be built or tested; each carries a named mutation to manufacture a
real red baseline later.

### GE-127b-2 — recording a fix that shipped somewhere else

While this branch was in flight, `origin/main` independently shipped PR #752: the
file-size ratchet resolved a file's previous length from `HEAD` alone, so during a merge
it judged content authored on the other parent as new growth. `GE-127b-2` specifies the
rule as shipped — a merge's permitted previous length is the most permissive across every
parent — and its `covered_by` points at `unit_tests/commit_guardian/
test_ki_cg_20260908_file_size_ratchet_merge_aware.py`, the real-git test that already
proves it, rather than standing up a second implementation. `GE-127b.yaml`'s
`covered_by` gains the child in the same commit, per this repo's own "AC-store commits —
stage the parent alongside the child" convention.

### Known issue closed — KI-CG-20260908-ratchet-reads-pre-merge-head

Filed open against this same branch (merging `origin/main` was refused for two files
already on main and untouched here), the entry now reads **RESOLVED 2026-09-08**
(`62410ca66`, PR #752), verified live against the same merge (`928e53ad9`) that originally
triggered it — it passed `check-file-size` with no `SKIP`. A reconciliation bullet was
added because the fixing commit and its own test docstring cite an id,
`KI-CG-20260908-file-size-ratchet-refuses-merge-commits`, that no register ever
contained — this entry, filed independently against the same defect, is the only record,
and the bullet exists so a reader who greps the other id concludes "differently named,"
not "missing."

### Known issue filed, still open — KI-BP-20260907-no-gitignore-for-consumers

`build.py` deploys no `.gitignore` to consumers. A fresh consumer install therefore
tracks `__pycache__`/`.pyc` files sitting beside deployed Python modules; any tool that
later imports one of those modules rewrites the tracked `.pyc`, and pre-commit reports
"files were modified by this hook" on an otherwise-passing gate. PR #728's
`PYTHONDONTWRITEBYTECODE=1` stops commit-guardian's own delegated hook processes from
triggering it, but does not remove the underlying gap, and the blast radius across other
deployed tooling is uncounted — which is why this is a known issue rather than an AC yet.

### Also

`docs/acceptance-criteria/guardrail-engine/PROJECT_CONTEXT.md` gained the context these
new records depend on. A blocking, pre-existing product-truth drift (derived files stale
against `work_status` flips landed on main the same day) was resolved by re-running the
store's own generator; no hook was skipped and no bypass was used for it.
