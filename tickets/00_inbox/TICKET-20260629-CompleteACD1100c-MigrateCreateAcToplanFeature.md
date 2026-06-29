---
title: "Complete ACD-1100c: migrate create-ac skill spec into plan-feature and remove create-ac"
status: todo
components:
  - skills_system
  - skill_registry
  - llm_authoring
created: 2026-06-29
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
tags:
  - v2-migration
  - phantom-done
  - skill-content-surgery
files_touched:
  - templates/skills/plan-feature/SKILL.md
  - templates/skills/build-single-ticket/SKILL.md
  - config/skill_registry.json
  - templates/skills/create-ac/SKILL.md
  - templates/skills/create-ac/
agents:
  architect-review: not_needed
  llm-expert: needed
  test-writer: not_needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
ac_coverage: 0/6
origin_agent: BrainCandy
---

# Complete ACD-1100c: migrate create-ac skill spec into plan-feature and remove create-ac

## Actor / Goal

In order to eliminate the phantom-done state of ACD-1100c-1 and establish a single
canonical planning-skill surface, we need to migrate the load-bearing specification
content from `templates/skills/create-ac/SKILL.md` into `templates/skills/plan-feature/SKILL.md`,
repoint all cross-references, scrub dead `/create-ac` invocation co-mentions, and
delete the now-empty `templates/skills/create-ac/` directory and its registry entry,
so that the skill registry invariant holds and no dangling references remain.

## Context

AC ACD-1100c-1 ("rename the create-ac skill to plan-feature") was marked done on
origin/main but is actually PHANTOM-DONE. A new thin `templates/skills/plan-feature/SKILL.md`
(~120 lines) was created as an entry-point shell, but the original
`templates/skills/create-ac/SKILL.md` (~955 lines on origin/main) was NEVER migrated.
It still holds ~909 lines of unique, load-bearing specification that plan-feature
does not contain. Both skill directories still coexist on origin/main.

The prior attempt (EPIC-Theacdrivendevelopmentpipelineistheonly, PR #131) was closed
without merge because it would have regressed main. This ticket finishes the job correctly.

### Key sections that must be migrated (as found on origin/main)

The implementing agent (llm-expert) MUST diff `create-ac/SKILL.md` against
`plan-feature/SKILL.md` at build time to identify unique load-bearing content.
Sections of particular importance:

- **§MP** — manual-worktree-protection spec (cross-referenced by build-single-ticket)
- **§1–§3** — the AC-authoring invariant (cross-referenced by build-single-ticket)
- **Partial-Run Recovery pre-flight** — procedure for resuming interrupted runs

### Working-tree note (CRITICAL for the implementing agent)

The local checkout diverges from origin/main: the local `create-ac/SKILL.md` may be
shorter (~295 lines) than the origin/main version (~955 lines), and the local
`build-single-ticket/SKILL.md` may not yet show the create-ac §MP/§1–§3 cross-references.
**The build MUST run from a fresh worktree off origin/main** where the full-length file
and the xrefs exist. Verify before editing.

### Related tickets

- `TICKET-20260610-ACD-1100c-1.md` — the phantom-done ticket (marked done, not actually done)
- `TICKET-20260610-ACD-1100c-2.md` — the companion ticket for `/create-ac` co-mention cleanup (may overlap; check before driving)
- `TICKET-20260622-CreateAcSkillRegistryOrphan.md` — confirmed the registry entry exists
  on origin/main after PR #146 added it; this ticket must REMOVE that entry

## Out of Scope (CRITICAL — do not touch)

- `create-ac-worktree` subcommand in `scripts/setup_ticket_worktree.py` and
  `templates/scripts/setup_ticket_worktree.py` — this is a separate, still-valid
  worktree-type identifier, NOT the `/create-ac` command surface. Do NOT modify.
- `scripts/proposals/agent_self_description_*.yaml` — stale set, separate hygiene ticket.
- `config/agent_registry.json` — not in scope.
- `scripts/build.py` — not in scope.
- Historical migration-note comments (e.g. "Renamed from create-ac.js") — allowed to remain.
- `templates/workflows-js/plan-feature.js` co-mentions of `/create-ac` — out of scope
  for this ticket; flagged as a latent break to be tracked separately if confirmed.

## Acceptance Criteria

```gherkin
Scenario: build-single-ticket cross-references repointed
  Given templates/skills/build-single-ticket/SKILL.md previously referenced
    create-ac/SKILL.md §MP and §1-§3,
  When this ticket is complete,
  Then those references point at the new canonical plan-feature location
  AND that location actually contains the §MP and §1-§3 spec content.

Scenario: create-ac directory removed and registry entry eliminated
  Given the create-ac skill directory and skill_registry.json entry exist,
  When this ticket is complete,
  Then templates/skills/create-ac/ does not exist
  AND config/skill_registry.json has no entry with id "create-ac"
  AND the registry file parses as valid JSON (python -m json.tool exits 0).

Scenario: no specification content lost
  Given the §MP manual-worktree-protection spec and §1-§3 AC-authoring invariant
    and Partial-Run Recovery pre-flight were authored in create-ac/SKILL.md,
  When this ticket is complete,
  Then all three sections are present in the canonical plan-feature location
  with their normative content preserved (no section dropped, no invariant weakened).

Scenario: create-ac-worktree subcommand unchanged
  Given the create-ac-worktree subcommand exists in setup scripts,
  When this ticket is complete,
  Then it is unchanged and still functional
  (git diff shows no edits to setup_ticket_worktree.py or templates/scripts/setup_ticket_worktree.py).

Scenario: no active command/skill file advertises /create-ac as an invocation surface
  Given no active command/skill file should present /create-ac as a command,
  When this ticket is complete,
  Then no file under templates/commands/ or templates/skills/ presents "/create-ac"
    as an invocation surface (historical migration notes excepted).

Scenario: registry bidirectional test passes
  Given tests/test_skill_registry.py::TestSkillRegistryBidirectional covers both
    orphaned directories and orphaned registry entries,
  When the test suite runs after this change,
  Then both test_no_orphaned_directories and test_no_orphaned_registry_entries pass
    (no net-new regressions vs baseline).
```

## Agent Contracts

### llm-expert

- [ ] AC-1: Given templates/skills/plan-feature/SKILL.md after the change, When its content is inspected, Then the §MP section, the §1-§3 AC-authoring invariant, and the Partial-Run Recovery procedure are all present in the canonical plan-feature surface with their normative content preserved (no section dropped, no invariant weakened).
- [ ] AC-2: Given templates/skills/build-single-ticket/SKILL.md after the change, When every cross-reference that previously pointed at create-ac §MP or §1-§3 is followed, Then each now resolves to the new canonical location inside templates/skills/plan-feature/SKILL.md, and no cross-reference in the file resolves to the create-ac skill.
- [ ] AC-3: Given the templates/skills and templates/commands trees after the change, When scanned for the token '/create-ac' presented as an active invocation surface, Then no active file presents it as an invocation (historical migration notes are excepted), AND the templates/skills/create-ac/ directory does not exist.

**Delivers to**: python-coder
**Depends on**: none

### python-coder

- [ ] AC-4: Given config/skill_registry.json after the change, When parsed as JSON, Then the file parses successfully (valid JSON) AND the 'skills' array contains no object whose id equals 'create-ac'.
- [ ] AC-5: Given the repository after the registry edit, When the registry bidirectional test is run, Then it completes without error and no remaining surface references the removed create-ac skill_registry id.
- [ ] AC-6: Given setup_ticket_worktree.py and templates/scripts/setup_ticket_worktree.py after the change, When the 'create-ac-worktree' subcommand definition is diffed against the prior revision, Then it is byte-for-byte unchanged; AND config/agent_registry.json and scripts/build.py are unmodified.

**Delivers to**: end user
**Depends on**: llm-expert

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | manual diff of §MP/§1-§3/PRR sections | templates/skills/plan-feature/SKILL.md | |
| AC-2 | grep for create-ac xrefs in build-single-ticket/SKILL.md | templates/skills/build-single-ticket/SKILL.md | |
| AC-3 | grep -r '/create-ac' templates/commands templates/skills | templates/skills/create-ac/ (deletion) | |
| AC-4 | python -m json.tool config/skill_registry.json | config/skill_registry.json | |
| AC-5 | pytest tests/test_skill_registry.py | config/skill_registry.json | |
| AC-6 | git diff -- scripts/setup_ticket_worktree.py templates/scripts/setup_ticket_worktree.py | none (negative AC) | |

## Sign-offs

- [ ] llm-expert
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

### 2026-06-29 — BrainCandy (status: ok)

Authored at depth 1, standard_ticket path. BA: complexity=standard. IT PO contracts
produced per-agent AC blocks (llm-expert: AC-1–AC-3, python-coder: AC-4–AC-6).
Working-tree divergence warning (local vs origin/main create-ac/SKILL.md length) surfaced
by BA and encoded in Context above. ACD-1100c-2 companion ticket may overlap on the
/create-ac co-mention cleanup step — check before driving both.

## Implementation Tasks

- [ ] Create a fresh worktree off origin/main and verify create-ac/SKILL.md is ~955 lines and contains §MP, §1-§3, and Partial-Run Recovery sections.
- [ ] Diff create-ac/SKILL.md against plan-feature/SKILL.md to identify all unique load-bearing content.
- [ ] Migrate §MP, §1-§3, and Partial-Run Recovery into templates/skills/plan-feature/SKILL.md (fold into skill body at the appropriate structural position).
- [ ] Update all cross-references in templates/skills/build-single-ticket/SKILL.md that pointed at create-ac §MP and §1-§3 to point at the new plan-feature canonical location.
- [ ] Scrub active templates/commands and templates/skills files of any `/create-ac` invocation-surface co-mentions (historical migration notes are exempt).
- [ ] Delete templates/skills/create-ac/ directory (entire directory).
- [ ] Remove the id: "create-ac" entry from config/skill_registry.json; run python -m json.tool to verify JSON validity.
- [ ] Run pytest tests/test_skill_registry.py tests/test_skill_registry_schema.py and confirm green (no orphaned-directory or orphaned-registry failures).
- [ ] Verify setup_ticket_worktree.py and templates/scripts/setup_ticket_worktree.py are untouched (git diff shows no edits to those files).

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? The spec content migration is reversible via git revert. The directory deletion is recoverable from git history. The registry edit is a single-entry removal; trivially revertible. No schema migrations involved.
- Referential integrity risk: if any file outside the declared scope references create-ac §MP or §1-§3, deleting the directory without repointing will leave a dangling reference. The implementing agent must grep the full template tree for create-ac references before deleting.
