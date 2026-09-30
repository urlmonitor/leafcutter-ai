---
title: "The worktree tool should resolve the repository from the install it is part of, not from its own directory and not from the caller's cwd"
description: "Resolution contract for _git_toplevel() in setup_ticket_worktree.py. Measures main's anchor-plus-search behaviour and PR #866's cwd-first ordering against the dev, consumer and test-harness layouts with real git repositories; shows that both the AC and the test that guards it encode the wrong contract; and recommends anchoring on the install root, which the deployed copy's own path already encodes."
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
  - docs/analysis/2026-09-28-git-toplevel-resolution-contract-2-what-the-two-implementations-actually-do.md
  - docs/analysis/2026-09-28-git-toplevel-resolution-contract-3-candidates.md
  - docs/analysis/2026-09-28-git-toplevel-resolution-contract-4-recommendation.md
---

# The worktree tool should resolve the repository from the install it is part of, not from its own directory and not from the caller's cwd

`_git_toplevel()` in `scripts/setup_ticket_worktree.py` and
`templates/scripts/setup_ticket_worktree.py` decides **which git repository** every
worktree this package creates is created in. It has been changed twice in six days, in
two different directions, by two different records — `ACD-2100a-2` on `main` and
`BO-4100d-4` on `feature/worktree-git-toplevel-anchor` (PR #866, unmerged) — and the two
subcommands that matter most now resolve by different strategies. This page establishes
what the contract should be, measures every candidate against the three layouts that
exist, and recommends one.

Everything asserted here about current behaviour was executed, not inferred. The probe
scripts are `/tmp/probe_layouts.py` and `/tmp/probe_installroot.py`; both build real git
repositories, copy the real script files into real deployed positions, and import them
from those positions so `__file__` is honest.

---

## 1. The contract

**`_git_toplevel()` must return the repository that the *install it belongs to* serves —
the project rooted at the install root — and it must derive that from the install's own
fixed on-disk shape, never from the process working directory.** In the DEV /
self-hosting layout the install root is the untracked workspace parent and the project it
serves is `leafcutter-ai/`, the one repository beneath it. In the CONSUMER layout the
install root is the adopter's project root and the project it serves is that same root —
the adopter's repository, *not* the vendored `leafcutter-ai/` clone inside it. In the TEST
harness the install root is the temporary repository the harness staged the script into,
and resolution must land there. The unifying principle is that the tool operates on
**the repository the install was built into**, and the deployed copy already knows that
repository's location because `build.py` put the copy at
`<install_root>/<output_root>/scripts/setup_ticket_worktree.py` — the path *is* the
provenance.

### The hard part, stated before it is answered

The resolver cannot tell which repository is leafcutter's. `git rev-parse
--show-toplevel` answers "is this directory inside *a* repository", never "is this
*the* repository". Every candidate below is an attempt to smuggle in the missing
identity from somewhere else: from the caller (cwd, an explicit flag), from the
filesystem (a sentinel file, a subdirectory search), or from the build (a provenance
marker). The reframing above is what makes the problem tractable: **the resolver does
not need to identify leafcutter's repository at all.** It needs to identify the
*install*, and in the consumer layout leafcutter's repository is deliberately the wrong
answer anyway.

### The AC's stated contract is wrong, and so is the test that guards it

`BO-4100d-4.yaml` states the criterion as "the workspace is created in **the repository
the tool belongs to**, not in whatever repository happens to contain the copy." Read
literally in a consumer install, "the repository the tool belongs to" is
`<consumer>/leafcutter-ai/` — the vendored package clone. Creating an adopter's feature
worktrees inside the vendored package clone is plainly wrong, and it is the opposite of
what `_resolve_installed_layout()`'s own docstring specifies for that layout
(`templates/scripts/setup_ticket_worktree.py:321-339`: consumer layout ⇒ `repo_root` and
`worktrees_base` are both the consumer project root).

The test written against that criterion inherits the error.
`unit_tests/build_orchestration/test_bo_4100d_4.py:221`,
`test_a_copy_deployed_inside_a_different_repository_does_not_resolve_that_repository`,
constructs an "adopter" repo containing the deployed copy and a second "tool" repo, sets
cwd to the second, and asserts the resolver returns the **cwd** repo and *not* the
adopter's. That is the consumer layout with the correct answer marked wrong. The
implementation and its test agree with each other and both disagree with the layout,
which is exactly how the regression below shipped green.

---

## 2. What the two implementations actually do

> See [2026-09-28-git-toplevel-resolution-contract-2-what-the-two-implementations-actually-do.md](2026-09-28-git-toplevel-resolution-contract-2-what-the-two-implementations-actually-do.md) for full details.

---

## 3. Candidates

> See [2026-09-28-git-toplevel-resolution-contract-3-candidates.md](2026-09-28-git-toplevel-resolution-contract-3-candidates.md) for full details.

---

## 4. Recommendation

> See [2026-09-28-git-toplevel-resolution-contract-4-recommendation.md](2026-09-28-git-toplevel-resolution-contract-4-recommendation.md) for full details.

---

## 5. Where `ACD-2100a-2` lands: **absorbed, and widened**

Not superseded, not kept alongside. Its search algorithm is correct and should survive
verbatim as step 3 of G; what should change is **where it starts** and **who calls it**.

- **Where it starts.** `_search_immediate_subdirectory_repos(Path.cwd())` becomes
  `_search_immediate_subdirectory_repos(install_root)`. That single substitution fixes
  the one measured case the current implementation refuses (dev layout, cwd inside a
  worktree — the ordinary agent cwd during a drive) and removes the fragility where an
  agent's `chdir` changes which repository the tool picks. Every property the AC's
  `it_requirements` insist on is preserved: bounded to immediate children, no upward
  walk, no symlink following, exactly-one-or-refuse, WARNING on stderr naming the
  selection, idempotent.
- **Who calls it.** The present state — `create-only` resolving by anchor-plus-search
  while `create-ac-worktree` and `create-fastlane-worktree` resolve by PR #866's ordered
  list and `setup-ticket` resolves from its ticket path — is not acceptable and is not
  merely untidy. `create-fastlane-worktree` is the subcommand of the originating
  incident: `fast-lane-ship.js:678` invokes
  `{{config.output_root}}/scripts/setup_ticket_worktree.py create-fastlane-worktree`,
  i.e. the deployed copy, by the one path `ACD-2100a-2` does not cover. **The fix on
  `main` does not fix the incident that motivated either record.** All four subcommands
  must call one resolver.

One `it_requirement` of `ACD-2100a-2` has to be amended rather than honoured: *"the
anchor-based resolution must remain the first choice … a change that makes the search
primary alters behaviour for every caller that works today."* Under G the anchor is still
first — it is just a *different* anchor (the install root rather than the script
directory), and for the in-repo copy the two are the same directory, so no caller that
works today changes. The requirement's intent survives; its literal wording does not.

`ACD-2100a-2-i` and the eight tests in `unit_tests/ac_driven_dev/test_acd_2100a_2.py` /
`test_acd_2100a_2_i.py` should be re-pointed at the install root rather than deleted.
They are the only existing coverage of the search's boundedness.

---

## 6. Files, ACs and tests a fix would touch

Nothing below was edited.

**Source (both copies — deliberately drifted; change the resolution behaviour only, never
resync wholesale, per ADR-001 and `BO-4100d-4`'s `it_requirements`):**

- `/home/henzeh/projects/leafcutter/worktrees/worktree-git-toplevel-anchor/templates/scripts/setup_ticket_worktree.py`
  — `_git_toplevel()` (:137), `_search_immediate_subdirectory_repos()` (:184),
  `_resolve_repository_with_search_fallback()` (:242),
  `_resolve_installed_layout()` (:298), and the four call sites:
  `cmd_setup_ticket` (:1786, already correct), `cmd_create_only` (:1843),
  `cmd_create_ac_worktree` (:1920), `cmd_create_fastlane_worktree` (:2020). The module
  docstring's "REPOSITORY RESOLUTION FALLBACK" block (:56-76) states the cwd-based
  contract and must be rewritten with it.
- `/home/henzeh/projects/leafcutter/worktrees/worktree-git-toplevel-anchor/scripts/setup_ticket_worktree.py`
  — `_git_toplevel()` (:139), `_resolve_installed_layout()` (:186), call sites at
  :1753, :1801, :1878, :1978. This copy has **neither** search helper today; it would
  gain the shared resolver.
- Constraint carried over from `BO-4100d-4`: the literal string `probe_failure` must not
  appear anywhere in the template file —
  `unit_tests/build_orchestration/test_fastlane_template_deploy_parity.py` asserts its
  absence by whole-file substring match.

**ACs:**

- `docs/acceptance-criteria/build-orchestration/BO-4100-sound-workspace-by-construction/BO-4100d-4.yaml`
  — criteria, `it_requirements` #1 and #3, and `test_spec` entry 2 all state the wrong
  contract (§1). Amend if #866 is reduced to the message improvement; its
  `work_status: done` is not currently supportable either way.
- `docs/acceptance-criteria/ac-driven-dev/ACD-2100-entry-point-unblocked/ACD-2100a-2.yaml`
  and `ACD-2100a-2-i.yaml` — amend the "anchor is first choice" requirement per §5;
  widen the criterion from "the setup step" to all four subcommands.
- **New AC** under `BO-4100d` for install-root anchoring, with the two cases neither
  existing record covers: consumer layout + foreign cwd, dev layout + cwd inside a
  worktree.

**Tests:**

- `unit_tests/build_orchestration/test_bo_4100d_4.py` — 5 tests.
  `test_a_copy_deployed_inside_a_different_repository_does_not_resolve_that_repository`
  (:221) asserts the inverted contract and must be rewritten;
  `test_a_copy_outside_the_repository_still_creates_the_workspace_in_the_tools_own_repository`
  (:171) needs its notion of "the tool's own repository" restated as the install's
  repository;
  `test_an_unresolvable_location_is_refused_with_the_path_it_tried` (:276),
  `test_the_in_repository_copy_keeps_working_unchanged` (:336) and
  `test_an_explicit_anchor_that_does_not_resolve_is_refused_not_silently_replaced` (:375)
  survive as written.
- `unit_tests/ac_driven_dev/test_acd_2100a_2.py`, `test_acd_2100a_2_i.py` — 8 tests,
  re-pointed from cwd to install root.
- `unit_tests/build_orchestration/test_bo2400f_13*.py` (5 files, 14 failing tests) and
  their harness `_bo2400f13_fixtures.py` — **no change needed under G**; the harness
  shape resolves correctly (§3 G, row 7). Worth adding `cwd=` to
  `run_create_fastlane_worktree` (:130-144) and `run_git`'s siblings anyway, as defence
  in depth: a test that can reach the live repository when the resolver misbehaves is a
  test that can damage it, and it did.
- `unit_tests/build_orchestration/test_fastlane_template_deploy_parity.py` — not changed,
  but constrains the wording of anything added to the template.

**Also implicated, not necessarily changed:** `templates/workflows-js/fast-lane-ship.js`
(:678), `templates/workflows-js/plan-feature.js` (:2490),
`templates/workflows-js/quick-fix.js` (:307), `templates/agents/worktree-agent.md`
(:98-109) — the four production call sites. Under G none of them needs to compute or pass
a repository, which is the point; under C every one of them would.

---

## 7. If the evidence still underdetermines it

It does not, on the mechanism — every claim above is a measurement. The one genuinely
open question is the §4 counterargument, and a single fact settles it:

> **Does any real or intended consumer install set `output_root` to something other than
> `.leafcutter`?**

If no, G's path convention is a safe constant and the recommendation stands unmodified.
If yes, G's step 1 must not test a hard-coded name, and the choice is between deriving
the name from a config file the deployed script can find at a fixed location (which is
the same coupling one level removed) and falling back to D's explicit deploy-time marker.
Nothing else in this analysis changes either way.
