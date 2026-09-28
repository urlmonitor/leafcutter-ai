---
title: "Startup halts get named causes: repo-anchored path resolution and split permission failures for plan-feature (ACD-2100, 13 of 25 tickets)"
date: "2026-09-07"
time: "12:55"
type: manual
components: 
  - ac_driven_dev
  - worktree_manager
  - build_pipeline
  - commit_guardian
summary: "Made the /plan-feature command work reliably from any starting folder, and replaced its one confusing permission-denied startup error with distinct messages that name what actually went wrong."
description: "29 commits (27 non-merge plus a merge of an advanced origin/main resolving 18 conflicts) land 13 of 25 ACD-2100 tickets. Repo-anchored path resolution replaces cwd-relative and config-relative lookups for the worktree-setup script and repo root, covering a linked worktree, an untracked cwd, and a sibling directory with no ancestry (ACD-2100a-1, a-2, a-3, a-5). The startup permission check now reports an unreadable registry, an uninterpretable registry, a missing agent-entries collection, and a genuine denial as four distinct outcomes instead of one collapsed permission-denied verdict, addressing KI-ACD-009 (ACD-2100b-1, b-2, b-3, b-3-i). Two previously-silent upstream catches now log at WARNING without changing the existing fail-closed control flow (ACD-2100b-4). An install now announces when it replaces a locally-changed generated file (ACD-2100d-2, d-2-i). Three pause-store test assertions were corrected to match a real command shape rather than a stale adjacency check (ACD-2100a-4). ACD-2100b-5 was re-targeted to a skill pre-flight surface but has no implementation yet; 11 of the epic's 25 tickets remain todo. The full test suite passes in CI on this branch."
pr: 652
commits: 
  - f41c23146
  - d908e5bcc
  - 0570c9dc8
  - 65a80bce2
  - 46def2668
  - f64a6318f
  - f1c595659
  - fcadb4375
  - 484efdfe7
  - ccc88542d
  - 295bc47c5
  - 3a0f673d2
  - 779627ba6
  - 2d50ca47b
  - 57c1ef374
  - 81ef74ef4
  - a7c10c207
  - aa96c59cd
  - ddcb0a7c6
  - 9682d6adf
  - 25cd63693
  - ef4d7d5f4
  - f7f5a6607
  - baaded860
  - c74e44784
  - 14d0419c8
  - cdd8ea320
  - 4ebcaeee8
  - 2b06a1491
  - 02878cae1
breaking: false
---

## Entry

EPIC-StartingNewWorkTheProperWayAlways implements `ACD-2100`: the `/plan-feature` entry
point should work from any working directory, and its startup checks should say what
actually went wrong instead of collapsing every failure into one misleading verdict. This
entry covers PR #652, which lands 13 of the epic's 25 tickets; 11 remain `todo` and one
(`ACD-2100b-5`, see below) is not yet implemented.

**Repo-anchored path resolution (ACD-2100a-1, a-2, a-3, a-5).** The authoring-worktree
creation step previously trusted a `{{config.output_root}}`-relative or cwd-relative path
to locate `scripts/setup_ticket_worktree.py`, which under the self-hosting layout could
resolve to the wrong (deployed, out-of-repo) copy of the script. `plan-feature.js` gained
`buildRepoAnchoredResolutionCommand()` / `resolveRepoAnchoredScriptPath()`, which resolve
the script to an absolute, repository-anchored path via `git rev-parse --show-toplevel`
with a bounded fallback, and fail closed under their own label on resolution failure
rather than silently falling back to the wrong copy. The `setup_ticket_worktree.py`
`create-only` step gained a parallel `_resolve_repository_with_search_fallback()` for the
case where the script itself is copied outside any git repository, plus an explicit
`--repo-root` override flag. A third resolution strategy added later (a-5) probes cwd's
own sibling directories when cwd has no git ancestry and no children of its own, covering
a working directory that sits alongside the project under a shared workspace parent
without turning startup into an unbounded filesystem search.

**Split permission-check failures (ACD-2100b-1, b-2, b-3, b-3-i; addresses
`KI-ACD-009`).** The startup permission check previously reported every non-`ok` outcome
as the same generic permission-denied verdict. It now distinguishes four causes: an
unreadable registry file, a registry that can be read but not interpreted, a missing
agent-entries collection within an otherwise-readable registry, and a genuine permission
denial — each reported under its own label with its own remedy, so a broken registry read
is no longer mistaken for a real access-control decision.

**Logged upstream catches (ACD-2100b-4).** Verified that all four startup-check halt
paths above already stop before any authoring dispatch or worktree/branch creation. Added
WARNING-level logging to the two catch blocks upstream of those branches (registry-read
dispatch failure and registry-interpretation failure) to satisfy this repo's
error-handling policy, without changing the existing fail-closed fallback values or
control flow.

**Generated-file replacement announcement (ACD-2100d-2, d-2-i).** An install now announces
when it is about to overwrite a generated file that has local, uncommitted changes,
instead of silently replacing it. Implemented in `scripts/build.py` and
`scripts/build_phases.py`; covered by `unit_tests/build_guards/test_acd_2100d_2.py` and
`test_acd_2100d_2_i.py`, including the boundary case that an unchanged generated file
produces no announcement.

**Corrected pause-store test assertions (ACD-2100a-4).** `buildPauseStoreCommand()`
correctly emits `--store-dir "$STORE_DIR"` between the script path and the subcommand
(argparse requires the top-level flag before the subcommand), which meant three
anti-phantom assertions in `unit_tests/workflows/test_bo_2300_pause_resume.py` were
matching on now-broken substring adjacency rather than the real invocation shape. All
three assertions were corrected to require both the script name and the parameterized
subcommand token, non-adjacent, while still failing against four adversarial strings that
lack a real invocation.

**Not shipped by this PR.** `ACD-2100b-5`'s acceptance criterion was re-targeted
(`0570c9dc8`) from a check inside the `plan-feature` workflow body to a new pre-flight
script invoked by the `plan-feature` skill, because the E2 workflow engine (ADR-030)
contextifies the workflow body with no filesystem primitive and the original record
required a local read of `config/agent_registry.json`. Only the AC record was amended;
`scripts/worktree/check_workspace_setup_permission.py` and the corresponding
`templates/skills/plan-feature/SKILL.md` change do not exist yet. Do not read this ticket
as done. The remaining 11 tickets in the epic (the `c` series and most of `d`/`e`) are
still `todo`.

**Merge.** The branch also merges an advanced `origin/main` into itself
(`f41c23146`, first-parent `d908e5bcc`), resolving 18 conflicts; that merge carries no
additional ACD-2100 behavior beyond what is described above.
