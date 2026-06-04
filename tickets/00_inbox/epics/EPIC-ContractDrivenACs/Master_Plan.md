---
title: "EPIC: Contract-Driven Acceptance Criteria"
type: epic
status: todo
components:
  - build_pipeline
created: 2026-06-03
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: true
requires_adr: true
---

# EPIC: Contract-Driven Acceptance Criteria

## Goal

In order to eliminate integration failures where agents build incompatible code
(frontend expects one API shape, backend builds another), we need to restructure
ticket creation so that acceptance criteria are per-agent technical contracts with
explicit interface specifications, so that each agent works against an unambiguous
spec and a final validator confirms coverage.

## Context

### The Problem

In recent ticket runs, business-level acceptance criteria were present but not
actionable enough for implementation agents:

1. ACs were written as Gherkin prose — human-readable but not machine-trackable
2. Sign-offs were per-phase ("python-coder: signed_off") with no link to which
   ACs the agent actually covered
3. No agent validated "did we cover ALL acceptance criteria?" at the end
4. When tickets touched multiple agents (sql-coder + python-coder + frontend-coder),
   no contract specified the interface between them — agents guessed at API shapes,
   field names, and data types independently

### The Solution: Two-Phase Ticket Creation

**Phase 1 — Business-analyst (Opus):** Researches the feature area first (reads
component docs, architecture diagrams, related tickets), then asks informed
questions based on a comprehensive elicitation framework. Only asks questions
whose answers aren't already obvious from research. Must NOT proceed until the
user confirms understanding. Logs assumptions for questions it chose not to ask.

**Phase 2 — IT PO (Opus):** Translates business ACs into per-agent technical ACs
with explicit interface contracts. Reads architecture diagrams and component docs
(NOT raw code — coders handle that). Produces the "Delivers to" / "Depends on"
contract blocks that specify exact data shapes, endpoints, and response types
between agents.

### Key Design Decisions

1. **Opus always for BA and IT PO.** The hardest cognitive work — understanding
   intent, identifying gaps, designing contracts — uses the strongest model.
   There is no model downgrade for "simple" tickets. Instead, process steps
   scale: simple tickets skip questions (obvious), skip IT PO (single-agent),
   skip brainstorm (clear direction). The model stays the same; the pipeline
   shortens.

2. **Pull-based knowledge acquisition via `docs/INDEX.md`.** Neither BA nor IT PO
   gets docs injected upfront. Both read the auto-generated INDEX.md (table of
   contents) first, then pull only the docs relevant to the current request.
   Clean separation of what each pulls:
   - BA pulls: user flows, how-tos, component pages, glossary
   - IT PO pulls: C4 diagrams, db_schema.json, api_conventions.json, routes_manifest.json
   Each specialist coder reads its own source files during implementation.
   INDEX.md auto-regenerates on every PR merge — always current, zero maintenance.

3. **BA and IT PO MUST ask questions.** Both use a comprehensive elicitation
   framework (not a minimum-count rule). They ask only questions whose answers
   aren't already obvious from their research. They log assumptions for questions
   they chose NOT to ask.

4. **AC format is numbered checklist, not Gherkin.** Machine-parseable via
   `- \[(x| )\] AC-\d+:` regex. Each AC gets an HTML comment attribution when
   signed off: `<!-- signed: python-coder -->`.

5. **ac-validator runs before commit.** A Sonnet agent at priority 11 that reads
   the AC checklist + diff + test output and produces a coverage matrix. Blocks
   on any missing AC.

6. **No sidecar files.** All AC state lives in the ticket markdown. Frontmatter
   gets one derived field: `ac_coverage: N/M`.

7. **Brainstorm swarm for novel/ambiguous features.** When the BA detects genuine
   design ambiguity (multiple valid architectures, no clear "right" approach), it
   spawns brainstorm agents with different perspectives, synthesizes options, and
   presents them to the user before writing ACs. This happens at design time, not
   just during failure adjudication.

### Relationship to Existing Agents

| Current Agent | Change |
|---------------|--------|
| business-analyst | Opus always. Research-first (user-facing docs), informed questions from elicitation framework, brainstorm swarm for novel features |
| refinement | Replaced by IT PO for multi-agent tickets; kept for single-agent |
| architect-review | Absorbed into IT PO (blast radius is part of contract design) |
| test-planner | Unchanged — reads technical ACs instead of business ACs |
| ac-validator | NEW — final coverage gate |

### Compute Model

Opus is the BA and IT PO, always. No model downgrade for simple tickets.
Process steps scale instead:

| Complexity | BA does | IT PO | Brainstorm |
|------------|---------|-------|------------|
| Trivial (typo fix) | Formats ticket, skips questions | Skip | Skip |
| Simple (single-agent) | Research + targeted questions | Skip (refinement) | Skip |
| Standard (multi-agent) | Full research + elicitation | Full contracts | Skip |
| Novel/ambiguous | Full research + elicitation | Full contracts | Swarm → user picks direction |

## Sub-Tickets

| # | File | Description | Phase | Status |
|---|------|-------------|-------|--------|
| 00 | [00_create_ticket_v2.md](./00_create_ticket_v2.md) | Parallel /create-ticket-v2 for testing new pipeline | 0 — test first | `[ ]` |
| 01 | [01_adr_contract_driven_acs.md](./01_adr_contract_driven_acs.md) | ADR documenting the contract-driven AC approach | 1 — foundations | `[ ]` |
| 02 | [02_ac_format_and_frontmatter.md](./02_ac_format_and_frontmatter.md) | Update ticket-authoring skill for numbered AC checklist + ac_coverage field | 1 — foundations | `[ ]` |
| 02a | [02a_documentation_index.md](./02a_documentation_index.md) | Auto-updating docs/INDEX.md for pull-based knowledge acquisition | 1 — foundations | `[ ]` |
| 02b | [02b_ac_count_hook.md](./02b_ac_count_hook.md) | Pre-commit hook: max 7 ACs per agent, max 20 per ticket | 1 — foundations | `[ ]` |
| 03 | [03_ba_question_enforcement.md](./03_ba_question_enforcement.md) | Upgrade BA to Opus, pull-based research + elicitation framework | 2 — agents | `[ ]` |
| 03a | [03a_ba_complexity_and_brainstorm.md](./03a_ba_complexity_and_brainstorm.md) | Add complexity routing + brainstorm escalation to BA | 2 — agents | `[ ]` |
| 04 | [04_it_po_agent.md](./04_it_po_agent.md) | Create IT PO agent (Opus) — translates business ACs into per-agent contracts | 2 — agents | `[ ]` |
| 05 | [05_ac_validator_agent.md](./05_ac_validator_agent.md) | Create ac-validator agent — final coverage gate before commit | 2 — agents | `[ ]` |
| 06 | [06_ticket_supervisor_wiring.md](./06_ticket_supervisor_wiring.md) | Wire routing by complexity into pipeline | 3 — wiring | `[ ]` |
| 07a | [07a_signoff_ac_recipe.md](./07a_signoff_ac_recipe.md) | AC-checkbox recipe in signoff skill (shared foundation) | 3 — wiring | `[ ]` |
| 07b | [07b_coder_contract_mode.md](./07b_coder_contract_mode.md) | Contract-aware mode for coder agents (python, frontend, sql) | 3 — wiring | `[ ]` |
| 07c | [07c_doc_agent_contract_mode.md](./07c_doc_agent_contract_mode.md) | Contract-aware mode for doc-writing agents | 3 — wiring | `[ ]` |
| 07d | [07d_test_pr_contract_mode.md](./07d_test_pr_contract_mode.md) | Contract-aware mode for test-writer + pr-reviewer | 3 — wiring | `[ ]` |

### Rollout Strategy

**Phase 0 — Test first.** Ship `/create-ticket-v2` as a parallel command. Run it
on 3-5 real requests alongside v1. Compare AC quality. Iterate.

**Phase 1 — Foundations.** ADR, AC format changes, documentation index. These are
backward-compatible infrastructure that doesn't change agent behavior.

**Phase 2 — Agents.** The BA, IT PO, and ac-validator. These are new agents that
only activate on v2 tickets.

**Phase 3 — Wiring.** Connect everything to the ticket-supervisor pipeline. Update
coder agents to understand the new format (backward-compatible — they detect v1 vs v2
and behave accordingly).

**Promotion.** Once v2 is proven across several real tickets: rename v2 → v1,
deprecate old templates. Old tickets in-flight continue to work — coders fall back
to v1 behavior when they see no `## Agent Contracts` section.

## Risk & Safety

- Touches money? No.
- Touches data? No — modifies ticket templates and agent prompts only.
- Reversibility? Fully reversible — all changes are additive templates. Dropping
  the epic leaves the current process intact.
