---
title: "Proving a fix is real no longer gambles with another session's stash"
date: "2026-09-14"
time: "13:22"
type: manual
components:
  - build_pipeline
summary: "The /quick-fix mutation proof used to set the fix aside with `git stash push` and bring it back with an unqualified `git stash pop`, which takes whatever entry is on top of a stack every session in the repository shares — so following the step as written popped a concurrent session's work instead. It now reverts through two files in /tmp, materialising HEAD's content into a temp file of its own rather than redirecting over the target, and proves the restore by byte-comparison instead of inferring it from git status. The same recipe lived in both the skill prose and the JS workflow that actually executes; both were corrected, because fixing only the one the report named would have left the executing path unchanged."
description: "templates/skills/quick-fix/SKILL.md Step 4.2 and the mutation-proof agent prompt in templates/workflows-js/quick-fix.js both replaced `git stash push -- <file>` / `git stash pop` with: cp the fixed copy to /tmp/quickfix-<ac-id>-fixed.bak; `git show HEAD:<path>` into /tmp/quickfix-<ac-id>-head.orig; cp that over the target to revert; cp the saved fix back to restore; `diff -q` to prove the restore. The HEAD content goes to its own temp file because `git show HEAD:<path> > <path>` truncates the target before git runs, so a failed lookup would destroy the fix the proof exists to protect. fix_restored is now set from the diff rather than from `git status --porcelain`, which only proves the path differs from HEAD — equally true of a partial restore — and the restore step is required on the failing path as well as the passing one. The blocked-path recovery message names the /tmp backup instead of a stash entry. The skill's Guard BP-600a-3 block, which advised a bare `git stash` for the user's own work, now advises `git stash push -m \"<label>\"` and popping that entry by its own stash@{n} ref found via `git stash list`. New AC BP-600c-3-ii constrains the mechanism under the mechanism-agnostic BP-600c-3, which needed no change."
commits:
  - e52aaa4be
breaking: false
---

## Entry

### The gap: a proof step that could destroy what it was protecting

`BP-600c-3` requires the mutation proof to revert the fix, observe red, restore it and
observe green — green-after-red alone does not show the test is coupled to the fix. It
says nothing about *how* to revert, and the two surfaces that implement it both chose
`git stash`.

That choice is unsafe for a reason that has nothing to do with quick-fix. The stash
stack is per-repository, not per-session or per-worktree, and `git stash pop` with no
argument pops whatever entry is on **top** of it. The entry on top is not necessarily
the entry you pushed. Run the step as written while another session holds a stash entry
and you pop theirs.

That is not hypothetical. It happened: the recipe was followed verbatim, a concurrent
session's stash was consumed, and the work was recovered from the stash commit's SHA —
but only because foreign content turning up in the working tree was noticed. A silent
loss was equally available, and quieter.

### Reverting without shared state

Both surfaces now use two files in `/tmp` and touch nothing any other session can see:

```
cp <target> /tmp/quickfix-<ac-id>-fixed.bak
git show HEAD:<target> > /tmp/quickfix-<ac-id>-head.orig
cp /tmp/quickfix-<ac-id>-head.orig <target>   # revert; expect red
cp /tmp/quickfix-<ac-id>-fixed.bak <target>   # restore; expect green
diff -q /tmp/quickfix-<ac-id>-fixed.bak <target>
```

Two details are load-bearing and are stated in the instructions as such.

The HEAD content goes into a temp file of **its own** rather than being redirected over
the target. The obvious one-liner — `git show HEAD:<path> > <path>` — is a trap: the
shell truncates the target before git runs, so if the lookup fails for any reason the
fix is gone, destroyed by the step whose entire purpose is to put it back afterwards.

And `fix_restored` now comes from `diff -q`, not from `git status --porcelain`. The old
check asked whether the path still shows as modified; that only proves it differs from
`HEAD`, which is just as true of a partial or corrupted restore as of a correct one. A
byte-comparison against the copy that was saved answers the question actually being
asked. The restore is also now required on the failing path, not only the passing one —
a proof that halts and leaves the fix reverted is worse than one that never ran.

### Two copies of one instruction

The field report named Step 4.2 of the skill. The skill's own header says both surfaces
are real and a behavioural change must land in both, and it is right: the mutation-proof
agent prompt inside `quick-fix.js` carried the identical `stash push` / `stash pop` pair,
and that is the copy that runs on the workflow path. Correcting the prose alone would
have produced a file describing something that does not happen, while the hazard stayed
live.

`BP-600c-3` itself is unchanged. It is mechanism-agnostic — it requires the revert and
the restore, not any particular way of performing them — so the constraint belongs in a
new child, `BP-600c-3-ii`, rather than in an amendment to it.

### Verification

All under `AC_ENFORCE_STRICT=1`, without which a failing test on a not-yet-done AC is
downgraded to `xfail` and shows a false green:

- New guard test red at **5 failed** before the change, green at **5 passed** after.
- Mutation-proved per target file, using the new stash-free mechanism itself: reverting
  `SKILL.md` alone turned exactly its 3 tests red and left the 2 JS tests green;
  reverting `quick-fix.js` alone turned exactly its 2 red and left the 3 skill tests
  green. Both restores verified by `diff -q`.
- Quick-fix-adjacent suites — `workflows/`, the build guard, the dual-engine and
  variant-transform tests: **700 passed, 1 xfailed**.
- AC store — `OK: all 34 AC YAML files are valid`.

One related test broke and was corrected rather than deleted:
`test_quick_fix_workflow.py`'s recovery-instructions test asserted the halt message
contains the word "stash". Its intent — the halt must tell the user how to recover the
fix — is unchanged, so it now requires the `/tmp` backup path and forbids any mention of
the stash stack.

The guard test matches stash **operations** (`push`, `pop`, `list`, …) rather than the
bare string, and scans only fenced command blocks in the markdown. A first draft matched
the string anywhere and failed on the new text's own prohibition — the sentence telling
you not to use `git stash` necessarily contains `git stash`.
