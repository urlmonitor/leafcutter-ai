---
title: "V3 template knowledge steps — inject at start, emit before exit"
status: done
components:
  - infrastructure
created: 2026-06-05
depends_on: []
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
  architect-review: signed_off
  adr-author: not_needed
  architecture-diagram-author: not_needed
  test-writer: not_needed
  python-coder: not_needed
  llm-expert: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
source_acs:
  - INF-400a-1
  - INF-400a-2
  - INF-400a-3
  - INF-400a-4
  - INF-400a-4-i
  - INF-400b-1
  - INF-400b-2
  - INF-400b-3
  - INF-400b-1-i
  - INF-400b-1-ii
---

# 00: V3 template knowledge steps — inject at start, emit before exit

## Actor / Goal

As the leafcutter-ai system, I want the three v3 pipeline agent templates
(PO v3, BA v3, IT PO v3) to include a pre-flight knowledge injection step
and a post-work knowledge emission step — so that these agents participate
in the knowledge lifecycle even though they do not use the signoff skill.

## Context

The v3 agents have `signoff: false`, so the mandatory §7 knowledge-capture
trigger never fires. They exit without persisting anything they learned.
The knowledge system (route-learning, capture-learning, PROJECT_CONTEXT.md)
already exists — the gap is that these agents don't invoke it.

This ticket adds two steps to each of the three templates:

1. **Pre-flight (inject)**: Before the agent's first substantive action, it
   reads domain-scoped accumulated context (PROJECT_CONTEXT.md, component
   README, per-agent memory files).

2. **Post-work (emit)**: After the agent produces its final output but before
   returning control, it runs a reflection prompt ("Did you discover any
   component conventions, user preferences, or domain patterns?") and
   invokes route-learning + capture-learning on "yes."

## Acceptance Criteria

```gherkin
# AC-1: Pre-flight step loads domain context (INF-400a-1)

Given the product-owner-v3, business-analyst-v3, and it-po-v3 agent templates,
When an agent is spawned to work on a feature in a specific component,
Then the agent template contains a pre-flight step that instructs the agent to:
  1. Identify the component from the L1 AC or ticket it was given,
  2. Read the PROJECT_CONTEXT.md file co-located with any skill the agent loads,
  3. Read the per-folder README.md for the component's AC directory,
And the pre-flight step appears before the agent's first numbered working step,
And the pre-flight step specifies that missing files are skipped without error.

# AC-2: Agents read their own prior-run memory files (INF-400a-2)

Given the product-owner-v3 agent has run previously and persisted a learning
  to memory/project_po_framing.md,
When the agent is spawned for a new run,
Then the pre-flight step includes reading memory files that match the agent's
  name pattern (e.g., memory/*po*.md, memory/*product*.md),
And the agent's context includes the content of those files before its first
  substantive action.

# AC-3: Agents read component-scoped PROJECT_CONTEXT.md (INF-400a-3)

Given a PROJECT_CONTEXT.md file exists at
  docs/acceptance-criteria/infrastructure/PROJECT_CONTEXT.md,
When the business-analyst-v3 agent is spawned to work on component infrastructure,
Then the pre-flight step reads that PROJECT_CONTEXT.md file,
And the agent's context includes the accumulated learnings about that component.

# AC-4: First run with no prior context produces normal-quality output (INF-400a-4)

Given no PROJECT_CONTEXT.md, README.md, or memory files exist for the target
  component,
When any v3 agent is spawned for the first time on that component,
Then the pre-flight step completes without errors (all reads skipped gracefully),
And the agent produces output at normal quality (same as before this ticket).

# AC-5: Corrupted PROJECT_CONTEXT.md does not crash the agent (INF-400a-4-i)

Given a PROJECT_CONTEXT.md file exists but contains invalid content
  (binary data, truncated YAML, or content exceeding 50KB),
When a v3 agent's pre-flight step attempts to read it,
Then the step logs a warning and skips the file,
And the agent proceeds with its remaining context.

# AC-6: Post-work capture step fires before exit (INF-400b-1)

Given the product-owner-v3, business-analyst-v3, and it-po-v3 agent templates,
When the agent template is read by a human or validation tool,
Then the template contains a mandatory post-work step that:
  1. Prompts: "Did you discover any component conventions, user preferences,
     or domain patterns during this run that future agents working in this
     component would benefit from knowing?",
  2. On "yes": directs the agent to invoke route-learning to classify,
  3. On "yes": directs the agent to invoke capture-learning to persist,
  4. On "yes": directs the agent to emit a knowledge_captured event to telemetry,
  5. On "no": proceeds without writing anything,
And this step is not conditional on ticket_path being present.

# AC-7: Emission schema matches signoff §7 (INF-400b-2)

Given a v3 agent captures a learning via the post-work step,
When the knowledge_captured event is emitted to the telemetry sink,
Then the event uses the same JSONL schema as signoff §7 events:
  { event: "knowledge_captured", timestamp: ISO-8601, agent: string,
    component: string, destination: string, entry_kind: string },
And the event is parseable by existing telemetry consumers without modification.

# AC-8: Capture prompt is domain-appropriate for specification work (INF-400b-3)

Given the v3 agents produce specifications (not code),
When the post-work reflection prompt fires,
Then the prompt asks about specification-relevant learnings:
  component conventions, naming patterns, standing rules, user framing
  preferences, agent assignment patterns, decomposition strategies,
And does NOT ask about code-level learnings (implementation patterns,
  error handling conventions, test strategies).

# AC-9: Capture failure does not block agent exit (INF-400b-1-i)

Given the route-learning or capture-learning skill is unavailable
  (missing, broken, or erroring),
When the post-work capture step encounters the failure,
Then the agent logs a warning about the failed capture,
And the agent returns its output normally without blocking,
And the agent does NOT retry or re-prompt.

# AC-10: Duplicate learnings are not persisted twice (INF-400b-1-ii)

Given the business-analyst-v3 agent discovers a learning "INF prefix ACs
  have no parent component" during run 1 and persists it,
When the same agent discovers the same learning during run 2,
Then the capture step detects the duplicate (via route-learning Step 0)
  and does not persist it a second time.
```

## Sign-offs

- [x] architect-review — 2026-06-05 10:00
- [x] llm-expert — 2026-06-05 10:15
- [x] test-runner — 2026-06-05 10:30
- [x] pr-reviewer — 2026-06-05 10:45
- [x] commit — 2026-06-05 11:00
- [x] pull-request — 2026-06-05 11:15

## Comments

### 2026-06-05 11:15 — pull-request (status: ok)
feedback-id: fb_2026-06-05_e7c35c64
completion_manifest:
  branch_pushed: true
  pr_opened: true
  pr_url_recorded: true

Pushed EPIC-AgentLearningLoop branch to origin. PR #60 opened at
https://github.com/urlmonitor/leafcutter-ai/pull/60 against main.

### 2026-06-05 11:00 — commit (status: ok)
feedback-id: fb_2026-06-05_de9e9743
completion_manifest:
  files_staged_explicitly: true
  commit_succeeded: true
  no_cross_worktree_pollution: true

Committed 4 files (3 v3 templates + ticket) as SHA 650a53c. Used explicit
git add per path (not git add .). Pre-commit hook absent (PRE_COMMIT_ALLOW_NO_CONFIG=1
used). Lock acquired before commit and released after. 553 insertions total.

### 2026-06-05 10:45 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-05_a23dd488
completion_manifest:
  diff_reviewed: true
  no_high_findings: true
  scope_verified: true

Reviewed the working diff against all 10 ACs. All additions are purely additive
template insertions — no code modified, no migrations, no API changes. All ACs
confirmed addressed: AC-1 through AC-5 covered by the pre-flight S0/§0 sections;
AC-6 through AC-10 covered by the post-work S8/§9/S9 sections. No high-confidence
findings. The 50 KB guard (AC-5), best-effort wrapping (AC-9), and duplicate
detection delegation to route-learning Step 0 (AC-10) are all correctly specified.

### 2026-06-05 10:30 — test-runner (status: ok)
feedback-id: fb_2026-06-05_cafc4986
completion_manifest:
  tests_run: true
  no_regression_from_template_changes: true
  pre_existing_failures_confirmed_unrelated: true

Ran 243 tests (excluding release/ and import-failing modules). 240 passed, 3
failed. All 3 failures are pre-existing baseline failures confirmed against
HEAD before this ticket's changes were applied — they relate to missing
`scripts.build_precommit` module (AC from a different ticket) and workflow
output path (separate unimplemented feature). No regressions from the v3
template insertions.

### 2026-06-05 10:15 — llm-expert (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  po_v3_preflight_added: true
  po_v3_postemit_added: true
  ba_v3_preflight_added: true
  ba_v3_postemit_added: true
  itpo_v3_preflight_added: true
  itpo_v3_postemit_added: true

Added S0/§0 Knowledge Loop Injection (pre-flight) and S8/§9/S9 Knowledge Loop
Emission (post-work) sections to all three v3 agent templates. Each pre-flight
step reads component PROJECT_CONTEXT.md, component README.md, and per-agent
memory files (graceful skip if absent, 50 KB guard per AC-5). Each post-work
step runs a specification-scoped reflection prompt; on "yes" invokes
route-learning then capture-learning then emits knowledge_captured telemetry;
wrapped in best-effort so capture failure does not block agent exit (AC-9).
Duplicate detection delegated to route-learning Step 0 (AC-10). Emission schema
matches signoff §7 with `agent` and `component` fields added (AC-7).

### 2026-06-05 10:00 — architect-review (status: ok)
feedback-id: fb_2026-06-05_d7bc845f
completion_manifest:
  blast_radius_assessed: true
  impact_classified: true
  architectural_note_written: true

Architectural review complete. Classification: SMALL. Three purely additive template
insertions (product-owner-v3.md, business-analyst-v3.md, it-po-v3.md). No always-large
trigger fired; ≤5 files, single component (templates/agents), no cross-module boundary.

Channels confirmed: ②/③/⑨ injection paths are correct for the pre-flight step; the
v3 agents have `signoff: false` so explicit reads in the pre-flight body compensate for
bypassed harness auto-memory. AC-7 emission schema is additive to signoff §7 schema
(adds `agent` and `component` fields) — backward-compatible with existing telemetry
consumers.

Design concern: the pre-flight step should guard for very large PROJECT_CONTEXT.md
files (AC-5 already handles this). The post-work emission step must use best-effort
wrapping per AC-9 — failure must not block agent exit.

No ADR required. No diagram required.

## Escalation

Branch: none
Reason: 3 additive template files in a single component; no always-large trigger fired.

## Implementation Tasks

### architect-review

- [x] Read the three v3 agent templates to confirm the current section
  numbering and identify the correct insertion points for pre-flight and
  post-work steps.
- [x] Read `docs/architecture/agent_knowledge_system.md` and
  `agent_knowledge_plane.md` to confirm the injection channels (②, ③, ⑨)
  and capture pipeline (route-learning → capture-learning) referenced
  by the ACs.
- [x] Verify that the emission schema in AC-7 is compatible with the
  existing `knowledge_captured` event format in `signoff` §7.
- [x] Confirm that the memory-file read pattern (AC-2) is compatible with
  the auto-memory injection mechanism (Channel ⑨).

### llm-expert

- [x] Add a pre-flight section to `templates/agents/product-owner-v3.md`:
  - Insert as a new section before S1 (Knowledge Acquisition).
  - Name it "S0 Knowledge Loop — Injection" or integrate into S1.
  - Read: component PROJECT_CONTEXT.md, component AC README.md, per-agent
    memory files. Skip gracefully if absent.
- [x] Add a pre-flight section to `templates/agents/business-analyst-v3.md`:
  - Insert before §1 (Knowledge Acquisition Protocol).
  - Same pattern: read PROJECT_CONTEXT.md, README.md, memory files.
- [x] Add a pre-flight section to `templates/agents/it-po-v3.md`:
  - Insert before S1 (Knowledge Acquisition).
  - Same pattern.
- [x] Add a post-work section to `templates/agents/product-owner-v3.md`:
  - Insert after S7 (Handoff) as new section S8 "Knowledge Loop — Emission."
  - Reflection prompt scoped to specification-relevant learnings.
  - On "yes": invoke route-learning, then capture-learning, then emit event.
  - On "no": proceed without writing.
  - Wrap in best-effort: failure logs warning, does not block exit.
- [x] Add a post-work section to `templates/agents/business-analyst-v3.md`:
  - Insert after §8 (Sign-Off Protocol) as new section §9.
  - Same reflection prompt pattern.
- [x] Add a post-work section to `templates/agents/it-po-v3.md`:
  - Insert after S8 (Self-Review Checklist) as new section S9.
  - Same reflection prompt pattern.

## Risk & Safety

- Touches money? No.
- Touches data? Modifies three agent template files. Template edits are
  additive (new sections only, no existing section changes).
- Reversibility? The new sections can be removed in a single commit per
  template.
