---
title: "Recommendation — git-toplevel resolution contract"
description: "Recommends adopting install-root anchoring (Candidate G) for _git_toplevel(), reducing PR #866 to its error-message improvement, and authoring a new AC for the install-root change. Includes the strongest counterargument (the output_root convention is configurable) and why it is judged acceptable, plus the scope decision to keep this out of PR #866."
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

## 4. Recommendation

**Adopt G (install-root anchoring), with `ACD-2100a-2`'s bounded search absorbed as its
step 3, applied to all four subcommands, and fix `_resolve_installed_layout()` in the
same change. Do it in a new AC. Reduce PR #866 to the error-message improvement — or
close it.**

Concretely:

- `_git_toplevel(anchor)` keeps the explicit-anchor-is-authoritative rule from PR #866.
  That part is right and should survive. Remove the `Path.cwd()` candidate entirely.
- The no-anchor default becomes install-root anchoring, not the script directory and not
  cwd.
- Because the install root also *is* the worktrees base in both deployed layouts, the
  resolver should return the `(repo_root, worktrees_base)` pair rather than leaving
  `_resolve_installed_layout()` to re-derive it by probing a parent — which is the §2
  third defect. For the in-repo copy, `_resolve_installed_layout()`'s existing
  parent-probe remains correct and should be kept for that path only.

### The strongest argument against it, stated fairly

**G hard-codes a deployment convention into the tool that reads it, and that convention
is configurable.** `output_root` is a `skills_config.json` key (default `.leafcutter`,
`config/skills_config.default.json:9`), and an adopter may set it to something else. A
resolver that tests `parent.name == ".leafcutter"` is wrong for that adopter, and wrong
*silently* — it would treat `<install>/myoutput/scripts/` as an in-repo copy, take
`<install>/myoutput` as the install root, resolve the adopter's repo from it, and get
the right repository for the wrong reason in the consumer layout while getting the dev
layout wrong. This is a real coupling: `setup_ticket_worktree.py` is deployed **verbatim**
and so cannot have the configured value injected at build time, which is exactly the
trap recorded for config literals in deployed `.py` files.

Three things blunt it, none of them fully. The convention is already load-bearing
elsewhere in the same file — `_install_drift_hook`'s generated hook computes
`repo_root = Path(__file__).resolve().parent.parent.parent`
(`templates/scripts/setup_ticket_worktree.py:1699`), the identical three-levels-up
assumption, shipped and working. The rule can be written as "walk up from the script
directory to the first ancestor that is a git repository root **or** that contains a
`scripts/` sibling plus a recognisable install marker", which degrades to a search rather
than a wrong answer. And the failure is detectable: if the derived install root is not a
repository *and* the bounded search finds zero candidates, refuse and name both the
derived install root and the `output_root` assumption in the message, so the next person
sees the assumption rather than a 128.

I judge the coupling acceptable **because the alternative to reading the convention is
writing a marker (D), and the convention is the marker** — one that `build.py` already
maintains correctly and that has never drifted, versus a new artifact in the problem
space of an open high-severity issue. But this is the point on which the recommendation
could reasonably be overruled, and if it is, D is the option to fall back to, not A.

### Scope: this does not belong in PR #866

PR #866 as it stands should **not** merge. Its net effect, measured, is: dev layout still
broken (better message), consumer layout newly and silently broken from a non-consumer
cwd, 14 tests red, and seven stray worktrees in the live repository. The honest disposal
is:

- **Reduce #866 to the error-message improvement only** — keep the "names every candidate
  tried / states the copy appears to be deployed outside the repository it manages"
  message and the explicit-anchor-is-authoritative rule, drop the `Path.cwd()` candidate.
  That alone turns a bare `exit status 128` into a diagnosable refusal, is a genuine
  improvement, is layout-neutral, and returns all 14 tests to green because script-dir
  ordering is restored. `BO-4100d-4` then needs amending to match what it actually
  delivered, because its criteria and three of its five tests describe the resolution
  change, not the message.
- **Author a new AC for G**, under `BO-4100d` alongside `BO-4100d-4`. It is a different
  change with a different blast radius (four subcommands, two files, plus
  `_resolve_installed_layout()`), and it needs test coverage that PR #866 does not have:
  the consumer-layout-with-foreign-cwd case that PR #866 gets wrong, and the
  dev-layout-from-inside-a-worktree case that `ACD-2100a-2` gets wrong.
- Do **not** attempt G inside #866. Its AC, its changelog and its tests all assert the
  cwd contract; amending all three in place produces a record whose history says it fixed
  something it did not.

### Also worth filing

`KI-BP-20260922-0620` is cited as filed in `BO-4100d-4.yaml:110` and in the branch
changelog, but **no such entry exists** under `docs/known-issues/` — a repo-wide grep
finds only those two references. The incident is real and reproducible; the register
entry is missing.
