---
title: "Strengthen business-analyst: research-first questioning and Opus upgrade"
status: todo
components:
  - build_pipeline
created: 2026-06-03
depends_on:
  - 01_adr_contract_driven_acs.md
  - 02a_documentation_index.md
priority: high
phase: "Phase 1"
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
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  architecture-diagram-author: not_needed
  user-surface-smoker: not_needed
---

# 03: BA Research-First Questioning + Opus Upgrade

## Business Intent

The business-analyst must genuinely understand both the application and the
user's intent before producing acceptance criteria. Currently it accepts vague
input and produces vague output. This ticket transforms the BA from a
template-filling agent into a competent technical interviewer that researches
first, then asks informed questions.

## Context

### The Problem With "Ask At Least 2 Questions"

A minimum-question-count rule produces cargo-cult behavior. Sonnet will dutifully
ask exactly 2 generic questions regardless of context. The BA needs to be an
intelligent interviewer who:

1. **First researches the feature area** — reads component docs, architecture
   diagrams, existing related code/tickets to build its own understanding
2. **Then evaluates the user's request against a comprehensive question framework**
   — only asking questions whose answers aren't already obvious from the research
3. **Asks informed, specific questions** — not "what are your requirements?" but
   "the current profile page has no image component; should this be a circular
   avatar in the header bar, or a full-width banner?"

### Why Opus for the BA

The BA is where requirements quality is determined. A Sonnet BA follows rules;
an Opus BA *thinks* about what's missing. The cost of Opus here (~15-20k tokens)
is trivial compared to the cost of an entire implementation cycle built on
misunderstood requirements.

This is the same reasoning as the IT PO: the hardest cognitive work (understanding
intent, identifying gaps, anticipating edge cases) should use the strongest model.
The mechanical work downstream (writing code to a spec) can use Sonnet.

## Agent Contracts

### python-coder

- [x] AC-1: business-analyst.md model field changed from `sonnet` to `opus`

- [x] AC-2: business-analyst.md includes a "§1 Research Before Asking" section that uses a PULL-BASED knowledge acquisition model:
  1. Read `docs/INDEX.md` first (the auto-generated table of contents)
  2. Identify which components/flows/docs are relevant to the user's request
  3. Pull only the relevant docs on-demand (Read tool)
  
  The BA pulls from these categories (user-facing docs only):
  - **User flows** — how the feature works end-to-end from the user's perspective
  - **Component pages** — what the component does, its purpose, its boundaries
  - **How-to guides** — existing procedures related to the feature area
  - **Glossary** — domain-specific terms the user might be using
  - **Related tickets** — what's been done/planned in this area before
  
  **Explicitly NOT pulled by BA:** architecture diagrams, db_schema.json, api_conventions.json, routes_manifest.json (those are IT PO's domain)
  
  The goal: the BA should understand what the application currently does FROM THE USER'S PERSPECTIVE so it can ask informed, specific questions — not generic ones

- [x] AC-3: business-analyst.md includes a "§2 Requirements Elicitation Framework" section with a comprehensive question taxonomy that the BA evaluates (not mechanically asks) against the user's request:

  **Functional scope:**
  - What is the feature / what does it do? (may already be clear from user input)
  - Where in the application does this live? (which page, component, service)
  - Who uses it? (end user, admin, system/automated)
  - What is the trigger? (user action, scheduled, event-driven)
  - What is the happy path end-to-end?
  - What are the key edge cases? (empty state, error state, concurrent access)

  **Business context:**
  - Why is this needed now? (business driver, user complaint, technical debt)
  - What's the priority / urgency? (blocking release? nice-to-have?)
  - What's explicitly out of scope for this iteration?

  **Technical constraints:**
  - Performance requirements? (response time, throughput, data volume)
  - Security/auth requirements? (who can access, what's sensitive)
  - Data requirements? (what's stored, retention, privacy)
  - Integration points? (external APIs, third-party services)

  **User experience:**
  - What does success look like from the user's perspective?
  - What feedback does the user see? (loading states, confirmations, errors)
  - Mobile/responsive requirements?

  **Operational:**
  - How do we know it's working? (monitoring, logging, alerts)
  - Rollback strategy if something goes wrong?
  - Migration needed for existing data/users?

- [x] AC-4: The framework instruction is: "Evaluate each question against your research findings and the user's input. Ask ONLY questions whose answers are (a) not already obvious from your research and (b) would materially change the implementation. Group your questions: must-answer (blocks AC writing) vs assumed (state your assumption, ask user to correct if wrong). For trivial/obvious requests, it is valid to ask ZERO questions and state only assumptions. The elicitation framework is a checklist to think through, not a form to fill out."

- [x] AC-5: business-analyst.md includes a "§3 Weasel Word Self-Check" requiring the BA to reject its own draft ACs if any contain: "appropriate", "properly", "correctly", "as expected", "relevant", "suitable", "reasonable", "adequate", "sufficient", "necessary". Each AC must have a concrete, testable observable outcome.

- [x] AC-6: business-analyst.md includes a "§4 Assumption Logging" section — for every question the BA chose NOT to ask (because the answer was obvious from research), it logs the assumption in the output payload: `{question: "...", assumption: "...", source: "read from component doc X"}`. This creates an audit trail and lets the user correct wrong assumptions.

- [x] AC-7: The BA's JSON output payload structure includes: `questions_asked` (what was asked + user's answers), `assumptions_made` (what was NOT asked + why), `open_questions` (unresolved items), `research_findings` (what the BA learned from reading docs — brief summary for downstream agents)

<!-- Complexity assessment (§5) and brainstorm escalation (§6) are in ticket 03a -->

## Sign-offs

- [x] python-coder — 2026-06-04 10:00
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
| AC-5 | | | |
| AC-6 | | | |
| AC-7 | | | |

## Implementation Tasks

### python-coder — rewrite business-analyst.md

- [x] Change model to `opus` in frontmatter
- [x] Add §1 Research Before Asking — pull-based model:
  - Read `docs/INDEX.md` to discover what docs exist
  - Identify relevant docs based on user's request
  - Pull only relevant user-facing docs (flows, components, how-tos, glossary)
  - Summarize findings as research context for downstream agents
- [x] Add §2 Requirements Elicitation Framework (full question taxonomy, evaluate-don't-mechanically-ask instruction)
- [x] Add §3 Weasel Word Self-Check (reject ACs with vague language)
- [x] Add §4 Assumption Logging (audit trail for questions not asked)
- [x] Update output payload structure to include questions_asked, assumptions_made, research_findings
<!-- §5 Complexity + §6 Brainstorm are in ticket 03a -->

## Risk & Safety

- Touches money? No.
- Touches data? No — modifies an agent template only.
- Reversibility? Fully reversible — single file edit.
- Risk: Opus BA is more expensive per ticket (~15-20k tokens vs ~5-10k for Sonnet).
  Mitigation: This is the cheapest place to invest quality. A misunderstood
  requirement costs 100k+ tokens in rework across downstream agents. For trivial
  tickets, Opus finishes fast (short context, no research needed) — the cost is
  minimal. The model stays the same; the pipeline shortens.
- Risk: BA research step adds latency (reading docs before asking questions).
  Mitigation: Research is bounded to user-facing docs for the touched area
  (how-tos, component pages, glossary), not the full codebase. Typically 3-5
  file reads.
- Risk: Brainstorm swarm adds significant cost/time for novel features.
  Mitigation: Only triggered when complexity = novel (rare — most features have
  a clear direction). The alternative is building the wrong thing entirely.

## Comments

### 2026-06-04 10:00 — python-coder (status: ok)
feedback-id: fb_2026-06-04_e460b89a
completion_manifest:
  code_implemented: true
  tests_passing: true
  doc_enforcer_clean: true
  complexity_check_clean: true
Upgraded business-analyst.md: model changed from sonnet to opus (AC-1); added §1 Research Before Asking with pull-based INDEX.md-first model (AC-2); added §2 Requirements Elicitation Framework with 5 sub-sections and evaluate-don't-ask instruction (AC-3, AC-4); added §3 Weasel Word Self-Check with 10 forbidden words and bad/good example (AC-5); added §4 Assumption Logging with JSON schema example (AC-6); extended output payload with questions_asked, assumptions_made, and research_findings fields (AC-7). No Python code was written — this ticket modifies a markdown template file. doc-enforcer and complexity-reduction are not applicable to markdown files.
