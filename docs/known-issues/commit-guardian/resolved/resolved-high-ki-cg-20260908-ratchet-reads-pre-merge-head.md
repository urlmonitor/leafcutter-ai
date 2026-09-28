---
title: "KI-CG-20260908-ratchet-reads-pre-merge-head — `check-file-size`'s ratchet resolves a file's previous length from `HEAD`, which during a merge is the branch's pre-merge tip, so a file long-standing on `origin/main` but absent from the branch is judged against the absolute limit and can refuse a merge for content the merge did not author"
description: "high — blocks any merge of `origin/main` into any branch, for anyone, whenever main holds a covered file over its line limit that the branch does not yet have. Not specific to this branch or to the two files below; they are today's instance"
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

# KI-CG-20260908-ratchet-reads-pre-merge-head — `check-file-size`'s ratchet resolves a file's previous length from `HEAD`, which during a merge is the branch's pre-merge tip, so a file long-standing on `origin/main` but absent from the branch is judged against the absolute limit and can refuse a merge for content the merge did not author

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../../commit-guardian.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high — blocks any merge of `origin/main` into any branch, for anyone, whenever main holds a covered file over its line limit that the branch does not yet have. Not specific to this branch or to the two files below; they are today's instances, and the next oversized file added to main re-triggers it against every branch that still lacks it.
- **Status:** RESOLVED 2026-09-08 (`62410ca66`, PR #752) — the ratchet is now merge-aware: `_merge_head_path()` in `_file_size_ratchet.py:353` reads `MERGE_HEAD`, and a file's permitted previous length during a merge is the MOST PERMISSIVE (maximum) across every parent, not `HEAD`'s alone. Covered by `unit_tests/commit_guardian/test_ki_cg_20260908_file_size_ratchet_merge_aware.py`, whose descriptors drive real `git init` / `git merge --no-commit` states and invoke the real `check_file_size.py` as a subprocess. Specified after the fact by `GE-127b-2`. Verified live: merge `928e53ad9` — the very merge this entry was filed from, retried after the fix landed — passed `check-file-size` with no `SKIP`. The `SKIP=check-file-size` bypass on `d0271d413` was used once, for that one earlier merge, and is not needed again.
- **ID reconciliation, because searching for the obvious id finds nothing.** The fixing commit and its test docstring both cite `KI-CG-20260908-file-size-ratchet-refuses-merge-commits`. **That id was never filed** — no register contains it. This entry, filed independently against the same defect, is the only record. A reader who greps the id named in the test will conclude the KI is missing rather than that it is under a different slug; that is what this bullet exists to prevent. Do not file the other id — one defect, one entry.
- **Occurrences:** 1 observed live merge, refusing 2 files simultaneously; the mechanism is structural, not incidental, and will recur on the next oversized file `origin/main` gains.
- **First seen:** 2026-09-07 (`check-file-size` registered live, GE-127a-1, `c13c22da4` / PR #728) · **Last seen:** 2026-09-08 (merge `d0271d413` refused on inherited content)
- **Where:** `templates/scripts/commit_guardian/_file_size_ratchet.py:194-230` (`_read_head_blob_bytes`; hardcoded `git show HEAD:<path>` at `:214`), `:287-314` (`get_previous_length`; hardcoded `git cat-file -e HEAD:<path>` at `:301`), `:233-284` (`resolve_head_covered_paths`; hardcoded `git rev-parse --verify HEAD` at `:265` and `git ls-tree -r --name-only HEAD` at `:272`) · `templates/scripts/commit_guardian/check_file_size.py:275-305` (`_classify_file`; falls through to the absolute-limit branch at `:303-304` whenever `previous_lengths.get(filepath)` at `:294` returns `None`)

**Symptom.** Merging `origin/main` into `fast-lane/ge-127a-1` — a merge whose only real conflict was three marker lines in `GE-127a-1.yaml` — was refused with:

```text
❌ FILE TOO LARGE:
   unit_tests/portability/test_ge_120e_2_i.py
   Lines: 462 (Limit: 400)
❌ FILE TOO LARGE:
   unit_tests/portability/test_ge_120e_4.py
   Lines: 501 (Limit: 400)
```

Both files were already committed on `origin/main` via `eaf49388b` and are untouched by the branch — confirmed with `git ls-tree origin/main --name-only <path>` (both present) and by checking every pre-merge commit on the branch for either filename (neither appears).

**Mechanism.** The ratchet (GE-127b-1, `c7fb650a3`, #710) exists precisely so an already-oversized file can still be worked on without every ordinary commit to it being refused: it reads the file's length at `HEAD` and only refuses a file that has *grown* past that. But every lookup in `_file_size_ratchet.py` is hardcoded to the literal ref `HEAD` — `git show HEAD:<path>`, `git cat-file -e HEAD:<path>`, `git rev-parse --verify HEAD`, `git ls-tree -r --name-only HEAD` — with no branch for a merge in progress. **During a merge, `HEAD` is the branch's PRE-merge tip**, not the merge result and not `origin/main`. A file that has lived on `origin/main` for any length of time but has never yet existed on the branch has no `HEAD` blob, so `get_previous_length` returns `None`; `check_file_size.py`'s `_classify_file` then falls straight past the ratchet branch (`previous is not None and previous > limit`, `:296`) to the plain `lines > limit` comparison, and the file is judged against the absolute 400-line limit as if it were new content the merge itself introduced — when in fact the merge introduces none of it.

**Blast radius is everyone, not this branch.** Nothing about the mechanism is specific to `fast-lane/ge-127a-1` or to these two test files. `check_file_size.py`'s own module docstring notes the ratchet was built to avoid "refusing essentially every commit that touches one of the ~200 files already over their limit" — and that same population is exactly what makes this structural rather than a one-off: any branch merging `origin/main` hits this the moment main holds a covered file over its limit that the branch does not yet have. The two files named above are today's instances; the next oversized file landed on main reproduces the same refusal against every other in-flight branch.

**Workaround used, and its scope.** `SKIP=check-file-size` was applied to the merge commit only (`d0271d413`), recorded in that commit's own message. This is a bypass, used once, for this merge, and nothing more — `check-file-size` remains fully active for ordinary commits, which is where its ratchet logic continues to do its job correctly.

**Fix direction — SHIPPED, see Status above; retained as the reasoning behind what was built.** Resolve the previous-length source from `MERGE_HEAD` (or the merge's other parent) instead of `HEAD` whenever a merge is in progress, so a file inherited from main is judged against main's own copy under the ratchet — exactly as any other already-oversized file already is. A merge commit authors no new content of its own; judging content it did not write against the absolute limit, rather than against where that content already stood, is the wrong question. Splitting the two named files is explicitly NOT the fix: it clears today's instance and leaves the `HEAD`-only lookup in place to refuse the next branch against the next oversized file main gains.

**The other reading, and why it loses.** One could argue a merge should be exactly the moment to refuse debt entering a branch, on the theory that letting it through defers a problem. It loses here because the debt is not entering anything: it already exists on `origin/main`, unconditionally, regardless of whether any given branch ever merges it in. The branch merging main has no authorship over that file and no way to have prevented its state. Refusing the merge does not stop the debt from existing — it only makes `origin/main` unmergeable into any branch that has not already independently split the same files, which is a strictly worse outcome than the debt itself.

**Related.**
- `GE-127b-1` (`c7fb650a3`, #710) — the ratchet this defect lives inside; its HEAD-vs-limit logic is correct for an ordinary commit and wrong only for the merge case this entry covers.
- `GE-127a-1` (`c790986b9`, #728) — registered `check-file-size` as `always_run`, which is what turned this from a latent gap (the hardcoded `HEAD` lookup had existed since GE-127b-1) into a live, commit-blocking condition — the same way registration did for the two entries below.
- `KI-BP-20260907-no-gitignore-for-consumers` (`docs/known-issues/build-pipeline.md:4141`) — same registration event, a different way it turned a latent condition into a live one.
- `KI-BP-20260907-bootstrap-swallows-build-failure` (`docs/known-issues/build-pipeline.md:1990`) and `KI-BO-20260907-resume-replays-cached-resolver` (`docs/known-issues/build-orchestration.md:2886`) — same-day neighbours in the sibling registers, cross-referenced only as same-day context, not because they share this defect's mechanism.

**Pattern:** registering a gate as `always_run` is what turns a latent, always-true condition (here: a ref lookup that was never merge-aware) into a live, repo-wide blocker — the third instance of that shape filed within the same week.

---
