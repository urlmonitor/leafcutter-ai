---
title: "Folder context accumulation — component READMEs and PROJECT_CONTEXT growth"
status: todo
components:
  - infrastructure
created: 2026-06-05
depends_on:
  - tickets/00_inbox/epics/EPIC-AgentLearningLoop/01_harvester_agent_and_adr.md
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/knowledge/init_component_readme.py
  - scripts/knowledge/context_file_maintenance.py
  - tests/knowledge/test_context_accumulation.py
agents:
  architect-review: signed_off
  adr-author: not_needed
  architecture-diagram-author: not_needed
  test-writer: signed_off
  python-coder: signed_off
  llm-expert: not_needed
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: needed
  pull-request: needed
source_acs:
  - INF-400d-1
  - INF-400d-2
  - INF-400d-3
---

# 02: Folder context accumulation — component READMEs and PROJECT_CONTEXT growth

## Actor / Goal

As the leafcutter-ai system, I want component AC directories to accumulate
README.md files with domain conventions, and skill-scoped PROJECT_CONTEXT.md
files to grow with each run — so that future agents working in those domains
start with relevant context.

## Context

The harvester (ticket 01) routes learnings to destination files. This ticket
ensures those destination files exist, accumulate entries correctly, and
remain readable as they grow over many runs.

Two file types:

1. **Component README.md**: `docs/acceptance-criteria/{component}/README.md` —
   accumulates domain conventions, naming patterns, and standing rules
   observed by agents working in that component.

2. **Skill PROJECT_CONTEXT.md**: `.claude/skills/{name}/PROJECT_CONTEXT.md` —
   accumulates project-specific learnings relevant to that skill.

## Acceptance Criteria

```gherkin
# AC-1: Component AC directory has accumulating README.md (INF-400d-1)

Given the harvester routes a learning with entry_kind "per-folder-readme"
  and destination "docs/acceptance-criteria/infrastructure/README.md",
When the destination file does not yet exist,
Then the harvester creates it with a standard header:
  "# infrastructure — domain conventions" and a dated, agent-attributed entry,
And when a second learning is routed to the same file,
Then the new entry is appended below existing entries (not replacing them),
And each entry includes the date and the name of the agent that discovered it.

# AC-2: Skill PROJECT_CONTEXT.md grows with each run (INF-400d-2)

Given a skill at .claude/skills/signoff/ has an existing PROJECT_CONTEXT.md
  with 3 accumulated entries,
When the harvester routes a new learning to that file,
Then the new entry is appended as a new section with date and agent attribution,
And the existing 3 entries are preserved unchanged,
And the file follows the naming convention PROJECT_CONTEXT.md (all uppercase,
  underscore separator).

# AC-3: Context files remain readable after many entries (INF-400d-3)

Given a component README.md has accumulated 20 entries over multiple runs,
When a human or agent reads the file,
Then entries are organized with clear date headings,
And the most recent entries appear at the top (reverse chronological),
And no individual entry exceeds 5 lines,
And the file includes a brief summary section at the top that is updated
  when the file grows past 15 entries.
```

## Sign-offs

- [x] architect-review — 2026-06-05 10:00
- [x] test-writer — 2026-06-05 10:15
- [x] python-coder — 2026-06-05 10:30
- [x] test-runner — 2026-06-05 10:45
- [x] pr-reviewer — 2026-06-05 11:00
- [ ] commit
- [ ] pull-request

## Comments

### 2026-06-05 10:00 — architect-review (status: ok)
feedback-id: fb_2026-06-05_253750c4
completion_manifest:
  blast_radius_assessed: true
  impact_classified: true
  architectural_note_written: true
Impact classification: SMALL. Three files in scope — `scripts/knowledge/init_component_readme.py`, `scripts/knowledge/context_file_maintenance.py`, and `tests/knowledge/test_context_accumulation.py`. All within the `scripts/knowledge/` + `tests/knowledge/` scope; no Alembic migration, no public API surface, no hypertable change, no ADR contract change. Single component (infrastructure/knowledge scripts). Requires no ADR (ticket already has `requires_adr: false`). Design decision on AC-3: summary section should be **auto-generated** by `context_file_maintenance.py` using a count threshold (>15 entries) and regenerated on each append call — this keeps the file self-maintaining without manual intervention and is consistent with the append-only principle. The reverse-chronological ordering (newest entry first) is compatible with Channel ③ auto-loading: agents reading the file will see the most recent learnings without scrolling past historical entries. Acceptance criteria are well-specified and implementation-ready. No acceptance adjustments required. `suggested_adr: null`. `suggested_diagrams: []`. Escalation: none.

## Escalation

Branch: none
Reason: 3 files in scripts/knowledge/ and tests/knowledge/; no always-large trigger fired; single infrastructure component.

### 2026-06-05 10:15 — test-writer (status: ok)
feedback-id: fb_2026-06-05_b56fe3e8
completion_manifest:
  test_stubs_created: true
  all_tests_red: true
  red_baseline_captured: true
  ac_ids_covered: [INF-400d-1, INF-400d-2, INF-400d-3]
red_baseline:
  - test_name: TestReadmeCreatedWhenAbsent::test_readme_created_when_absent
    file: tests/knowledge/test_context_accumulation.py
    error: "_ModuleNotImplementedError: context_file_maintenance not yet implemented: [Errno 2] No such file or directory: '...scripts/knowledge/context_file_maintenance.py'"
  - test_name: TestReadmeCreatedWhenAbsent::test_readme_appends_not_overwrites
    file: tests/knowledge/test_context_accumulation.py
    error: "_ModuleNotImplementedError: context_file_maintenance not yet implemented: [Errno 2] No such file or directory: '...scripts/knowledge/context_file_maintenance.py'"
  - test_name: TestProjectContextPreservesExisting::test_project_context_preserves_existing
    file: tests/knowledge/test_context_accumulation.py
    error: "_ModuleNotImplementedError: context_file_maintenance not yet implemented: [Errno 2] No such file or directory: '...scripts/knowledge/context_file_maintenance.py'"
  - test_name: TestProjectContextPreservesExisting::test_project_context_filename_convention
    file: tests/knowledge/test_context_accumulation.py
    error: "_ModuleNotImplementedError: context_file_maintenance not yet implemented: [Errno 2] No such file or directory: '...scripts/knowledge/context_file_maintenance.py'"
  - test_name: TestReverseChronologicalOrder::test_reverse_chronological_order
    file: tests/knowledge/test_context_accumulation.py
    error: "_ModuleNotImplementedError: context_file_maintenance not yet implemented: [Errno 2] No such file or directory: '...scripts/knowledge/context_file_maintenance.py'"
  - test_name: TestEntryAttribution::test_entry_attribution
    file: tests/knowledge/test_context_accumulation.py
    error: "_ModuleNotImplementedError: context_file_maintenance not yet implemented: [Errno 2] No such file or directory: '...scripts/knowledge/context_file_maintenance.py'"
  - test_name: TestSummaryGeneration::test_summary_generated_after_threshold
    file: tests/knowledge/test_context_accumulation.py
    error: "_ModuleNotImplementedError: context_file_maintenance not yet implemented: [Errno 2] No such file or directory: '...scripts/knowledge/context_file_maintenance.py'"
7 failing test stubs written covering AC-1 (INF-400d-1), AC-2 (INF-400d-2), and AC-3 (INF-400d-3). All 7 tests red at exit code 1. Test file: tests/knowledge/test_context_accumulation.py. Ruff E722/BLE001/TRY: clean. Coder success target: implement create_readme(), append_entry(), generate_summary(), and CONTEXT_FILENAME in scripts/knowledge/context_file_maintenance.py.

### 2026-06-05 10:30 — python-coder (status: ok)
feedback-id: fb_2026-06-05_ffe41752
completion_manifest:
  files_created: true
  tests_green: true
  ruff_clean: true
Implemented scripts/knowledge/context_file_maintenance.py with create_readme(), append_entry(), generate_summary(), CONTEXT_FILENAME, and private helpers for reverse-chronological insertion and summary block management. Also implemented scripts/knowledge/init_component_readme.py as a CLI entry point. All 7 tests now pass (7/7 green). Ruff E722/BLE001/TRY clean on both files.

### 2026-06-05 10:45 — test-runner (status: ok)
feedback-id: fb_2026-06-05_aebc0d63
completion_manifest:
  tests_suite_run: true
  all_tests_green: true
  no_regressions: true
14/14 tests green in tests/knowledge/ (7 new context-accumulation tests + 7 pre-existing harvest-learnings tests). All AC coverage tests pass. No regressions introduced.

### 2026-06-05 11:00 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-05_ab09c9bd
completion_manifest:
  acs_covered: true
  error_handling_compliant: true
  append_only_verified: true
  ruff_clean: true
  tests_green: true
Code review passed. AC-1 (create_readme with standard header, idempotent append), AC-2 (existing entries preserved, PROJECT_CONTEXT.md naming convention), and AC-3 (reverse-chronological, auto-summary >15 entries) are all satisfied. All I/O is wrapped with try/except OSError + log+raise per project policy. No bare excepts, no blind exception catches. Ruff E722/BLE001/TRY clean on all 3 new/modified files. 7/7 test cases green. Implementation is correct and complete.

## Implementation Tasks

### architect-review

- [x] Read existing `PROJECT_CONTEXT.md` files to understand the current
  format and naming convention.
- [x] Confirm the append-only, reverse-chronological format is compatible
  with the auto-loading behavior described in Channel ③ of the
  knowledge plane.
- [x] Decide whether the summary section (AC-3) should be auto-generated
  or manually maintained.

### test-writer

- [x] Write `tests/knowledge/test_context_accumulation.py`:
  - `test_readme_created_when_absent`: route to non-existent README; assert
    created with header + entry.
  - `test_readme_appends_not_overwrites`: route two learnings; assert both
    present.
  - `test_project_context_preserves_existing`: fixture with 3 entries; route
    new one; assert all 4 present.
  - `test_reverse_chronological_order`: route 3 entries with different dates;
    assert newest first.
  - `test_entry_attribution`: route a learning from "business-analyst-v3";
    assert agent name appears in entry.

### python-coder

- [x] Implement `scripts/knowledge/context_file_maintenance.py`:
  - Functions for: create_readme, append_entry, generate_summary.
  - Entry format: date heading, agent name, learning text (max 5 lines).
  - Reverse chronological ordering.
  - Summary regeneration when entry count > 15.
  - Called by the harvester during its write phase.

## Risk & Safety

- Touches money? No.
- Touches data? Creates and appends to README.md and PROJECT_CONTEXT.md
  files. Append-only — existing content is never modified or deleted.
- Reversibility? New files can be deleted. Appended entries can be removed
  via git revert.
