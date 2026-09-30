---
title: "What the two implementations actually do — git-toplevel resolution contract"
description: "Measured behaviour of main's anchor-plus-search resolver and PR #866's cwd-first resolver across the dev and consumer layouts, plus a third defect neither record mentions: _resolve_installed_layout() misclassifying the consumer layout when handed the deployed copy's resolved root."
type: explanation
status: active
created: 2026-09-28
last_updated: 2026-09-28
components:
  - worktree_manager
  - build_orchestration
  - build_pipeline
  - ac_driven_dev
related_docs:
  - docs/analysis/2026-09-28-git-toplevel-resolution-contract.md
---

> **Parent document:** [2026-09-28-git-toplevel-resolution-contract.md](2026-09-28-git-toplevel-resolution-contract.md)

## 2. What the two implementations actually do

Measured with `/tmp/probe_layouts.py`. "Correct" is per §1.

| Layout | cwd | `main` returns | PR #866 returns | Correct |
|---|---|---|---|---|
| Consumer, deployed copy | `<consumer>` | `<consumer>` ✅ | `<consumer>` ✅ | `<consumer>` |
| Consumer, deployed copy | an unrelated repo | `<consumer>` ✅ | **`<other-project>`** ❌ silent | `<consumer>` |
| Dev, deployed copy | workspace root | raises (git 128) ❌ | raises, better message ❌ | `<ws>/leafcutter-ai` |
| Dev, deployed copy | inside a worktree | raises ❌ | **`<ws>/worktrees/some-feature`** ❌ silent | `<ws>/leafcutter-ai` |

Three things follow, and each is load-bearing.

**PR #866 does not fix the incident it was filed for.** In the dev layout neither
candidate is a repository, so the deployed copy still cannot create a worktree. The
branch's own changelog says so outright
(`changelogs/2026-09-22-2250-…-rather-than-the-one-it-is-standing-in.md`): *"the deployed
copy now refuses clearly instead of crashing opaquely but still cannot create a worktree,
and the fast lane remains blocked in this workspace."* Reproduced verbatim against the
live install: `git -C /home/henzeh/projects/leafcutter/.leafcutter/scripts rev-parse
--show-toplevel` → `fatal: not a git repository`, exit 128. PR #866's dev-layout
contribution is the error message and nothing else.

**PR #866 creates a new silent wrong-repository bug where `main` was correct.** Row 2:
with the deployed copy inside the adopter's project and the caller's cwd in some other
repository, `main` returns the adopter's project and PR #866 returns the other
repository. No exception, no warning. This is precisely the failure mode
`BO-4100d-4`'s own criteria forbid — *"it never reports success for a workspace created
in a different repository from the one the caller asked about"* — produced by the change
written to prevent it. It is also the shape
`KI-BO-20260921-worktree-base-resolver-defaults-to-cwd` exists to warn about: a default
taken from ambient state that is right in one layout and silently wrong in another. That
entry's own fix direction reads *"a default of the repository root rather than the
process cwd would have made this a loud failure."* PR #866 did the thing the entry warns
against, and the changelog's claim that it is *"deliberately NOT a plain cwd default"* is
not supported by the code: with no explicit anchor, cwd is tried first
(`templates/scripts/setup_ticket_worktree.py:168-169`).

**The regression is not confined to the test suite.** Row 4 is the observed test failure.
`env --chdir=<worktree> python -m pytest
unit_tests/build_orchestration/test_bo2400f_13ii_foreign_occupant.py` → 6 failed, with
the payload naming
`/home/henzeh/projects/leafcutter/worktrees/worktrees/unreadable-listing-slug`. That
nested `worktrees/worktrees` is row 4 arithmetic: cwd resolves to the *worktree*, so
`_resolve_installed_layout()` makes `worktrees_base` the worktree's parent
(`…/worktrees`) and appends `worktrees` again. The harness
(`unit_tests/build_orchestration/_bo2400f13_fixtures.py:130-144`) invokes the script as a
subprocess with **no `cwd=` argument**, so the child inherits pytest's cwd; the harness's
documented "anchoring trick" (`:114-127`) is to stage the script inside the temp repo,
which only works under script-dir-first.

**Collateral, on disk, in the live repository.** Those runs did not merely fail. `git
worktree list` shows **seven real worktrees** under
`/home/henzeh/projects/leafcutter/worktrees/worktrees/` — `bare-dir-foreign-slug`,
`detached-head-slug`, `distinguish-foreign-slug`, `distinguish-own-slug`,
`no-destructive-foreign-slug`, `other-branch-foreign-slug`, `unreadable-listing-slug` —
with seven matching `fast-lane/*` branches dated 2026-09-28 07:02 and 07:37 UTC. They are
not fixtures; they are registered worktrees of the real `leafcutter-ai` repository,
created because the resolver pointed the test's temp-repo operations at the live one.
They also poison re-runs: a repeat of the same test file now classifies the occupant as
`own_prior_attempt` rather than reaching the original assertion, so the failure mode
itself has mutated. **They should be pruned before any further work on this branch.** No
code, test or AC was changed in producing this analysis, and these were left in place
rather than removed unilaterally.

### A third defect, in both implementations, that neither record mentions

Row 1 above is marked ✅ for `_git_toplevel()` only. The full probe shows what happens
next:

```
CONSUMER layout, deployed copy, cwd=<consumer>
  main   : toplevel=<root>/consumer   repo_root=<root>/consumer  worktrees_dir=<root>/worktrees
  PR#866 : toplevel=<root>/consumer   repo_root=<root>/consumer  worktrees_dir=<root>/worktrees
```

`_resolve_installed_layout()` assumes its argument is the *leafcutter-ai* repository and
classifies the layout by probing that repository's parent. Hand it the consumer root —
which is what the deployed copy resolves to — and the parent is not a repository, so it
reports "dev layout" and puts `worktrees_base` **one level above the adopter's project**.
Worktrees land as a sibling of the consumer's repo, outside it entirely. Both
implementations do this. Any fix to `_git_toplevel()` that does not also fix this is
half a fix, because the consumer layout's deployed copy hits it unconditionally.
