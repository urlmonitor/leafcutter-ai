---
title: "Add complexity assessment and brainstorm escalation to BA"
status: todo
components:
  - build_pipeline
created: 2026-06-03
depends_on:
  - 03_ba_question_enforcement.md
priority: medium
phase: "Phase 2"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
user_facing_surface: null
files_touched:
  - templates/agents/business-analyst.md
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  architecture-diagram-author: not_needed
  user-surface-smoker: not_needed
---

# 03a: BA Complexity Assessment + Brainstorm Escalation

## Business Intent

After the BA understands the request (ticket 03), it classifies complexity to
determine pipeline routing, and spawns a brainstorm swarm for novel/ambiguous
features where multiple valid approaches exist.

## Agent Contracts

### python-coder

- [ ] AC-1: business-analyst.md includes "§5 Complexity Assessment" — classifies request after research as trivial (skip questions + IT PO), simple (skip IT PO), standard (full pipeline), or novel (brainstorm first)
- [ ] AC-2: Complexity classification is included in the BA output payload as `complexity` field
- [ ] AC-3: business-analyst.md includes "§6 Brainstorm Escalation" — when complexity = novel, spawns 2-3 brainstorm-worker agents with different perspectives, synthesizes options, presents to user, writes ACs only after user picks direction
- [ ] AC-4: BA output payload includes `questions_asked`, `assumptions_made`, `research_findings`, and `complexity` fields

## Sign-offs

- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |

## Risk & Safety

- Touches money? No.
- Touches data? No — modifies agent template only.
- Reversibility? Fully reversible — additive sections to existing template.
- Risk: Brainstorm swarm adds cost/time for novel features.
  Mitigation: only triggered when complexity = novel (rare).
