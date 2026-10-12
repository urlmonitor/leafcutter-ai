---
title: "check-mermaid-parent-link: the installed hook checks the repository's docs, not its own folder"
status: todo
components:
  - commit_guardian
  - documentation_system
created: 2026-10-07
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
change_target:
  - code
  - docs
risk_surface: internal
roadmap_phase: phase_1
advances_current_outcome: true
tags:
  - pre-commit
  - architecture-docs
  - mermaid
  - green-means-checked
last_updated: 2026-10-07
files_touched:
  - templates/scripts/commit_guardian/check_mermaid_parent_link.py
  - docs/architecture/components/supervisor-spawn-topology.md
  - unit_tests/commit_guardian/test_check_mermaid_parent_link_root.py  # new
agents:
  architecture-diagram-author: needed
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  llm-expert: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  status-checker: not_needed
---

# check-mermaid-parent-link: the installed hook checks the repository's docs, not its own folder

## Actor / Goal
In order that the architecture-doc parent links stay two-way, we need the installed
check-mermaid-parent-link hook to find the repository's real root and read the real docs. Then a
missing `children:` entry is refused at commit, instead of every commit passing unchecked.

## Context
- **Found 2026-10-07** by the architecture-diagram-author on EPIC-BuildToolingRunsThrough ticket 04.
  The installed `.leafcutter/` copy of the hook treats `.leafcutter/` as the repository root, finds no
  docs, and always passes. The `scripts/` copy reports ARCH-BIDIRECTIONAL correctly.
- **Cause.** `templates/scripts/commit_guardian/check_mermaid_parent_link.py:49` sets
  `REPO_ROOT = Path(__file__).resolve().parents[2]`. Two folders above the hook is:
  - from `scripts/commit_guardian/`, the repository root;
  - from the installed `.leafcutter/scripts/commit_guardian/`, which pre-commit runs
    (`.pre-commit-config.yaml:167-173`), `.leafcutter`;
  - from the source `templates/scripts/commit_guardian/`, `templates`.
  Every check reads `REPO_ROOT / <path>` (:228, :252, :283, :312, :342, :355). The architecture-doc
  check returns no violation when the file is not there (`if not abs_path.exists(): return []`,
  :228-230), so a wrong root reads as "all clear".
- **Measured 2026-10-07 at 6b7f05d1c.** `_check_arch_doc` run over the 82 non-ADR docs under
  `docs/architecture/`:
  - the installed copy: `REPO_ROOT` = `.leafcutter`, 0 violations;
  - the `scripts/` copy: 26 violations, of which 13 are ARCH-PARENT-MISSING, 8 ARCH-PARENT-NOTFOUND,
    3 ARCH-BIDIRECTIONAL and 2 ARCH-LEVEL-ORDER.
  - The Python-docstring check finds 6 more over tracked `.py` files outside `unit_tests/`. The ADR
    check finds none.
- **The concrete case.** `docs/architecture/components/build-epic-workflow-dispatch.md:10` names
  `docs/architecture/components/supervisor-spawn-topology.md` as its parent. That parent has no
  `children:` field at all (its frontmatter is :1-9).
  - `build-ticket-workflow-dispatch.md` names the same parent and has the same violation.
  - `supervisor-spawn-topology.md` itself has a mermaid block but no `parent:` or `root: true`. The
    working hook reports ARCH-PARENT-MISSING for it as soon as it is staged. So fixing the child link
    also means giving the parent a `parent:` (or `root: true`).
- **The shared resolver.** `_resolve_root.find_project_root()`
  (`templates/scripts/commit_guardian/_resolve_root.py:82`) prefers `git rev-parse --show-toplevel`
  and falls back to an ancestor walk. 41 hooks in that folder use it, e.g. `check_doc_links.py:38-40`.
- **Related AC.** GE-120b-2 ("Checks obtain their prerequisites through one shared resolution path",
  `todo`) lists `check_mermaid_parent_link.py` among the 19 files that still carry a private
  `parents[]` walk. This ticket does that migration for this one file.
- **Same pattern elsewhere (out of scope; GE-120b-2's work).** `check_adr_cross_reference.py:64`,
  `check_structural_change.py:83` and `check_components_integrity.py:127` also derive the root from
  `parents[2]`. Whether they fail the same way was not checked.
- **Effect of turning it on.** The hook checks staged files only. Once it works, any commit that
  stages one of the 26 docs, or one of the 6 `.py` files, is refused until that file is fixed.
  - Ticket 04's staged change edits `build-epic-workflow-dispatch.md`, so commit ticket 04 before
    this lands.
  - The 8 ARCH-PARENT-NOTFOUND docs write `parent: agent_delivery_workflows.md`, a bare name, while
    the hook resolves parents from the repository root. That is a convention question, not a typo.
- **Size.** The hook measures 300 of 400 lines (check-file-size, 2026-10-07).

## Open Question (for the user)
Fix the other 23 doc violations and the 6 `.py` ones in this ticket, in a follow-up ticket, or let
each surface when its file is next staged? The implementer lists them in Comments (AC-5) and asks.

## Acceptance Criteria
- [ ] AC-1: The hook gets the repository root from `_resolve_root.find_project_root()` and keeps no private `parents[]` walk. It finds the same root from the source, `scripts/` and installed `.leafcutter/` layouts.
- [ ] AC-2: Run from an installed `.leafcutter/scripts/commit_guardian/` copy, in a repository where a staged child doc names a parent whose `children:` does not list it, the hook exits 1 and reports ARCH-BIDIRECTIONAL naming both files.
- [ ] AC-3: A staged file the hook cannot find under the resolved root is reported as not checked, naming the root it used, and the hook exits non-zero. It never passes silently.
- [ ] AC-4: `supervisor-spawn-topology.md` lists `build-epic-workflow-dispatch.md` and `build-ticket-workflow-dispatch.md` in `children:`, and declares a `parent:` or `root: true`. A commit that stages those three docs passes the working hook.
- [ ] AC-5: Every other violation the working hook reports over the repository is listed in this ticket's Comments, with the user's decision on when it is fixed.
- [ ] AC-6: Apart from AC-3, the four checks and their message texts are unchanged.

## Test Requirements

```yaml
tests:
  - name: test_installed_copy_reports_a_missing_child_link
    location: unit_tests/commit_guardian/test_check_mermaid_parent_link_root.py
    type: integration
    covers: [AC-1, AC-2]
    description: |
      Temporary git repository with docs/architecture/components/parent.md (no children:) and
      child.md (a mermaid block and parent: docs/architecture/components/parent.md). Copy the
      hook and _resolve_root.py into <repo>/.leafcutter/scripts/commit_guardian/, stage child.md,
      and run the copy as pre-commit does, from the repository root. Exit 1, and ARCH-BIDIRECTIONAL
      names both files. Red today: exit 0.
  - name: test_staged_doc_missing_under_the_root_is_not_passed
    location: unit_tests/commit_guardian/test_check_mermaid_parent_link_root.py
    type: integration
    covers: [AC-3]
    description: |
      Make the root resolve to a folder that lacks the staged doc (e.g. patch find_project_root to
      an empty folder). The hook exits non-zero and says it could not check the file, naming the
      root. Red today: exit 0.
  - name: test_supervisor_topology_family_passes
    location: unit_tests/commit_guardian/test_check_mermaid_parent_link_root.py
    type: integration
    covers: [AC-4]
    description: |
      Run the hook's architecture-doc check, resolved against the real repository, on
      supervisor-spawn-topology.md, build-epic-workflow-dispatch.md and
      build-ticket-workflow-dispatch.md. No violations. Red until the docs are fixed.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_installed_copy_reports_a_missing_child_link | | |
| AC-2 | test_installed_copy_reports_a_missing_child_link | | |
| AC-3 | test_staged_doc_missing_under_the_root_is_not_passed | | |
| AC-4 | test_supervisor_topology_family_passes | | |
| AC-5 | (Comments inventory) | | |
| AC-6 | (review) | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

### architecture-diagram-author
- [ ] `supervisor-spawn-topology.md`: add `children:` with both dispatch docs, and a `parent:` (or
  `root: true`) that fits the doc tree. Keep the level order valid.

### test-writer
- [ ] Write `unit_tests/commit_guardian/test_check_mermaid_parent_link_root.py`.

### python-coder
- [ ] `check_mermaid_parent_link.py`: replace `REPO_ROOT` (49) with `find_project_root()`, and report
  a staged file missing under the root (AC-3). Add a DECISION HISTORY entry naming GE-120b-2.
- [ ] Run `python scripts/build.py` so `.leafcutter/` gets the new copy. Stage every tracked output it
  changes.
- [ ] Run the working hook over the whole repository, list the remaining violations in Comments, and
  ask the user the open question (AC-5).

### test-runner / pr-reviewer / commit
- [ ] Run the new file and `unit_tests/commit_guardian/test_resolve_root_git_preferred.py`.

## Risk & Safety
- Touches money? No.
- Touches data? No. Commits that stage a doc with a broken parent link start being refused. That is
  the hook doing its job, but it reaches docs that have passed unchecked until now.
- Reversibility: revert the commit.

## Out of Scope
- The other hooks with a `parents[2]` root (GE-120b-2).
- The parent-path convention behind the 8 ARCH-PARENT-NOTFOUND docs, unless the user folds it into
  the open question.
