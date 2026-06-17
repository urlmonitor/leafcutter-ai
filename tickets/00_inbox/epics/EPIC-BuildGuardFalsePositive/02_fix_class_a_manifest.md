---
title: "Class A manifest fix: derive deployable-scripts manifest from build phases"
status: todo
components:
  - build_pipeline
created: 2026-06-17
depends_on:
  - 01_research_class_b_triage.md
priority: critical
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 02: Class A Manifest Fix — Derive Deployable-Scripts Manifest from Build Phases

## Goal

In order to stop the build guard from falsely flagging scripts that are already
deployed, we need `_get_source_deployable_scripts()` to derive its manifest from
the actual deploy phases rather than a hardcoded name list that cannot keep pace
with phase additions.

## Context

`_get_source_deployable_scripts()` (scripts/build.py ~line 393 in the EPIC worktree)
hardcodes three manifest sources:
1. `scripts/ac_store/*` — scanned dynamically (correct)
2. `scripts/feedback/` — only 3 named scripts (`submit_feedback.py`,
   `emit_hook_finding.py`, `list_tags.py`) — omits `aggregate.py` and
   `resolve_feedback.py` which `build_feedback` also deploys
3. Two standalone scripts — hardcoded names

This causes 10 Class A false positives (8 commit_guardian + 2 feedback). The fix is
structural: the manifest should be derived from what the deploy phases actually write,
not from a maintained parallel list.

Preferred implementation: scan the source directories that each deploy phase reads
from — e.g. `templates/scripts/commit_guardian/` for `build_commit_guardian`,
`scripts/feedback/` for `build_feedback`. This way adding a new phase or a new script
within an existing phase automatically updates the manifest.

Key files:
- `scripts/build.py` — `_get_source_deployable_scripts()` (edit target)
- `scripts/build_phases.py` — `build_commit_guardian()`, `build_feedback()` source
  directories to mirror
- `scripts/commit_guardian/` — all scripts deployed by `build_commit_guardian`
- `scripts/feedback/` — all scripts deployed by `build_feedback`

Depends on ticket 01 to confirm which commit_guardian and feedback scripts are
legitimately Class A (all should be, but the triage confirms this).

## Acceptance Criteria

```gherkin
Scenario: clean build exits 0 after manifest fix (AC BP-900-Fix-1)
  Given the unmodified leafcutter package with this ticket's changes applied
  When python scripts/build.py --target-dir <fresh-temp-dir> runs
  Then it exits 0
  And it writes a non-zero number of files to the target directory
  And it emits zero broken-reference JSONL lines to stderr
  origin_agent: BrainCandy

Scenario: manifest derived from deploy phases not hardcoded lists (AC BP-900-Fix-2)
  Given the updated _get_source_deployable_scripts() function
  When a new .py file is added to scripts/commit_guardian/ or scripts/feedback/
  Then _get_source_deployable_scripts() includes it automatically
  And no manual name-list edit is required
  origin_agent: BrainCandy

Scenario: commit_guardian scripts all included in manifest (AC-3)
  Given the updated manifest function
  When it runs against the current package root
  Then the returned set includes scripts/commit_guardian/check_adr_collision.py,
    scripts/commit_guardian/check_v2_ac_store_alignment.py,
    scripts/commit_guardian/known_failing_tests.py,
    scripts/commit_guardian/check_ac_schema.py,
    scripts/commit_guardian/check_doc_frontmatter.py,
    scripts/commit_guardian/check_ticket_signoff_parity.py,
    scripts/commit_guardian/check_documentation.py,
    scripts/commit_guardian/run_hook.py
  origin_agent: BrainCandy

Scenario: full feedback set included in manifest (AC-4)
  Given the updated manifest function
  When it runs against the current package root
  Then the returned set includes scripts/feedback/aggregate.py
  And it includes scripts/feedback/resolve_feedback.py
  And it includes the previously-covered three scripts
  origin_agent: BrainCandy
```

## Implementation Tasks

- [ ] Read `build_phases.py` to identify the source directories for `build_commit_guardian`
  and `build_feedback`
- [ ] Rewrite the hardcoded feedback name-list in `_get_source_deployable_scripts()` to
  scan the actual source directory (`scripts/feedback/`) dynamically, matching what
  `build_feedback` deploys
- [ ] Add a manifest entry block for commit_guardian scripts, scanning
  `templates/scripts/commit_guardian/` (the source `build_commit_guardian` reads from)
- [ ] Audit all other deploy phases in `_run_phases()` to check for any additional
  scripts they deploy that are not yet in the manifest; add those too
- [ ] Verify that a clean build now exits 0 with zero broken-ref JSONL lines

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Change is a function rewrite in scripts/build.py; trivially reversible.
- Risk: widening the manifest for scripts that are NOT actually deployed would mask
  Class B gaps. Verify each new manifest entry corresponds to a real deploy phase output.

## Comments

_(Append-only log — leave blank when authoring.)_
