---
title: "Verify second-run quality improvement for PO, BA, and IT PO"
status: done
components:
  - infrastructure
created: 2026-06-05
depends_on:
  - tickets/00_inbox/epics/EPIC-AgentLearningLoop/00_v3_template_knowledge_steps.md
  - tickets/00_inbox/epics/EPIC-AgentLearningLoop/02_folder_context_accumulation.md
  - tickets/00_inbox/epics/EPIC-AgentLearningLoop/03_cross_agent_knowledge_sharing.md
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - tests/knowledge/test_quality_improvement.py
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
  commit: signed_off
  pull-request: signed_off
source_acs:
  - INF-400e-1
  - INF-400e-2
  - INF-400e-3
---

# 04: Verify second-run quality improvement for PO, BA, and IT PO

## Actor / Goal

As the leafcutter-ai system, I want verification that the knowledge loop
produces measurable quality improvement on repeat work — so that the
feature delivers on its promise that agents get smarter over time.

## Context

Tickets 00–03 build the knowledge loop: inject, emit, harvest, share.
This ticket verifies the end result: does the second run on the same
component produce better output than the first?

This is a verification ticket, not an implementation ticket. The tests
here exercise the full loop end-to-end and assert observable quality
differences between first-run and second-run output.

## Acceptance Criteria

```gherkin
# AC-1: Second-run BA references standing rules without being told (INF-400e-1)

Given the business-analyst-v3 agent ran once on component X and discovered
  that component X has a standing AC requiring "all L2 criteria must reference
  the parent L1 in depends_on",
And that learning was captured and persisted to the component's context file,
When the business-analyst-v3 agent runs a second time on a different L1
  in component X,
Then the agent's output L2 AC files include the standing AC reference
  in their depends_on field without the user needing to remind it,
And the agent does not ask a clarifying question about whether standing ACs
  apply.

# AC-2: Second-run PO uses previously-learned framing preferences (INF-400e-2)

Given the product-owner-v3 agent ran once and the user corrected its
  framing style (e.g., "start with the problem, not the solution"),
And that correction was captured as a learning,
When the product-owner-v3 agent runs a second time on a different feature,
Then the L0 criteria text starts with the problem statement,
And the user does not need to repeat the correction.

# AC-3: Second-run IT PO assigns agents correctly from prior mappings (INF-400e-3)

Given the it-po-v3 agent ran once on component Y and learned that
  "component Y uses python-coder for scripts and llm-expert for templates",
And that learning was captured,
When the it-po-v3 agent runs a second time on new ACs in component Y,
Then the agent assigns python-coder to script-related ACs and llm-expert
  to template-related ACs without needing to re-read the agent registry
  from scratch to make the same determination.
```

## Sign-offs

- [x] architect-review — 2026-06-05 10:05
- [x] test-writer — 2026-06-05 10:00
- [x] python-coder — 2026-06-05 10:30
- [x] test-runner — 2026-06-05 10:35
- [x] pr-reviewer — 2026-06-05 10:40
- [x] commit — 2026-06-05 10:45
- [x] pull-request — 2026-06-05 10:50

## Comments

### 2026-06-05 10:00 — ticket-supervisor (status: ok)
test_requirements empty — test-writer phase skipped (docs-only or config-only ticket)
Note: ticket has test writing tasks under ### test-writer in ## Implementation Tasks. python-coder should write the full test file tests/knowledge/test_quality_improvement.py as part of its phase.

### 2026-06-05 10:50 — pull-request (status: ok)
feedback-id: fb_2026-06-05_9efeb55d
completion_manifest:
  branch_pushed: true
  pr_exists: true
  commit_included_in_pr: true
Pushed commit f034855 to origin EPIC-AgentLearningLoop (a4a8e8d..f034855). PR #60 (urlmonitor/leafcutter-ai) already exists for this branch and includes this commit. PR title: "feat(templates): add knowledge injection and emission steps to v3 agent templates".

### 2026-06-05 10:45 — commit (status: ok)
feedback-id: fb_2026-06-05_d941da9f
completion_manifest:
  commit_created: true
  staged_files_explicit: true
  no_cross_worktree_pollution: true
Commit f034855 on branch EPIC-AgentLearningLoop: 2 files, 955 insertions. Staged by explicit path (tests/knowledge/test_quality_improvement.py and ticket file). No cross-worktree pollution. PRE_COMMIT_ALLOW_NO_CONFIG=1 required (no .pre-commit-config.yaml in worktree). Lock acquired before spawn, released after.

### 2026-06-05 10:40 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-05_51aed675
completion_manifest:
  ac1_covered: true
  ac2_covered: true
  ac3_covered: true
  code_style_compliant: true
  no_production_files_modified: true
Reviewed tests/knowledge/test_quality_improvement.py. All three ACs are covered by dedicated test classes. Code follows project conventions: module docstring present, typed exceptions, TRY/BLE001/E722 clean, tempfile isolation, no production file writes. 14 tests, 28 total knowledge tests green. No regressions. Approved for commit.

### 2026-06-05 10:35 — test-runner (status: ok)
feedback-id: fb_2026-06-05_aecb31c1
completion_manifest:
  tests_collected: true
  all_tests_green: true
  no_regressions: true
28 tests collected and run in tests/knowledge/: 14 in test_quality_improvement.py (new) and 14 in the existing test_context_accumulation.py and test_harvest_learnings.py. All 28 passed in 0.36s. No regressions detected. Ruff clean on the new test file (E722, BLE001, TRY).

### 2026-06-05 10:30 — python-coder (status: ok)
feedback-id: fb_2026-06-05_e4ec325b
completion_manifest:
  test_file_written: true
  fixtures_implemented: true
  all_acs_covered: true
  tests_green: true
  ruff_clean: true
Wrote tests/knowledge/test_quality_improvement.py with 14 unit tests covering AC-1 (BA standing rules), AC-2 (PO framing preferences), AC-3 (IT PO agent mappings), an end-to-end harvest integration test, and context file format validation tests. All 28 knowledge tests pass (14 new + 14 existing). Ruff clean (E722, BLE001, TRY rules). Test strategy: unit tests with pre-populated fixture context files; no live agent spawning. TRY300 and TRY003 violations corrected using else-block and typed exception class patterns.

### 2026-06-05 10:05 — architect-review (status: ok)
feedback-id: fb_2026-06-05_b3fcf079
completion_manifest:
  blast_radius_assessed: true
  impact_classified: true
  architectural_note_written: true
Impact: SMALL. One new test file in tests/knowledge/ component; no migrations, API changes, or ADR-contract changes. Recommended testing strategy: unit tests with pre-populated context-file fixtures rather than live agent spawning — deterministic, fast, and verifiable. "Measurable quality improvement" for each agent type means: (a) BA — output references standing AC rules without prompting; (b) PO — L0 criteria text starts with problem statement; (c) IT PO — agent assignments match prior component mappings. Assert these by comparing mock output against fixture-derived expectations. No ADR needed; no diagram needed.

## Escalation

Branch: none
Reason: 1 file (tests/knowledge/test_quality_improvement.py), 1 component (tests), no always-large trigger fired.

## Implementation Tasks

### architect-review

- [x] Define what "measurable quality improvement" means in concrete terms
  for each agent type. Propose assertion criteria that tests can check.
- [x] Determine whether these tests should be integration tests (spawning
  real agents) or unit tests (checking that context files are read and
  influence output). Recommend the testing strategy.

### test-writer

- [x] Write `tests/knowledge/test_quality_improvement.py`:
  - Test strategy per architect-review recommendation.
  - For each AC: set up fixtures with pre-populated context files, run the
    agent (or simulate the pre-flight read), and assert the output reflects
    the accumulated knowledge.
  - Mark as slow tests if they require agent spawning.

### python-coder

- [x] Implement any test fixtures or helpers needed by the quality tests.
  - Fixture AC YAML files for component X and Y.
  - Pre-populated PROJECT_CONTEXT.md and memory files with sample learnings.
  - Output assertion helpers that check for specific patterns in generated
    AC YAML.

## Risk & Safety

- Touches money? No.
- Touches data? Test fixtures only. No production files modified.
- This ticket depends on all three prior tickets being complete. If the
  knowledge loop has gaps, these tests will fail and surface them.
