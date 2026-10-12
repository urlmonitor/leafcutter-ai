---
title: "KI-CG-20260928-file-size-ratchet-refuses-when-both-parents-grew — the max-across-parents merge fix covers one side growing, not both, so a merge of two branches that each extended the same over-limit file is refused although neither branch's own growth was"
description: "medium — the merge-awareness added for KI-CG-20260908 takes the MAXIMUM previous length across parents, which is the right answer when one side grew. When BOTH parents grew the same already-oversized file, the merge result exceeds both, and the merge author is refused for growth that is the arithmetic of merging rather than anything they wrote. No action available to them fixes it."
type: reference
category: reference
status: active
created: '2026-09-28'
last_updated: '2026-09-28'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
---

# KI-CG-20260928-file-size-ratchet-refuses-when-both-parents-grew — the max-across-parents merge fix covers one side growing, not both

- **Severity:** medium. It blocks a merge rather than corrupting anything, and the growth it
  reports is real. But the only routes past it are `SKIP=check-file-size` or a refactor
  unrelated to the merge, so in practice it converts into a skip on a required-adjacent gate.
- **Status:** open — no AC. Diagnosed and measured, not fixed. The fix needs a semantics
  decision (below) rather than a patch.
- **Occurrences:** 1 observed (PR #862, 2026-09-28), but it applies to any merge where both
  parents extended the same file that was already over its limit.
- **First seen:** 2026-09-28 · **Last seen:** 2026-09-28
- **Where:** `templates/scripts/commit_guardian/_file_size_ratchet.py`,
  `resolve_parent_revisions` / `resolve_previous_lengths` and the permitted-previous-length
  rule they feed.

## Mechanism

`KI-CG-20260908-file-size-ratchet-refuses-merge-commits` established that during a merge the
permitted previous length is the **maximum** across every parent, not `HEAD`'s alone. That
module's own docstring states the reasoning: `HEAD` names only the branch being merged INTO,
so main's growth would otherwise look like growth the merge author caused.

Maximum-across-parents is correct when **one** side grew. It is insufficient when **both**
did, because the merged file contains both sets of additions and is therefore longer than
either parent:

```
                      build-feature.js (content lines, limit 1000)
  origin/main  (MERGE_HEAD)   2816
  branch       (HEAD)         2902     <- max across parents, the permitted previous length
  merge result                2964     <- refused: +62 over the maximum
```

Each side's growth passed the ratchet when it was committed. Only their union is refused,
and the union is not an act the merge author performed.

## Why it is not simply "the file did get longer"

It did, and that is why this is medium rather than high. But the gate's purpose is to stop a
person making an oversized file worse, and here no person did. The merge author's available
responses are:

- **Shrink the file by the union amount.** A refactor of a 2964-line driver, unrelated to the
  merge, performed under merge conflict resolution. This is the worst possible moment for it.
- **Convert `//` comments to `/* */`.** The measure excludes block comments, so this reduces
  the count without deleting anything. It is pure metric-gaming and should not be done.
- **`SKIP=check-file-size`.** What actually happened on PR #862, recorded in the commit
  message with the three line counts above.

## Evidence it is the rule and not the branch

The hook reported `Previous length: 2902` — the branch's count, not main's 2816. That is
positive proof the merge-awareness ran and read `MERGE_HEAD`, took the maximum, and still
refused. This is not the KI-CG-20260908 defect recurring; it is the next case along.

Verified with the module's own counter (`count_content_lines`) against all three blobs, so
the numbers above are the gate's own metric, not `git diff --numstat` — which would give a
different and wrong answer, since the measure discards block comments and docstrings.

## Candidate fix, and the decision it needs

The principled rule is: **compare the merge result against what the auto-merge alone would
have produced**, so only the merge author's own additions count. Growth introduced while
resolving conflicts is theirs; growth that is the sum of both parents' committed work is not.

`git merge-tree` can produce the would-be-merged blob without touching the working tree,
making this computable. What it needs first is a decision on two edge cases:

- A **conflicted** path has no single auto-merge result. Falling back to max-across-parents
  there keeps today's behaviour for exactly the files most likely to be hand-edited.
- An **octopus** merge has more than one pairwise auto-merge. The same fallback applies.

The naive alternative — "permit the union of both parents' lengths" — should be rejected. It
makes any growth launderable through a merge: extend a file on a branch, merge, and the
ratchet has no baseline that ever saw the pre-growth length.

## Pattern

A guard hardened for the case where one input changed, meeting the case where two did. The
first fix was correct and is not being undone; it just did not go one step further. Worth
checking whether the same shape exists in the other merge-aware gates —
`check-predone-scope` computes its changed-file set over the branch range and has a sibling
entry for a different reason (`KI-BO-20260923-0700`).
