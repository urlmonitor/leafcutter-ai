---
title: "KI-CG-20261013-ac-done-on-merge-rewrites-an-ac-the-merge-did-not-touch — on a fast-forward onto a merge of main, check-ac-done-on-merge re-processed every done ticket main had changed and flipped main's own BO-2900a-1 from todo to done in the epic worktree, undoing main's deliberate demotion; main itself holds a done ticket whose source AC is todo"
description: "low — the post-merge hook reads `git diff --name-only HEAD~1 HEAD`, so after a merge of main (or a fast-forward onto one) it sees every file main changed since the merge base. Here that was 4,942 paths and 20 done tickets with a source_ac. One of them, 01_TICKET-20260925-BO-2900a-1 (status: done since 2af440d93), points at BO-2900a-1, which main deliberately set back to todo in b1b1532f7 when it suspended that rule. The hook called mark_ac_done.py --ticket with no --test-root and the AC became done, as an unstaged edit in an unrelated branch. Current main code would write in_progress instead (dry-run verified); the done is consistent with the install built before the merge."
type: reference
category: reference
status: active
created: '2026-10-13'
last_updated: '2026-10-13'
components:
  - commit_guardian
  - ac_store
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
  - docs/known-issues/commit-guardian/open-low-ki-cg-20260909-gate-ac-done-on-merge.md
  - docs/known-issues/commit-guardian/open-low-ki-cg-20260914-post-merge-stage-registers-but-installs-no-shim.md
  - docs/known-issues/build-pipeline/open-low-ki-bp-20261009-epic-worktree-install-goes-stale-per-ticket.md
---

# KI-CG-20261013-ac-done-on-merge-rewrites-an-ac-the-merge-did-not-touch — a merge of main re-applies main's ticket statuses to main's ACs, in someone else's branch

> Filed 2026-10-13 from the BO-4300 drive. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`).

- **Severity:** low. The write is an unstaged working-tree edit, and the hook says what it did. But it
  silently reverses a deliberate correction made on main, and a phase agent that stages AC files could
  carry it into an unrelated commit.
- **Status:** open, no AC. Hook, ticket and AC state verified on `origin/main` `964f23a60`. The flip
  itself is from the coordinator's session account.
- **Occurrences:** 1 (epic worktree of EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace, 2026-10-12).
- **First seen:** 2026-10-12 · **Last seen:** 2026-10-12
- **Where:** `templates/scripts/commit_guardian/hooks/check_ac_done_on_merge.py`: the diff is
  `git diff --name-only HEAD~1 HEAD` (`:62`); every `.md` with `status: done` and a `source_ac` is passed
  on (`:205-219`) to `mark_ac_done.py --ticket <path> --ac-root <root>`, with no `--test-root`
  (`:158-168`). Registered as `post-merge` (`commit_guardian.json:1472-1480`).

## Two defects

**(a) On main: a done ticket whose source AC is todo.**

- `tickets/00_inbox/epics/EPIC-AProofThatReachedTheCodeByDirectImport/01_TICKET-20260925-BO-2900a-1.md:44-45`:
  `source_ac: BO-2900a-1`, `status: done` (set in `2af440d93`, 2026-09-27).
- `docs/acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900a-1.yaml:11`:
  `work_status: todo`. `b1b1532f7` (2026-09-30) set it back from done on purpose: it suspended the
  entry-point rule to report-only, and "the suspension rejects nothing". Its four children
  (BO-2900a-1-i to -iv) are all `todo`.
- The epic's `Master_Plan.md` still says `status: in_progress`. Nothing reopened the ticket when its AC
  was demoted. The merge diff below holds 20 done tickets with a `source_ac` value. One value is `-`;
  of the 19 real ACs, this is the only one that is not `done` on main.

**(b) The hook acts on that mismatch in an unrelated branch.**

- `f65e2ca33` (2026-10-12) merged `origin/main` into the epic branch. Its first-parent diff, which is
  what `HEAD~1 HEAD` reads, lists **4,942 paths**, including the ticket above and the 19 other done
  tickets with a `source_ac` (verified).
- Inferred: the merge was made in a side worktree (`worktrees/bo4300-side`), and the epic worktree
  fast-forwarded onto it. `post-merge` fires on a fast-forward too, with the same `HEAD~1`.
- The hook called `mark_ac_done.py` for each. BO-2900a-1 in the epic worktree went `todo` → `done`. The
  epic branch never committed it (`work_status: todo` at tip `cc3c85edc`).

**Why `done` and not `in_progress` (inferred).** On main today, the same call (`--dry-run`) answers
"would mark BO-2900a-1 work_status=in_progress (unfinished children: ...)", because the BO-202
composite rule (`ed2190fd3`, 2026-10-06) keeps a composite open while its children are open. The epic's
`scripts/ac_store/mark_ac_done.py` lacked that rule before the merge (`f65e2ca33~1`) and has it after.
A post-merge hook runs the install built before the merge, so old code judged the new data.

## Detection

After any merge or pull, `git status` shows AC YAML files modified that the merge did not change. Or the
hook's stdout reports "marked <id> work_status=..." for ACs outside the branch's own work.

## Workaround

`git restore` the AC files the hook touched after merging main. Reopen or annotate tickets on main whose
source AC was deliberately demoted.

## Fix direction

- **Scope the diff to what the merge brought in that the branch did not already decide.** For a merge or
  fast-forward of main into a feature branch, main's own ticket closes were already applied on main. The
  hook should act only on tickets the *merging* branch closed (for example, ticket files whose status
  changed on the second parent's side when main is the first parent), or only on main itself.
- **Never move an AC back to done that is newer than the ticket.** If the AC's last change is later than
  the ticket's `status: done` change, report the mismatch and leave the AC alone.
- **Run the post-merge hook from the merged install, or rebuild first.** A hook that runs the pre-merge
  install judges new data with old rules (see `KI-BP-20261009-epic-worktree-install-goes-stale-per-ticket`).
- **Close the main-side mismatch:** when an AC is demoted, reopen its source ticket in the same commit,
  or let the ticket-lifecycle check refuse a done ticket whose source AC is not done.

**Related.** `KI-CG-20260909-gate-ac-done-on-merge` (written before the hook was registered; it
predicted this store-mutation risk). `KI-CG-20260914-post-merge-stage-registers-but-installs-no-shim`
(where the hook does and does not fire).

**Pattern:** a hook that treats one record (the ticket) as authoritative over another (the AC) without
asking which was changed last, and runs wherever the diff is, not where the decision was made.
