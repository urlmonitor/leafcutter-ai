---
title: "A merge adopts the other parent's length, it does not grow the file"
date: "2026-09-08"
time: "09:10"
type: manual
components:
  - commit_guardian
summary: "The file-size ratchet resolved a file's previous length from HEAD alone, so during a merge the other parent's already-accepted growth of an oversized file read as new growth the merge author had introduced. Registering the gate (GE-127a-1) therefore made most merges unpassable except via SKIP=, since build.py and done_proof.py are both over their limits and both change constantly on main. A merge's permitted previous length is now the maximum across every parent — HEAD plus every line of MERGE_HEAD."
description: "check_file_size.py delegates previous-length resolution to _file_size_ratchet.py, which read the blob at HEAD and nothing else. During `git merge origin/main`, HEAD names only the branch being merged INTO; the other parent can already carry a longer length for the same already-oversized file, grown there in commits this same gate had vetted on that side. Judging the merge result against HEAD's length alone therefore attributed all of that already-accepted growth to whoever ran the merge. Reproduced on a real in-progress merge in a bp-100n-4 worktree: seven files refused — scripts/build.py 1884->1906, scripts/ac_store/done_proof.py 937->1347, scripts/build_referential_integrity.py 1031->1039, check_contract_shrinking.py 401->443, check_done_proof.py 466->640, plus unit_tests/portability/test_ge_120e_2_i.py and test_ge_120e_4.py refused outright as TOO LARGE at 462 and 501 against a 400 limit. Every one of those lines was authored on main. The rule is now that a merge's permitted previous length is the MOST PERMISSIVE length across every parent, not HEAD's alone: growth beyond what EVERY parent already had is the only growth a commit is answerable for. The same reasoning settles the absolute-limit crossing refusal, since a file already over its limit on ANY parent was not taken over the limit by this commit. _classify_file() is deliberately untouched — it already judged a file against whatever previous length it was handed, so correcting the baseline fixes both the ratchet refusal and the crossing refusal without a single new branch in the decision itself. MERGE_HEAD is located with `git rev-parse --git-path MERGE_HEAD` and read in full, every non-blank line: the naive `git rev-parse -q --verify MERGE_HEAD` resolves only the FIRST line and silently drops every later parent of an octopus merge, the exact mistake check_package_surface_declaration.py's docstring already documents, so this follows that precedent rather than rediscovering it. --git-path also resolves correctly inside a linked worktree, where MERGE_HEAD lives under the worktree's private git-dir. An ordinary commit's parent set is just [HEAD], making its behaviour byte-identical to before. A merge whose parent set cannot be established, or whose MERGE_HEAD exists but cannot be read, raises PreviousLengthSourceError and exits 2 INDETERMINATE rather than quietly falling back to a smaller, wrong baseline — fail closed, per GE-127b-1-i's own floor. Cherry-pick and revert stage against CHERRY_PICK_HEAD / REVERT_HEAD and the argument may extend to them, but neither writes a competing multi-parent baseline the way MERGE_HEAD does and no reproducible false refusal was found for either, so both are left for a follow-up with a real reproduction behind it rather than built on speculation."
breaking: false
---

## Entry

### The defect

The ratchet asked one question — *how long was this file at HEAD?* — and during a merge
that is the wrong parent to ask. `HEAD` is the branch being merged **into**. The other
parent routinely carries a longer version of the same oversized file, grown there in
commits this very gate already approved on that side.

So the gate charged the merge author for growth they did not write. With `build.py` and
`done_proof.py` both over their limits and both changing constantly on main, that made
most merges unpassable by any route except `SKIP=`.

### Reproduced on a real merge

| file | HEAD | merge result | verdict before |
|---|---|---|---|
| `scripts/ac_store/done_proof.py` | 937 | 1347 | refused |
| `scripts/build.py` | 1884 | 1906 | refused |
| `scripts/build_referential_integrity.py` | 1031 | 1039 | refused |
| `check_contract_shrinking.py` | 401 | 443 | refused |
| `check_done_proof.py` | 466 | 640 | refused |
| `test_ge_120e_2_i.py` | — | 462 | too large (limit 400) |
| `test_ge_120e_4.py` | — | 501 | too large (limit 400) |

### The rule

A merge's permitted previous length is the **maximum across every parent** — `HEAD` plus
every line of `MERGE_HEAD`. Growth beyond what *every* parent already had is the only
growth a commit is answerable for. The same reasoning settles the crossing refusal: a file
already over its limit on **any** parent was not taken over the limit here.

`_classify_file()` is untouched. It already judged a file against whatever previous length
it was handed, so fixing the baseline fixes both refusals with no new branching.

### Why MERGE_HEAD is read the long way

`git rev-parse -q --verify MERGE_HEAD` resolves only the **first** line and silently drops
every later parent of an octopus merge. `git rev-parse --git-path MERGE_HEAD` plus reading
every non-blank line is what `check_package_surface_declaration.py`'s docstring already
prescribes — this follows that precedent rather than rediscovering the bug. `--git-path`
also resolves inside a linked worktree.

### Coverage — the mutation table, not the count

Six tests, each building a real git repo in a tmpdir and driving a real merge. None writes
`MERGE_HEAD` by hand or mocks a git call: the defect lives in how the gate reads real git
state, and a mocked test would have passed against the broken code.

**Three are RED against the unfixed gate** (verified by stashing the two production files:
`3 failed, 3 passed`, then `6 passed` once restored):

- a merge adopting an already-grown oversized file from the other parent;
- an octopus merge — also fails any first-line-only `MERGE_HEAD` read, since the first
  additional parent never touched the file;
- an unreadable `MERGE_HEAD` mid-merge must be INDETERMINATE, not a refusal.

**Three pass both before and after**, and are stated as such rather than padding the count.
They exist to catch an over-broad fix that simply switches the gate off during a merge: a
merge result larger than *every* parent is still refused; a non-merge commit growing an
oversized file is still refused; a non-merge commit crossing the limit is still refused.

### Verified

`unit_tests/commit_guardian/` in full under `AC_ENFORCE_STRICT=1` — **1438 passed, 4
skipped, 1 xfailed, 168 subtests, 0 failed**, including the 27 pre-existing GE-127a-1 /
GE-127b-1 / GE-127b-1-i ratchet tests. `ruff` clean on all three files.

Only `templates/` is touched: `scripts/commit_guardian/` is gitignored in this
self-hosting layout and reached through a symlink into `.leafcutter/`, so there is no
tracked build-output copy to mirror (`git ls-files scripts/commit_guardian` returns
nothing).

### Still open

Cherry-pick and revert stage against `CHERRY_PICK_HEAD` / `REVERT_HEAD` and the same
argument may apply, but neither writes a competing multi-parent baseline and no
reproducible false refusal was found. Left for a follow-up with a real reproduction behind
it.
