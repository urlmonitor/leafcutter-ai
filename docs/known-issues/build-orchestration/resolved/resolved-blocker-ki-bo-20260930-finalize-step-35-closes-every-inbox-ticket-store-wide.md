---
title: "KI-BO-20260930 — /finalize-feature Step 3.5 flips every inbox ticket and AC to done store-wide, not just the branch's"
description: "KI-BO-20260930 — /finalize-feature Step 3.5 flips every inbox ticket and AC to done store-wide, not just the branch's"
type: reference
category: reference
status: active
created: '2026-09-30'
last_updated: '2026-10-21'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
  - docs/acceptance-criteria/build-orchestration/BO-400-ticket-status-source-of-truth/BO-400e-3.yaml
  - docs/acceptance-criteria/build-orchestration/BO-4500-fix-once-every-route/BO-4500a-5-iv.yaml
---

# KI-BO-20260930 — /finalize-feature Step 3.5 flips every inbox ticket and AC to done store-wide, not just the branch's

> Index: [build-orchestration.md](../../build-orchestration.md).

- **Severity:** blocker — it writes `done` onto work that was never built, and the
  falsification is silent, durable, and indistinguishable from real completion
  afterwards. Indexed `blocker` per the register's worst-reading rule.
- **Status:** **RESOLVED 2026-10-21** by PR #1292 (merge `aa762f3f4`). See the Resolution
  section at the end. Original line, preserved: open.
- **Occurrences:** 1 observed directly; the defect is in the closure step every epic
  finalization runs, so every prior finalization is a candidate
- **Where:** `.claude/workflows/finalize-feature.js`, Step 3.5 (cross-epic closure)

**Symptom.** Step 3.5 is meant to close the tickets and ACs the finalizing branch
actually delivered. It instead walks the whole inbox and sets **every** ticket and AC it
finds to `done` — including records belonging to unrelated, unstarted epics. The commit
it produces looks routine; the damage is visible only in `git show <sha> --stat`, which
is not something a finalize run prompts anyone to read.

**Why this is worse than a wrong status field.** `done` is load-bearing in this repo,
not descriptive. `ticket-prioritizer` treats a `done` ticket as satisfying other
tickets' `depends_on`, so falsely-closed records unblock work whose prerequisites do not
exist. `ac_prioritizer` stops surfacing a `done` AC, so the work silently leaves the
backlog rather than failing loudly. And nothing downstream re-derives the truth: once
written, a false `done` is indistinguishable from a real one, so the error is not
self-correcting and compounds with every subsequent planning pass.

**Detection.** Before finalizing, record the status of every sibling record you are
*not* closing. After the closure commit, re-read them. Any that changed were changed by
Step 3.5. `git show <sha> --stat` on the closure commit is the fast version: a closure
for one ticket that touches dozens of AC files under `docs/acceptance-criteria/` is the
signature.

**Workaround — close by hand, with a sibling baseline.** This is a workaround for a
defect that should be fixed, not a procedure worth promoting: it exists because Step 3.5
cannot currently be trusted to scope itself, and it should disappear when Step 3.5 is
fixed. Do not build tooling around it.

Capture the statuses of the sibling records before touching anything, close the one
ticket and its ACs by hand, then re-read the same list and diff. The check has to be a
*captured* before-state, not a recollection — the whole failure mode is a write nobody
noticed. Used for `TQ-600a-5` on 2026-09-30: `TQ-600a-2/3/4/6/7/8` were recorded `todo`
beforehand and verified still `todo` afterwards, which is what established that the
hand closure leaked nothing. An unverified hand closure proves nothing that the
automated one does not.

**Two further finalize defects hit on the same drive**, recorded here because together
they are why the hand path was taken rather than a retry:

- Step 3 false-halts on the build layer — deploy-dependent tests read as regressions
  when the step skips `build.py`.
- The environment bootstrap runs `poetry`, but this repo installs from
  `requirements-dev.txt`, so the bootstrap fails before the step does anything.

**Remediation.**

1. Scope Step 3.5 to the records the finalizing branch actually touched — derive the set
   from the branch diff, not from an inbox scan. An inbox scan has no way to know which
   records this branch delivered, so there is no safe filter to add to the current shape.
2. Until that lands, have Step 3.5 print the records it is about to close and require
   confirmation. The step already runs behind prompt gates for destructive git
   operations; writing `done` across the store is destructive in the same sense.

**Related.** `KI-BO-20260927-finalize-triage-baseline-predates-merged-main` (a different
finalize defect, in the test-triage step rather than the closure step).

**Pattern:** a closure step that infers "what this branch delivered" from a store-wide
scan rather than from the branch, so its blast radius is the store and not the branch.

---

## Resolution — 2026-10-21

**Fixed by** PR #1292 (merge `aa762f3f4`, 2026-10-21), under ACs `BO-400e-3-ii` through
`BO-400e-3-ix` and `BO-4500a-5-iv`. All nine are `work_status: done` on origin/main.
Re-verified against the code at `aa762f3f4`, not against the PR description.

Remediation item 1, "scope Step 3.5 to the records the branch actually touched, derived from
the branch diff":

- **The closable set is computed in code, not chosen by an agent.** Step 3.5 of
  `templates/workflows-js/finalize-feature.js` runs
  `scripts/build_orchestration/finalize_closable_set.py derive`, then reads its reply. The
  inbox scan is gone.
- **Merge base plus the branch's own commits.** `_fcs_derive.py` measures from
  `git merge-base <base-ref> HEAD`, never a two-dot diff. A path counts only when it differs
  between the merge base and HEAD **and** one of the branch's own first-parent, non-merge
  commits touched it. Content that arrived by merging main never qualifies.
- **A single-ticket branch is bounded to its built-for ticket.** That ticket is read from
  `git config branch.<branch>.leafcutterTicket` and from nothing else, together with its
  `source_ac`. `setup_ticket_worktree.py` (both `scripts/` and `templates/scripts/`) writes
  the record through `_setup_ticket_branch_record.py`. It refuses a second, different ticket
  on the same branch name, and it refuses to set up a ticket branch at all when the helper is
  missing.
- **An epic branch is bounded to its own folder.** Only tickets under
  `tickets/<lane>/epics/<branch>/` are candidates.

Remediation item 2, "print the records it is about to close and require confirmation":

- **Listed and confirmed by a person.** The derived `listing_text` is shown at a
  `confirm` / `decline` gate. Only a resume answer from channel `person` counts as a yes.
- **The closer is bounded by a persisted, digested set.** `derive` writes the records and
  their digest under the worktree's git dir. `_fcs_close.py` refuses a set file outside the
  git dir, an unreadable one, or one whose digest does not match. A resumed answer is applied
  only when the re-derived set has the digest stored in the pause record.
- **A leak is detected, not assumed away.** The closer snapshots the status and content hash
  of every ticket and AC file before and after it runs. Any change outside the set halts with
  `closed_outside_set`, and nothing is committed.

The shape of the defect is also closed:

- **Explicit path staging.** The closure commit goes through `commit_changes.py` with the
  closer's `commit_paths` list only.
- **No `reset --hard`.** A Step 2 test merge still in progress is cleared with
  `git merge --abort` only, and the abort is re-checked. Neither Step 3.5 nor the
  `_fcs_*.py` modules contain `reset --hard` or `git add -A`.
- **Undeterminable outcomes halt before the merge.** These cases halt at Step 3.5 with
  "The PR has NOT been merged": no merge base, a failed git call, no built-for record, more
  than one record, uncommitted edits to candidate records, or an unreadable reply. Nothing
  falls back to a guess.
- **Closers keep their checks.** A ticket closes only through `set_ticket_status.py`, and an
  AC only through `mark_ac_done.py`. An AC closes only when the ticket that delivered it
  closed in the same run.

**Not covered here.** The two other finalize defects noted above were never this entry's
remediation, and PR #1292 does not claim them: the Step 3 build-layer false-halt and the
`poetry` bootstrap. Track them on their own entries.

**Not verified end-to-end.** No live `/finalize-feature` run against a real branch was made
for this closure. The verdict rests on the code at `aa762f3f4` and the tests PR #1292 added
under `unit_tests/build_orchestration/test_bo_400e_3_*.py` and
`unit_tests/workflows/test_bo_400e_3_*.py` / `test_bo_4500a_5_iv_finalize_commit.py`. If a
closure commit again touches records the branch did not deliver, file a new entry. Do not
reopen this one.
