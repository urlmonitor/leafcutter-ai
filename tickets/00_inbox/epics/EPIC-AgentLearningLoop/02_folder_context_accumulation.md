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
  architect-review: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  test-writer: needed
  python-coder: needed
  llm-expert: not_needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
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

- [ ] architect-review
- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### architect-review

- [ ] Read existing `PROJECT_CONTEXT.md` files to understand the current
  format and naming convention.
- [ ] Confirm the append-only, reverse-chronological format is compatible
  with the auto-loading behavior described in Channel ③ of the
  knowledge plane.
- [ ] Decide whether the summary section (AC-3) should be auto-generated
  or manually maintained.

### test-writer

- [ ] Write `tests/knowledge/test_context_accumulation.py`:
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

- [ ] Implement `scripts/knowledge/context_file_maintenance.py`:
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
