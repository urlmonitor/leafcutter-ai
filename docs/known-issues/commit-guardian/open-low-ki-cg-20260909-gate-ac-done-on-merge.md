---
title: "KI-CG-20260909-gate-ac-done-on-merge — the only gate of the twelve that writes, never run here, and registration points it at 354 tickets"
description: "medium — zero blocking risk, non-zero store-mutation risk."
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-10-13'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
  - docs/known-issues/commit-guardian/open-low-ki-cg-20261013-ac-done-on-merge-rewrites-an-ac-the-merge-did-not-touch.md
---

# KI-CG-20260909-gate-ac-done-on-merge — the only gate of the twelve that writes, never run here, and registration points it at 354 tickets

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium — zero blocking risk, non-zero store-mutation risk.
- **Status:** open — no AC. Needs its own session; dry-run before registering.
- **Occurrences:** measured once, `df1f0cfb5`; the predicted store write observed once, 2026-10-12 (below). · **First seen:** 2026-09-09 · **Last seen:** 2026-10-12
- **Where:** `templates/scripts/commit_guardian/hooks/check_ac_done_on_merge.py`; proposed as `stages: [post-merge]`.

**What it does.** For every `.md` in `git diff HEAD~1 HEAD` carrying `status: done` plus `source_ac`, it shells out to `mark_ac_done.py`. It always returns 0, so it can never block a merge. **354 tracked tickets carry both fields.**

**Why it still needs a session.** It is the only one of the twelve with a side effect, it has never executed in this repo, and `mark_ac_done.py` mutates the AC store — the store this whole guardrail family exists to keep honest. A first run against 354 live records is not the place to discover a mismatch between what the hook thinks `status: done` means and what `mark_ac_done.py` does with it. Note also that `mark_ac_done.py` gates on a passing covers-tagged test but does not populate `implemented_by`, so a bulk run could produce records that are `done` with empty implementation evidence — the phantom-done shape, created by the tool meant to prevent it.

**Definition of done.** A dry-run mode exists and has been run against all 354 with its diff reviewed; the `implemented_by` question is answered explicitly; only then registered. No ratchet needed — it does not refuse anything.

## Observed again, 2026-10-13: the hook wrote a wrong status

The hook has been registered on `post-merge` since `5d0792d13` (PR #808, 2026-09-14), so the
"never executed" premise above no longer holds. On 2026-10-12 it ran on a fast-forward onto a merge of `origin/main`
into `epic/every-piece-of-separate-work-gets-its-workspace`. It re-processed every done ticket main had
changed since the merge base, and flipped main's own BO-2900a-1 from `todo` to `done` in the epic
worktree. That undid main's deliberate demotion of BO-2900a-1 (`b1b1532f7`). This is the "mismatch
between what the hook thinks `status: done` means and what `mark_ac_done.py` does with it" predicted
above. The mechanism, and the done-ticket/todo-AC mismatch on main that triggered it, are filed as
`KI-CG-20261013-ac-done-on-merge-rewrites-an-ac-the-merge-did-not-touch`.

---
