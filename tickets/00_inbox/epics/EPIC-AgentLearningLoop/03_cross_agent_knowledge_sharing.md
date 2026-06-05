---
title: "Cross-agent knowledge sharing via shared persistence"
status: todo
components:
  - infrastructure
created: 2026-06-05
depends_on:
  - tickets/00_inbox/epics/EPIC-AgentLearningLoop/00_v3_template_knowledge_steps.md
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/agents/product-owner-v3.md
  - templates/agents/business-analyst-v3.md
  - templates/agents/it-po-v3.md
agents:
  architect-review: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  test-writer: not_needed
  python-coder: not_needed
  llm-expert: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
source_acs:
  - INF-400f-1
  - INF-400f-2
  - INF-400f-3
  - INF-400f-1-i
---

# 03: Cross-agent knowledge sharing via shared persistence

## Actor / Goal

As the leafcutter-ai system, I want knowledge captured by one v3 pipeline
agent to be automatically available to the next agent in the same pipeline
run — so that the BA benefits from PO discoveries and the IT PO benefits
from BA discoveries without explicit hand-off messaging.

## Context

The v3 pipeline runs agents sequentially: PO v3 → BA v3 → IT PO v3. After
ticket 00, each agent captures learnings before exit. The key insight is
that no new infrastructure is needed for cross-agent sharing — the harness
already auto-loads memory files at spawn time (Channel ⑨). If the PO writes
a learning to a memory file, the BA will read it at spawn because the
harness injects all memory files.

This ticket verifies that the pipeline-level flow works end-to-end and that
the template instructions make this behavior explicit rather than accidental.

## Acceptance Criteria

```gherkin
# AC-1: PO learnings available to BA in same pipeline run (INF-400f-1)

Given the product-owner-v3 agent runs first and discovers a user preference
  (e.g., "user prefers value propositions to start with the problem"),
And the PO's knowledge-capture step persists that learning to
  memory/feedback_l0_framing_preference.md before the PO exits,
When the business-analyst-v3 agent is spawned next in the same pipeline run,
Then the BA's pre-flight step reads the memory file the PO just wrote,
And the BA's L2 decomposition reflects the PO's learned preference,
And no manual hand-off or explicit "pass this to the BA" instruction is required.

# AC-2: BA discoveries available to IT PO in same pipeline run (INF-400f-2)

Given the business-analyst-v3 agent discovers a component convention
  (e.g., "infrastructure ACs always include architect-review in the agent map"),
And the BA's knowledge-capture step persists that learning before exit,
When the it-po-v3 agent is spawned next in the same pipeline run,
Then the IT PO's pre-flight step reads the persisted learning,
And the IT PO's enrichment respects the discovered convention.

# AC-3: Knowledge flows through shared persistence, not message passing (INF-400f-3)

Given the v3 pipeline agents share knowledge across runs,
When the template instructions are reviewed,
Then the cross-agent knowledge flow relies on:
  - The emitting agent writing to a shared persistence surface (memory files,
    PROJECT_CONTEXT.md, component README),
  - The harness auto-loading those files at the next agent's spawn (Channel ⑨),
And there is NO agent-to-agent message passing, parameter forwarding, or
  explicit "hand this to the next agent" instruction in any template.

# AC-4: BA runs correctly when PO captures no learnings (INF-400f-1-i)

Given the product-owner-v3 agent runs but discovers nothing worth persisting
  (knowledge-capture prompt answered "no"),
When the business-analyst-v3 agent is spawned next,
Then the BA's pre-flight step finds no new memory files from the PO,
And the BA proceeds with its baseline context without errors,
And the BA's output quality is unchanged from the no-knowledge-loop baseline.
```

## Sign-offs

- [ ] architect-review
- [ ] llm-expert
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### architect-review

- [ ] Verify that the harness re-reads memory files between agent spawns
  within the same pipeline invocation. If the harness caches memory at
  session start, cross-agent sharing within a single run may not work.
  Document the finding.
- [ ] Confirm that the PO's capture-learning output destinations (memory
  files, PROJECT_CONTEXT.md) are within the set of paths the BA's
  pre-flight reads.

### llm-expert

- [ ] Review the three templates (after ticket 00 lands) to confirm the
  pre-flight + post-work steps enable the cross-agent flow without
  additional changes.
- [ ] If gaps are found, add explicit instructions to each template:
  - PO template: "Your post-work learnings persisted to memory/ or
    PROJECT_CONTEXT.md will be available to the BA in the same pipeline
    run. Write learnings that would help the BA decompose your L1s."
  - BA template: "Your pre-flight step may find learnings from the PO
    that just ran. Incorporate them into your analysis."
  - IT PO template: "Your pre-flight step may find learnings from both
    the PO and BA. Incorporate them into your enrichment."
- [ ] Ensure the "no learnings" path (AC-4) is explicitly handled in
  each template's pre-flight step (skip gracefully).

## Risk & Safety

- Touches money? No.
- Touches data? Template edits only. No new files or scripts.
- The key risk is harness caching: if memory files are loaded once at
  session start and not re-read between agent spawns, this ticket cannot
  work. Architect-review must verify this.
