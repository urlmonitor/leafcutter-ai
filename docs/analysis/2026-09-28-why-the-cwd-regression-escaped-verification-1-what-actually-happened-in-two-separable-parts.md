---
title: "What actually happened, in two separable parts — the cwd regression escape"
description: "Miss A (the operator ran the wrong subset of a correct test file list, with zero causal weight) and Miss B (the verification run inherited a working directory where the new cwd-dependent code path was unreachable, which alone caused the escape). Plus two systemic facts: the hazard was documented in the file the change broke, and the repository's own testing instruction prescribes the fatal working directory."
type: explanation
status: active
created: 2026-09-28
last_updated: 2026-09-28
components:
  - build_orchestration
  - testing_quality
related_docs:
  - docs/analysis/2026-09-28-why-the-cwd-regression-escaped-verification.md
---

> **Parent document:** [2026-09-28-why-the-cwd-regression-escaped-verification.md](2026-09-28-why-the-cwd-regression-escaped-verification.md)

## 1. What actually happened, in two separable parts

### Miss A — the wrong subset of a correct file list

Before the change the operator grepped for test files referencing
`setup_ticket_worktree`, got fifteen, ran four of them
(`tests/test_setup_ticket_worktree.py`, `unit_tests/test_setup_ticket_worktree.py`,
`unit_tests/setup/test_setup_ticket_worktree.py`, `unit_tests/test_bp_900g_6_paths.py`
— 46 passed) and skipped the `build_orchestration` files on the reasoning that a
separate PR's run had already covered that directory. That other PR's branch did not
contain this change, so the reasoning does not hold: a green run of directory *D* on a
branch without change *C* is evidence about *D*, not about *C*.

**What Miss A alone would have caught: nothing.** This is the load-bearing point. Had
all fifteen files been run, they would have run from the same working directory as the
four that were run, and they would all have passed. Miss A is a real process defect
with, in this instance, zero causal weight on the outcome.

**Two further facts make the grep itself weaker than "the correct list was in hand."**

- The grep is a one-hop textual approximation of a dependency edge. Three of the five
  files in the family that broke —
  `unit_tests/build_orchestration/test_bo2400f_13i_own_leftover_report.py`,
  `test_bo2400f_13iii_refusal_is_inert.py`, `test_bo2400f_13iv_free_location_proceeds.py`
  — do **not** contain the string `setup_ticket_worktree` at all. Verified:
  `git grep -L setup_ticket_worktree` over those three paths returns all three. They
  reach the script only through `unit_tests/build_orchestration/_bo2400f13_fixtures.py`.
  So even the "correct fifteen" was 60% of the family that mattered.
- Run today, the same grep returns 23 files under `tests/` and `unit_tests/`, not
  fifteen. Whatever the difference (branch state, pattern), the list was not stable
  enough to reason about by exclusion.

### Miss B — the verification inherited the operator's working directory

`_git_toplevel()`'s new candidate list is
`[("process working directory", Path.cwd()), ("script's own directory", …)]`
(`scripts/setup_ticket_worktree.py:170-171`). The operator's shell cwd is
`/home/henzeh/projects/leafcutter`, the untracked workspace parent, which is
deliberately **not** a git repository (ADR-001 layout: `leafcutter-ai/` is the git
root, the parent holds build outputs). From there the cwd candidate raises and
execution falls through to the script's own directory — byte-for-byte the old
behaviour. CI checks out the repository and runs
`python -m pytest tests/ unit_tests/ -q` from the checkout root
(`.github/workflows/ci.yml:192`), where the cwd candidate resolves, wins, and the
regression is exposed.

Reproduced here today, one variable changed:

```
env --chdir=/home/henzeh/projects/leafcutter/worktrees/worktree-git-toplevel-anchor \
  python -m pytest unit_tests/build_orchestration/test_bo2400f_13ii_foreign_occupant.py -p no:randomly -q
  → 6 failed in 21.47s

env --chdir=/home/henzeh/projects/leafcutter \
  python -m pytest <same file, absolute path> -p no:randomly -q
  → 6 passed in 0.76s
```

(The incident record has 5 failed / 1 passed for this file; I observe 6/6 with random
ordering disabled. Same direction, and the family carries real cross-test git state, so
ordering moves the count. The discrepancy does not affect the conclusion.)

**Why the tests are cwd-dependent at all.** The fixture module isolates by *script
location*, not by cwd. `_bo2400f13_fixtures.py:113-125` (`stage_script`) copies the
script under test into `<fixture_repo>/scripts/`, and
`_bo2400f13_fixtures.py:129-143` (`run_create_fastlane_worktree`) invokes it with
`subprocess.run([...])` and **no `cwd=` argument** — so the child inherits pytest's
working directory. Under the old order the inherited cwd was never consulted and the
isolation held. Under the new order the inherited cwd is consulted first and the
isolation is void. The tests did not change; their isolation mechanism was silently
removed from underneath them.

**What Miss B alone would have caught: everything, provided Miss A had not also
occurred.** Running the fifteen files from a repo-root cwd fails loudly and
immediately. Miss B is the miss with the causal weight; Miss A is what removed the
only run that Miss B could have turned red.

**Both were necessary.** Miss A alone: green, because cwd was wrong. Miss B alone (all
fifteen run, from the workspace parent): green, because cwd was wrong. The escape needs
the subset choice *and* the directory. Any post-mortem that names only one of them will
write a guard that does not close the hole.

### The two facts that make this systemic rather than personal

**The hazard was written down, in the file the change broke.** `_bo2400f13_fixtures.py`
carries a section header addressed to exactly the person making this change:

> `=== The _git_toplevel() anchoring trap (read before editing) ===`
> "`_git_toplevel(anchor=None)` resolves the repository root from
> `Path(__file__).resolve().parent` — the SCRIPT'S OWN directory — not the process cwd
> and not an argument. Invoking the real deployed script in place … could create real
> worktrees/branches inside the actual development tree."
> (`unit_tests/build_orchestration/_bo2400f13_fixtures.py:20-42`)

That warning states the invariant BO-4100d-4 inverted, and predicts the exact
consequence. It is not a comment buried in a test body; it is a titled block in a
module docstring, in the directory the operator was told about and chose not to run.
Nothing mechanical surfaced it, so it did not matter.

The prediction is accurate. Running one of those files from a repo-root cwd to produce
the evidence above created **seven real git worktrees and seven real branches in the
actual development repository**
(`/home/henzeh/projects/leafcutter/worktrees/worktrees/{bare-dir-foreign-slug,
detached-head-slug, distinguish-foreign-slug, distinguish-own-slug,
no-destructive-foreign-slug, other-branch-foreign-slug, unreadable-listing-slug}`,
branches `fast-lane/<slug>`). They have been removed and the tree is clean. This
matters beyond tidiness: **the regression's failure mode is not "14 red tests," it is
"the test suite mutates the developer's real repository."** The 28× runtime difference
(0.76s versus 21.47s) is the observable signature — the green run was suspiciously
cheap because it was doing the isolated work; the red run was slow because it was doing
real git work on the real repo.

**The repository's own testing instruction prescribes the fatal working directory.**
`CLAUDE.md:649-659`, "Full test suite + ruff at epic-finalize", says in prose to run
"from the worktree root" and then gives a recipe explicitly shaped so that you need not
be there:

```bash
python -m pytest <worktree-root>/unit_tests/ -q
```

An absolute test path run from anywhere. Combined with the global shell convention —
absolute paths, never `cd` — the operator's standing cwd at the workspace parent is not
a lapse; it is the prescribed posture. The instruction's prose and its command disagree,
and the command is what gets executed.
