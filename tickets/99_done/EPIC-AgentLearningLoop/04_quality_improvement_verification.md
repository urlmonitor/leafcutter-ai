---
title: "Verify second-run quality improvement for PO, BA, and IT PO"
status: todo
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

- [ ] Define what "measurable quality improvement" means in concrete terms
  for each agent type. Propose assertion criteria that tests can check.
- [ ] Determine whether these tests should be integration tests (spawning
  real agents) or unit tests (checking that context files are read and
  influence output). Recommend the testing strategy.

### test-writer

- [ ] Write `tests/knowledge/test_quality_improvement.py`:
  - Test strategy per architect-review recommendation.
  - For each AC: set up fixtures with pre-populated context files, run the
    agent (or simulate the pre-flight read), and assert the output reflects
    the accumulated knowledge.
  - Mark as slow tests if they require agent spawning.

### python-coder

- [ ] Implement any test fixtures or helpers needed by the quality tests.
  - Fixture AC YAML files for component X and Y.
  - Pre-populated PROJECT_CONTEXT.md and memory files with sample learnings.
  - Output assertion helpers that check for specific patterns in generated
    AC YAML.

## Risk & Safety

- Touches money? No.
- Touches data? Test fixtures only. No production files modified.
- This ticket depends on all three prior tickets being complete. If the
  knowledge loop has gaps, these tests will fail and surface them.
