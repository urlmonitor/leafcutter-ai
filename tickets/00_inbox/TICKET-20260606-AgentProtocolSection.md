---
title: "Write Agent Protocol section in knowledge-query SKILL.md"
status: in_progress
components:
  - build_pipeline
created: 2026-06-06
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/skills/knowledge-query/SKILL.md
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  llm-expert: signed_off
ac_coverage: 0/8
ac_traceability:
  l2:
    - KM-KQS-032
    - KM-KQS-033
    - KM-KQS-034
    - KM-KQS-035
    - KM-KQS-036
    - KM-KQS-039
  l3:
    - KM-KQS-037
    - KM-KQS-038
  ac_path: docs/acceptance-criteria/knowledge-management/
---

# Write Agent Protocol section in knowledge-query SKILL.md

## Actor / Goal

In order to allow consuming agent templates to delegate shared knowledge-query
handling to a single authoritative reference, we need a self-contained
"Agent Protocol" section appended to `templates/skills/knowledge-query/SKILL.md`
so that each agent template can reference it with one line instead of repeating
seven behavioural rules inline.

## Context

Implements KM-KQS-032 through KM-KQS-039. All eight ACs target the same file
(`templates/skills/knowledge-query/SKILL.md`) and together specify the content,
structure, and voice of an "Agent Protocol" section that does not yet exist.

The section must cover seven distinct rules (invocation syntax, zero-result
handling, empty-graph handling, graceful error degradation, citation format,
deduplication warnings, and mandatory-invocation rule). KM-KQS-039 specifies
the structural requirement: the completed section must be self-contained and
positioned after the existing "Invocation" and "Error Behaviour" sections so
that it builds on previously-defined concepts.

Parallel ticket: `TICKET-20260606-WireKnowledgeQuerySkillsUsed.md` adds
`knowledge-query` to the `skills_used` frontmatter of the three v3 agent
templates. That work is independent of this ticket and can run in parallel.

Key reference: `templates/skills/knowledge-query/SKILL.md` (the file being
edited — current content ends at the "Error Behaviour" section; append after it).

## Acceptance Criteria

### KM-KQS-032 — Invocation syntax

- [ ] AC-1: The Agent Protocol section specifies two invocation patterns with
  concrete Bash examples: (a) keyword query
  `python scripts/knowledge_query.py --query <term>` where `<term>` is derived
  from the agent's current context, and (b) surface-scoped query
  `python scripts/knowledge_query.py --surface <name>`. The protocol states that
  agents MUST use the Bash tool (not Read or any other tool) and that
  `--project-root` is not required when the working directory is the project root.

### KM-KQS-033 — Zero-result and empty-graph handling

- [ ] AC-2: The Agent Protocol section distinguishes two non-error conditions:
  (a) zero results — graph has nodes but none match the query; and (b) empty
  graph — graph has zero nodes total (fresh project). The exact log message for
  zero results is:
  `"knowledge-query returned 0 nodes for '<query-term>' — proceeding with file-based context only"`.
  The exact log message for empty graph is:
  `"knowledge-query: graph contains 0 nodes (fresh project) — proceeding with file-based context only"`.
  Neither condition triggers a user-facing prompt, a retry, or a blocked status.
  The agent's output quality must not degrade (no empty or placeholder fields).

### KM-KQS-034 — Graceful error degradation

- [ ] AC-3: The Agent Protocol section covers two failure modes: (a) script not
  found, and (b) non-zero exit. For both the agent captures error output, logs a
  warning, and continues. The exact warning format is:
  `"knowledge-query failed: <error_message> — skipping graph context, proceeding with file-based reads only"`.
  The protocol states the agent MUST NOT abort, return blocked, retry, or surface
  the error to the user unless verbose output was requested.

### KM-KQS-035 — Citation and deduplication formats

- [ ] AC-4: The Agent Protocol section specifies the citation format for
  overlapping nodes: `"[<surface>] <title>"` (e.g. `"[agents] python-coder"`).
  Citations are presented at confirmation gates, not inline in output YAML.
  The deduplication warning format for overlapping ACs is:
  `"<ac-id> already specifies this behavior — skipping or creating a variant"`.
  When overlap is with a doc or ADR node, the agent adds the path to
  `doc_links` with `relationship: context`. When no overlapping nodes are found
  the agent logs
  `"knowledge-query returned no related nodes for '<query-term>' — proceeding with file-based context only"`
  and presents no deduplication warning.

### KM-KQS-036 — Mandatory-invocation rule

- [ ] AC-5: The Agent Protocol section contains an explicit mandatory-invocation
  rule: `"Agents MUST invoke knowledge-query during their knowledge-acquisition
  phase even if prior file reads appear to provide sufficient context"`. The
  rationale states that file reads cannot detect cross-component overlap,
  recently-registered agents/skills, or ACs authored in sibling components since
  the last template update. The only acceptable reason to skip is script failure
  (covered by the error-handling rules). The protocol does NOT prescribe WHEN or
  WHICH surfaces to query — those remain agent-specific.

### KM-KQS-037 — Deduplication distinguishes surface types (L3)

- [ ] AC-6: The deduplication warning applies ONLY to nodes whose surface is
  `acs` or whose id matches the AC ID pattern. The `doc_links` auto-population
  applies ONLY to `docs` or `adrs` surface nodes. Nodes from other surfaces
  (`agents`, `skills`, `hooks`) are cited for information but do not trigger
  deduplication warnings or `doc_links` additions. When a single query returns
  both an overlapping AC and an overlapping doc, the agent presents BOTH the
  deduplication warning AND adds the doc to `doc_links` in the same confirmation
  gate output.

### KM-KQS-038 — Error message distinguishes failure modes (L3)

- [ ] AC-7: When the script is not found, the warning message uses the literal
  text `"script not found"` as the `<error_message>` portion. When the script
  exits non-zero, the agent's actual output is used as `<error_message>`. The
  protocol makes clear that the consuming agent can distinguish these two modes
  by the Bash tool output format, but the degradation path is identical.

### KM-KQS-039 — Self-contained structure

- [ ] AC-8: The Agent Protocol section is self-contained: an agent template can
  reference it with a single line such as "Load the knowledge-query skill and
  follow its Agent Protocol section" without repeating any of the seven rules
  inline. The section clearly delineates shared handling logic (what the protocol
  prescribes) from agent-specific concerns (which surfaces to query, when to
  query, what to do with results). The section is positioned after the existing
  "Invocation" and "Error Behaviour" sections in `SKILL.md`. The section uses
  second-person imperative voice ("You MUST...", "You MUST NOT...") throughout.

## AC Coverage

| AC   | Test | Implementation | Validated |
|------|------|----------------|-----------|
| AC-1 | | KM-KQS-032: invocation patterns + Bash requirement | |
| AC-2 | | KM-KQS-033: zero-result + empty-graph log messages | |
| AC-3 | | KM-KQS-034: failure-mode warning format | |
| AC-4 | | KM-KQS-035: citation + deduplication formats | |
| AC-5 | | KM-KQS-036: mandatory-invocation rule + rationale | |
| AC-6 | | KM-KQS-037: surface-type deduplication distinction | |
| AC-7 | | KM-KQS-038: script-not-found vs non-zero-exit message | |
| AC-8 | | KM-KQS-039: self-contained structure + placement + voice | |

## AC Traceability

| AC ID       | Level | Title | Agent |
|-------------|-------|-------|-------|
| KM-KQS-032  | L2 | Agent Protocol specifies standard invocation syntax | llm-expert |
| KM-KQS-033  | L2 | Agent Protocol specifies zero-result and empty-graph handling | llm-expert |
| KM-KQS-034  | L2 | Agent Protocol specifies graceful degradation when script fails | llm-expert |
| KM-KQS-035  | L2 | Agent Protocol specifies citation and deduplication formats | llm-expert |
| KM-KQS-036  | L2 | Agent Protocol specifies mandatory-invocation rule | llm-expert |
| KM-KQS-037  | L3 | Deduplication warning distinguishes AC overlap from doc/skill overlap | llm-expert |
| KM-KQS-038  | L3 | Error message distinguishes script-not-found from non-zero-exit | llm-expert |
| KM-KQS-039  | L2 | Agent Protocol section is structured for single-line reference | llm-expert |

AC files: `docs/acceptance-criteria/knowledge-management/KM-KQS-032.yaml` through `KM-KQS-039.yaml`

## Sign-offs

- [x] llm-expert — 2026-06-06 10:00
- [x] pr-reviewer — 2026-06-06 10:15
- [x] commit — 2026-06-06 10:30
- [ ] pull-request

## Comments

### 2026-06-06 10:00 — llm-expert (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  template_written: true
  prompt_quality_checklist_passed: true
  convention_violations_resolved: true
Appended self-contained "Agent Protocol" section to `templates/skills/knowledge-query/SKILL.md` after the existing "Error Behaviour" section. Section covers all 8 ACs (KM-KQS-032 through KM-KQS-039): invocation syntax with Bash-only rule, zero-result and empty-graph handling with exact log messages, graceful error degradation with exact warning format, citation and surface-type deduplication routing, mandatory-invocation rule with rationale (no WHEN/WHICH prescribed), failure mode distinction (script-not-found vs non-zero-exit), and self-contained structure in second-person imperative voice.

### 2026-06-06 10:15 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-05_37f9b334
completion_manifest:
  template_written: true
  prompt_quality_checklist_passed: true
  convention_violations_resolved: true
Reviewed diff (+135 lines, 1 file). All 8 ACs verified: invocation syntax (AC-1), zero-result/empty-graph log messages (AC-2), graceful degradation format (AC-3), citation+dedup surface routing (AC-4), mandatory-invocation rule without WHEN/WHICH (AC-5), surface-type distinction (AC-6), failure mode distinction (AC-7), self-contained imperative voice structure (AC-8). No high-confidence findings. Escalation: not escalated (medium count 0).

### 2026-06-06 10:30 — commit (status: ok)
feedback-id: fb_2026-06-05_cdf157ea
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
Committed SHA cda2533 on branch feat/agent-protocol-section. 2 files changed, 161 insertions. No hook failures. Subject: feat(knowledge-query): add Agent Protocol section to SKILL.md.

## Implementation Tasks

- [x] Read the current `templates/skills/knowledge-query/SKILL.md` to locate the end of
  the "Error Behaviour" section — the new "Agent Protocol" section inserts after it.
- [x] Draft the Agent Protocol section covering all seven rules in second-person
  imperative voice, respecting the exact log message formats from ACs 2, 3, and 4.
- [x] Verify that the mandatory-invocation rule (AC-5) explicitly omits WHEN and WHICH
  surfaces to query from the protocol body.
- [x] Verify that the self-contained check (AC-8) is satisfied: all seven rules are
  present, section uses `You MUST` / `You MUST NOT` imperative voice, and there is
  no duplication with the existing "Invocation" or "Error Behaviour" sections.
- [x] Write the amended `SKILL.md`.
- [ ] PR review: verify exact log message strings, surface-type routing (AC-6),
  and placement order in the file.

## Risk & Safety

- Touches money? No.
- Touches data? No — single Markdown file edit; no user data affected.
- Reversibility? Fully reversible — the new section is an append; reverting
  removes it without affecting existing content.
- Risk of regressions: None. The file has no automated tests; the change is
  additive prose appended after existing sections.
