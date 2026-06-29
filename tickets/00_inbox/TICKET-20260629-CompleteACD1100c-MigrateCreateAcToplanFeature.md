---
title: "Complete ACD-1100c: migrate create-ac skill spec into plan-feature and remove create-ac"
status: in_progress
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
  llm-expert: signed_off
  test-writer: not_needed
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
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

- [x] AC-1: Given templates/skills/plan-feature/SKILL.md after the change, When its content is inspected, Then the §MP section, the §1-§3 AC-authoring invariant, and the Partial-Run Recovery procedure are all present in the canonical plan-feature surface with their normative content preserved (no section dropped, no invariant weakened). <!-- signed: llm-expert -->
- [x] AC-2: Given templates/skills/build-single-ticket/SKILL.md after the change, When every cross-reference that previously pointed at create-ac §MP or §1-§3 is followed, Then each now resolves to the new canonical location inside templates/skills/plan-feature/SKILL.md, and no cross-reference in the file resolves to the create-ac skill. <!-- signed: llm-expert -->
- [x] AC-3: Given the templates/skills and templates/commands trees after the change, When scanned for the token '/create-ac' presented as an active invocation surface, Then no active file presents it as an invocation (historical migration notes are excepted), AND the templates/skills/create-ac/ directory does not exist. <!-- signed: llm-expert -->

**Delivers to**: python-coder
**Depends on**: none

### python-coder

- [x] AC-4: Given config/skill_registry.json after the change, When parsed as JSON, Then the file parses successfully (valid JSON) AND the 'skills' array contains no object whose id equals 'create-ac'. <!-- signed: python-coder -->
- [x] AC-5: Given the repository after the registry edit, When the registry bidirectional test is run, Then it completes without error and no remaining surface references the removed create-ac skill_registry id. <!-- signed: python-coder -->
- [x] AC-6: Given setup_ticket_worktree.py and templates/scripts/setup_ticket_worktree.py after the change, When the 'create-ac-worktree' subcommand definition is diffed against the prior revision, Then it is byte-for-byte unchanged; AND config/agent_registry.json and scripts/build.py are unmodified. <!-- signed: python-coder -->

**Delivers to**: end user
**Depends on**: llm-expert

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | manual diff of §MP/§1-§3/PRR sections | Migrated §PRR, §1–§3, §MP into plan-feature/SKILL.md preserving all normative content | ok — 2026-06-29 |
| AC-2 | grep for create-ac xrefs in build-single-ticket/SKILL.md | Repointed §MP xref and §1–§3 xref in build-single-ticket/SKILL.md to plan-feature | ok — 2026-06-29 |
| AC-3 | grep -r '/create-ac' templates/commands templates/skills | Removed active /create-ac invocation surface mentions; historical migration note in DECISION HISTORY exempted | ok — 2026-06-29 |
| AC-4 | python -m json.tool config/skill_registry.json | Removed id:"create-ac" entry from config/skill_registry.json; python3 -m json.tool exits 0 | ok — 2026-06-29 |
| AC-5 | pytest tests/test_skill_registry.py | Deleted templates/skills/create-ac/ via git rm; all 9 registry tests + 7 schema tests pass (16/16 green) | ok — 2026-06-29 |
| AC-6 | git diff -- scripts/setup_ticket_worktree.py templates/scripts/setup_ticket_worktree.py | git diff HEAD shows no changes to guard files; create-ac-worktree subcommand untouched | ok — 2026-06-29 |

## Sign-offs

- [x] llm-expert — 2026-06-29 11:00
- [x] python-coder — 2026-06-29 12:00
- [x] test-runner — 2026-06-29 13:00
- [x] pr-reviewer — 2026-06-29 14:00
- [x] commit — 2026-06-29 15:00
- [ ] pull-request

## Comments

### 2026-06-29 — BrainCandy (status: ok)

Authored at depth 1, standard_ticket path. BA: complexity=standard. IT PO contracts
produced per-agent AC blocks (llm-expert: AC-1–AC-3, python-coder: AC-4–AC-6).
Working-tree divergence warning (local vs origin/main create-ac/SKILL.md length) surfaced
by BA and encoded in Context above. ACD-1100c-2 companion ticket may overlap on the
/create-ac co-mention cleanup step — check before driving both.

### 2026-06-29 11:00 — llm-expert (status: ok)

feedback-id: (submit-failed)
completion_manifest:
  spec_content_migrated: true
  build_single_ticket_xrefs_repointed: true
  create_ac_comention_scrubbed: true

Migrated §PRR (Partial-Run Recovery Pre-flight), §1–§3 (Stage Pipeline / Commit-Before-Next-Stage Invariant), and §MP (Main-Branch Invocation) from templates/skills/create-ac/SKILL.md into templates/skills/plan-feature/SKILL.md. All three sections are present with their normative content intact. Updated templates/skills/build-single-ticket/SKILL.md: the §MP cross-reference now points to plan-feature/SKILL.md §MP, and the §1–§3 cross-reference now points to plan-feature/SKILL.md §1–§3. Grepped templates/commands/ and templates/skills/ for active /create-ac invocation surfaces and cleaned them in build-single-ticket/SKILL.md; one historical migration note in plan-feature/SKILL.md DECISION HISTORY block is exempt. Note: feedback submission failed (submit_feedback.py config not found in worktree at templates/config/feedback_categories.yaml).

### 2026-06-29 12:00 — python-coder (status: ok)

feedback-id: (submit-failed)
completion_manifest:
  skill_registry_entry_removed: true
  create_ac_directory_deleted: true
  registry_tests_green: true
  guard_files_untouched: true

Removed id:"create-ac" entry from config/skill_registry.json (9 lines). Deleted templates/skills/create-ac/ (955-line SKILL.md) via git rm. Verified JSON validity with python3 -m json.tool (exit 0). Ran tests/test_skill_registry.py (9/9 passed) and tests/test_skill_registry_schema.py (7/7 passed). Confirmed guard files scripts/setup_ticket_worktree.py, templates/scripts/setup_ticket_worktree.py, config/agent_registry.json, and scripts/build.py show zero diff vs HEAD.

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

### 2026-06-29 13:00 — test-runner (status: ok)

feedback-id: (submit-failed)
completion_manifest:
  skill_registry_tests_green: true
  no_orphaned_directory_failures: true
  no_orphaned_registry_failures: true

Ran tests/test_skill_registry.py (9/9 passed) and tests/test_skill_registry_schema.py (7/7 passed) independently.
Key passing tests: TestSkillRegistryBidirectional::test_no_orphaned_directories, TestSkillRegistryBidirectional::test_no_orphaned_entries,
TestSkillRegistryBidirectional::test_registry_entry_schema, TestSkillRegistrySchemaValidation::test_registry_validates_against_schema.
The 4 collection errors from the broader -k skill sweep are pre-existing path-dependency issues (check_feedback_id, check_mermaid_complexity,
known_failing_tests, transform_decision_history modules absent from sys.path when run without the installed package) — none introduced by this
ticket, none in the diff. Note: feedback submission failed (submit_feedback.py not present in scripts/feedback/).

### 2026-06-29 14:00 — pr-reviewer (status: ok)

feedback-id: (submit-failed)
completion_manifest:
  spec_sections_present: true
  xrefs_repointed: true
  no_active_create_ac_surface: true
  registry_clean: true
  guard_files_untouched: true

Review passed. Verified §PRR (lines 116–319), §1–§3 (lines 343–396), and §MP (lines 399–475) are all present in templates/skills/plan-feature/SKILL.md with normative content intact. No `/create-ac` active invocation surfaces remain in templates/commands/ or templates/skills/ (matches found are `create-ac-worktree` subcommand references and DECISION HISTORY exempt notes only). skill_registry.json parses as valid JSON with no `id: "create-ac"` entry (36 entries remain). Guard files scripts/setup_ticket_worktree.py, templates/scripts/setup_ticket_worktree.py, config/agent_registry.json, and scripts/build.py show zero diff. Diff scope is exactly the 5 expected files with no unexpected additions.

### 2026-06-29 15:00 — commit (status: ok)

feedback-id: (submit-failed)
Auto-authorized commit gate: subject "feat(skills): complete ACD-1100c — migrate create-ac spec into plan-feature"; staged files: config/skill_registry.json templates/skills/build-single-ticket/SKILL.md templates/skills/create-ac/SKILL.md templates/skills/plan-feature/SKILL.md tickets/00_inbox/TICKET-20260629-CompleteACD1100c-MigrateCreateAcToplanFeature.md.

SHA: ebcc30c6f3dd77ea3eff32f5d04cb844e3cc4033. Pre-commit hook autofix applied: added `feedback-id: (submit-failed)` to python-coder comment heading before retrying commit.

completion_manifest:
  commit_executed: true
  pre_commit_hooks_passed: true
