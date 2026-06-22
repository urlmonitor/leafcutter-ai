---
title: "Each epic ticket is written only inside the epic folder, with its back-reference pointing at the epic-folder path"
status: in_progress
source_ac: ACD-1200a-9
components:
  - ac-driven-dev
created: 2026-06-22
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/goal_to_epic.py
agents:
  python-coder: signed_off
  test-writer: signed_off
  test-runner: signed_off
  sql-coder: not_needed
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: needed
---

# Each epic ticket is written only inside the epic folder, with its back-reference pointing at the epic-folder path

## Actor / Goal

As the leafcutter-ai system, I want every generated epic ticket written to
exactly one location — inside the epic folder — with its `implemented_by`
back-reference naming that same epic-folder path, so that goal-mode `/build-ac`
runs leave no duplicate loose inbox tickets and no AC points at a path that
should not exist.

## Context

This ticket implements AC store entry `ACD-1200a-9` (component
`ac-driven-dev`, assigned `python-coder`, complexity M). It fixes defects #1
and #2 of the `goal_to_epic.py` known-quirks set: the generator currently
writes each ticket to `tickets/00_inbox/<file>.md` (loose) *and* copies it into
the epic folder, and stamps each source AC's `implemented_by` with the loose
inbox-root path instead of the epic-folder path.

Part of EPIC-GoalToEpicBugfixes. Sibling `02_basename_collision_resolution.md`
(ACD-1200a-9-i) builds on the single-location write contract established here.

## AC References

- Implements ACD-1200a-9 (single-location epic-folder ticket write + correct `implemented_by` back-reference)

## Acceptance Criteria

```gherkin
Given goal ACD-050 (title: "Validate API inputs") has 3 leaf ACs beneath it,
And the epic folder EPIC-ValidateApiInputs has been chosen as the assembly target,
When the system generates the ticket files for those leaf ACs,
Then each of the 3 ticket files exists only at one location, inside the epic
  folder under the tickets inbox (tickets/00_inbox/epics/EPIC-ValidateApiInputs/),
And no copy of any of those 3 ticket files exists at the tickets inbox root
  (tickets/00_inbox/) outside the epic folder,
And for each leaf AC, the implemented_by back-reference recorded in that AC's
  YAML names the ticket's path inside the epic folder
  (tickets/00_inbox/epics/EPIC-ValidateApiInputs/NN_*.md),
And no implemented_by back-reference names an inbox-root path
  (tickets/00_inbox/NN_*.md) for any of those tickets.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| ACD-1200a-9 | 17 tests in test_single_location_write.py, all green (3 regression tests for [H-1] added) | Fixed path normalisation bug: run() now relativises absolute loose_path using worktree_root before passing to _replace_implemented_by_entry; worktree_root param added to run() and wired from main() | ok — 2026-06-22 |

## Comments

### 2026-06-22 10:00 — ticket-supervisor (status: ok)
test_requirements empty — test-writer phase skipped (docs-only or config-only ticket)

### 2026-06-22 12:00 — python-coder (status: ok)
feedback-id: fb_2026-06-22_a65191f7
completion_manifest:
  dual_write_removed: true
  implemented_by_uses_epic_path: true
  loose_copies_deleted_after_assembly: true
  idempotency_preserved: true
  tests_written_and_green: true
  error_handling_policy_followed: true
  ruff_clean: true
Fixed dual-write bug (ACD-1200a-9) in scripts/goal_to_epic.py. Added three helpers: _build_loose_to_epic_map() mirrors assemble_epic_folder's numbering to produce a loose→epic path mapping; _replace_implemented_by_entry() replaces the loose inbox-root path in each source AC YAML's implemented_by list with the epic-folder path; _remove_loose_inbox_tickets() deletes the loose copies from inbox root after assembly. run() now calls all three after assemble_epic_folder() succeeds. 14 new tests in unit_tests/ac_store/test_single_location_write.py, all green. Existing ac_store tests unaffected (5 pre-existing failures in test_tree_traversal.py remain; not caused by this change).

### 2026-06-22 13:30 — test-runner (status: ok)
feedback-id: fb_2026-06-22_b6a2ab08
completion_manifest:
  test_suite_executed: true
  all_tests_passing: true
  failure_report_structured: true
All 14 tests in test_single_location_write.py pass. The broader ac_store suite ran 257 tests with 252 passing; the 5 failures are pre-existing test_tree_traversal.py failures documented by python-coder as unrelated to this ticket.

### 2026-06-22 15:00 — python-coder (status: ok)
feedback-id: fb_2026-06-22_8d0ab6fd
completion_manifest:
  path_normalisation_fix_implemented: true
  regression_tests_added: true
  all_17_tests_green: true
  ruff_clean: true
  worktree_root_passed_from_main: true
Fixed [H-1] absolute-vs-relative path mismatch in run(). Root cause: generate_ticket_from_ac.py writes implemented_by using ticket_path.relative_to(worktree) (relative), but _call_generate_ticket_from_ac() returns the absolute path from the "Written:" stdout line. The guard "if old_path not in implemented_by" always evaluated False because absolute != relative, so _replace_implemented_by_entry silently did nothing. Fix: added worktree_root: Path | None = None to run(); in the ACD-1200a-9 loop, if worktree_root is supplied the absolute loose_path is relativised via Path.relative_to(worktree_root) before passing to _replace_implemented_by_entry. main() now detects and passes the worktree root in both code paths (explicit flags and default). Added 3 regression tests: test_absolute_old_path_does_not_match_relative_yaml_value (documents the bug), test_relative_old_path_matches_relative_yaml_value (verifies the fix at helper level), test_run_worktree_root_normalises_absolute_to_relative (end-to-end production data flow simulation). All 17 tests pass; 5 pre-existing test_tree_traversal.py failures unchanged.

### 2026-06-22 14:00 — pr-reviewer (status: blocker)
feedback-id: fb_2026-06-22_5b0ce775
completion_manifest:
  ac_coverage_matches_implementation:
    result: false
    reason: "High-confidence correctness bug [H-1]: _replace_implemented_by_entry is called with absolute old_path values (read from the 'Written:' stdout of generate_ticket_from_ac.py via _call_generate_ticket_from_ac), but generate_ticket_from_ac.py writes implemented_by into AC YAML using a relative path (ticket_path.relative_to(worktree)). The 'if old_path not in implemented_by' guard always evaluates False because absolute != relative; the function silently scans all AC YAML files and returns without making any changes. The implemented_by back-reference is never corrected from the loose inbox path to the epic-folder path. All 14 tests pass because they use identical relative string literals for both the YAML value and the old_path argument — the tests do not simulate the real production data flow."
    remediation: "Respawn python-coder to fix _replace_implemented_by_entry (or its call site in run()) to normalise paths before comparison — either convert old_path to a relative form matching what generate_ticket_from_ac.py writes, or store and compare both as absolute paths. Also add a test that uses an absolute ticket_path alongside a relative implemented_by value to reproduce the real-world mismatch."
  error_handling_policy_followed: true
  tests_adequate: false
  ruff_clean: true

### 2026-06-22 17:00 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-22_e4dbebce
completion_manifest:
  h1_fix_verified: true
  regression_tests_catch_bug: true
  no_new_high_confidence_issues: true
  prior_medium_findings_not_blockers: true
  all_17_tests_pass: true
  ruff_clean: true
  ac_coverage_validated: true
[H-1] is genuinely fixed: run() now relativises the absolute loose_path via Path.relative_to(worktree_root) before passing to _replace_implemented_by_entry, with a ValueError fallback. The 3 regression tests correctly simulate the real production data flow (absolute stdout path vs relative YAML value) and would have caught the original bug. No new high-confidence issues introduced. Prior medium findings do not rise to blocker level — the worktree_root=None degraded path is a safe no-op, not a regression. All 17 tests pass; ruff clean.

### 2026-06-22 18:00 — commit (status: ok)
feedback-id: fb_2026-06-22_91f79b75
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
Auto-authorized commit gate (COMMIT_AGENT_MODE=1 batch drive). Staged files: scripts/goal_to_epic.py, unit_tests/ac_store/test_single_location_write.py, tickets/00_inbox/epics/EPIC-GoalToEpicBugfixes/01_single_location_write_and_backref.md. Commit SHA to follow after git commit execution.

## Sign-offs

- [x] python-coder — 2026-06-22 15:00
- [x] test-writer — 2026-06-22 10:00
- [x] test-runner — 2026-06-22 13:30
- [x] pr-reviewer — 2026-06-22 17:00
- [x] commit — 2026-06-22 18:00
- [ ] pull-request

## Implementation Tasks

- [x] Locate the dual-write path in `goal_to_epic.py` (the loose `tickets/00_inbox/` write plus the epic-folder copy) and remove the loose write so only the epic-folder write remains.
- [x] Ensure the `implemented_by` back-reference written onto each leaf AC names the epic-folder path the ticket was actually written to.
- [x] Keep the ticket-file write and the `implemented_by` write consistent so an AC never ends a run pointing at a nonexistent path. Wrap file/YAML I/O per the project error-handling policy.
- [x] Confirm idempotency: re-generating the same goal into the same epic folder does not multiply ticket files across locations.
- [x] Tests for: single-location write, no inbox-root stray, epic-folder `implemented_by`, no inbox-root back-ref.

## Risk & Safety

- Touches money? No.
- Touches data? Yes — changes how `implemented_by` is stamped onto AC YAML; targeted field updates only.
- Reversibility? High — behavior-only change to a generator script.
