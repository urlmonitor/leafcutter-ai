---
title: "KI-CG-20260914-ratchet-max-baseline-refuses-union-merges — `check-file-size`'s merge baseline is the MAXIMUM across parents, but a clean merge holds BOTH parents' additions, so a union that authored no new content still exceeds the permitted length and the gate refuses it"
description: "KI-CG-20260914-ratchet-max-baseline-refuses-union-merges — check-file-size uses max(HEAD, MERGE_HEAD) as its merge baseline, but a correct merge is a union of both parents' additions, so an auto-merged file nobody edited still exceeds the bound and the gate refuses the merge. Follow-on to the resolved KI-CG-20260908-ratchet-reads-pre-merge-head, not a regression of it."
type: reference
category: reference
status: active
created: '2026-09-14'
last_updated: '2026-09-14'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-20260914-ratchet-max-baseline-refuses-union-merges — `check-file-size`'s merge baseline is the MAXIMUM across parents, but a clean merge holds BOTH parents' additions, so a union that authored no new content still exceeds the permitted length and the gate refuses it

> One known issue. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high — blocks any substantive catch-up merge of `origin/main` into any long-lived branch, for anyone. The larger the divergence, the more certainly it fires: the defect is a property of merging itself, not of any file being oversized.
- **Status:** OPEN.
- **This is a FOLLOW-ON to `KI-CG-20260908-ratchet-reads-pre-merge-head` ([RESOLVED](resolved/resolved-high-ki-cg-20260908-ratchet-reads-pre-merge-head.md)), NOT a duplicate of it, and not a regression of that fix.** That entry covered the ratchet reading `HEAD` — the branch's *pre-merge* tip — so a file long-standing on `origin/main` but absent from the branch had no baseline at all and was judged against the absolute limit. `62410ca66` / PR #752 fixed exactly that by taking the MOST PERMISSIVE (maximum) previous length across every parent. That fix is present, deployed, and working: verified today by running the deployed `.leafcutter/scripts/commit_guardian/_file_size_ratchet.py` directly and observing it correctly report `HEAD=1707, MERGE_HEAD(origin/main)=1915, max permitted=1915` for `scripts/build.py`. Taking `max()` was the right answer to the narrower question that entry asked. The remaining gap is narrower still and was not in scope there: `max(A, B)` is the wrong bound when the merge result legitimately contains the additions of **both** A and B. Leaving KI-CG-20260908 closed — its defect really is fixed; this is the next one along the same seam.
- **Occurrences:** 1 observed live merge, refusing 4 files simultaneously.
- **First seen:** 2026-09-14 (merge of 95 `origin/main` commits into `EPIC-StartingNewWorkTheProperWayAlways`) · **Last seen:** same.
- **Where:** `templates/scripts/commit_guardian/_file_size_ratchet.py` — the merge branch added by `62410ca66` (`_merge_head_path()` at `:353` and the maximum-across-parents selection it feeds).

**Symptom.** A merge whose conflicts were all resolved, whose build was green and whose test suite was clean (693 passed / 5 xfailed) was refused by `check-file-size` on four files:

```text
❌ scripts/build.py: 1915 → 1976
❌ scripts/build_phases.py: 2848 → 2864
❌ templates/scripts/commit_guardian/check_done_proof.py: 663 → 665
❌ templates/scripts/setup_ticket_worktree.py: 1354 → 1441
```

**Mechanism, and the file that proves it.** `templates/scripts/setup_ticket_worktree.py` is the clinching case because **it never conflicted** — git auto-merged it, so no human and no agent wrote a line of the result. Its raw line counts: branch parent 1756, main parent 2150, merged result 2338. `git diff --cached origin/main --numstat` reported `191  3`, and 2150 + 191 − 3 = 2338 exactly. The merged file is therefore a pure union: all of main's 2150 lines, plus the 191 the branch added independently. A union of two divergent edits necessarily exceeds either parent alone, so `max(HEAD, MERGE_HEAD)` is an upper bound the result cannot satisfy while remaining a correct merge. The other three files fit the same shape (two conflicted and were union-resolved; `check_done_proof.py`'s +2 is the merged docstring of main's composite-level branch and this branch's `test_required` exemption).

**Note on reproducing the figures.** The ratchet reports a code-line metric, not raw `wc -l` — hence `1354 → 1441` for a file whose raw counts are 1756 / 2150 / 2338. A reader checking these numbers with `wc` will not reproduce them and should not conclude the entry is wrong.

**Workaround used, and its scope.** The merge commit `6378f4dd8` was landed with a user-authorised `SKIP=check-file-size`, recorded in that commit's own message as `[NO-HOOKS-OVERRIDE: check-file-size]` with the reason. `--no-verify` was NOT used and every other hook ran and passed. The bypass covers that one merge commit and nothing else; the ratchet remains fully active for ordinary commits, where its logic is correct.

**Fix direction — a SUGGESTION, not a decision; this needs its own AC.** For a merge commit the baseline should reflect both parents' contributions rather than the larger one — conceptually a union-aware bound. This is genuinely harder than the `max()` change that preceded it and must not be patched quickly: too generous a merge baseline lets real bloat through under cover of a merge, which is the failure this gate exists to prevent, and a merge is an unusually easy place to hide it. Specify the intended bound before implementing.

**Why not just split the four files.** The flagged content is legitimate merged code from both parents, verified additive against `origin/main`. Shrinking to satisfy the gate would mean deleting main's work or the branch's to make a number go down, and would leave the bound unchanged for the next catch-up merge.

**Related.**
- [`KI-CG-20260908-ratchet-reads-pre-merge-head`](resolved/resolved-high-ki-cg-20260908-ratchet-reads-pre-merge-head.md) (RESOLVED) — the previous defect on this same seam; its `max()` fix is the direct predecessor of this gap.
- [`KI-CG-20260914-ratchet-freezes-central-registries`](open-high-ki-cg-20260914-ratchet-freezes-central-registries.md) — same-day, same ratchet, different shape: there the per-file rule makes a growing registry unmaintainable; here the merge bound makes a correct merge unrepresentable. Both are cases of a per-file length rule meeting a situation its baseline does not model. Two entries, not a duplicate pair.
- `GE-127a-1` — registered `check-file-size` as `always_run`, which is again what turns a latent bound into a live, commit-blocking condition.

**Pattern:** this is the second follow-on found by fixing the *stated* case of a ratchet defect without revisiting the bound itself. `HEAD` → `max(parents)` answered "which parent do we compare against"; it never asked "is a single parent the right comparand for a merge at all".

---
