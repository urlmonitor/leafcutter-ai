---
title: "Add error-handling policy to CLAUDE.md and coder skill templates"
status: todo
components:
  - build_pipeline
  - config_loader
created: 2026-05-31
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
files_touched:
  - leafcutter-ai/CLAUDE.md
  - leafcutter-ai/templates/skills/python-coder.md
  - leafcutter-ai/templates/agents/python-coder.md
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: signed_off
  adr-author: not_needed
  architecture-diagram-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  explanation-author: not_needed
  user-surface-smoker: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: needed
---

# 03: Add error-handling policy to CLAUDE.md and coder skill templates

## Actor / Goal

In order to ensure every contributor (human or AI agent) follows consistent,
explicit error-handling rules before writing their first line of code, we need
an error-handling policy section added to `CLAUDE.md` and the relevant coder
skill/agent templates, so that the rules are declared upfront rather than
discovered through linter failures.

## Context

The pre-commit hook (ticket 01) and Claude Code hook (ticket 02) enforce error
handling mechanically, but they operate after the code is written. A policy
statement in `CLAUDE.md` and coder templates primes the agent (and human) with
the rules at the start of every session, reducing the frequency of violations
in the first place.

The policy must be brief enough to be read and followed but specific enough to
leave no room for interpretation. It must be portable: `CLAUDE.md` is the
compiled output installed into any target project; the template source is
`leafcutter-ai/CLAUDE.md` (or equivalent template file if `build.py`
interpolates it).

This ticket is the normative source for what the mechanical enforcement in
tickets 01 and 02 is guarding. If the rule wording here changes, update
tickets 01 and 02 accordingly.

Related:
- ticket 01 (`01_ruff_precommit_exception_rules.md`) — Ruff rules that enforce
  this policy at commit time.
- ticket 02 (`02_claude_code_hook_ruff_feedback.md`) — live hook that
  reinforces this policy during authoring.

## Acceptance Criteria

```gherkin
Given a developer opens CLAUDE.md in any project where leafcutter is installed
When they search for "error handling"
Then they find a clearly labelled section with the four policy rules
  (wrap external I/O, never bare except, log or re-raise, no try/except on pure functions)

Given the python-coder agent template is compiled and deployed
When the agent begins a coding task
Then the compiled template includes the error-handling policy section verbatim

Given the policy section is present in CLAUDE.md
When a developer reads it
Then the section is self-contained: it names the Ruff rule IDs (E722, BLE001, TRY)
  it refers to, so readers can look them up independently
```

## Sign-offs

- [x] documentation-expert — 2026-06-01 12:00
- [x] pr-reviewer — 2026-06-01 12:05
- [x] commit — 2026-06-01 12:10
- [ ] pull-request

## Comments

### 2026-06-01 12:00 — documentation-expert (status: ok)
feedback-id: fb_2026-06-01_bb2d904c
completion_manifest:
  doc_written: true
  cross_links_added: true
  diataxis_genre_correct: true
Added `## Error Handling Policy` section (four rules with code examples and Ruff rule references E722, BLE001, TRY) to `CLAUDE.md` and `templates/agents/python-coder.md`. `templates/skills/python-coder.md` does not exist — task skipped per ticket instructions. `python scripts/build.py --validate-only` passes with no broken placeholder references.

### 2026-06-01 12:05 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-01_27eb0316
completion_manifest:
  diff_reviewed: true
  no_high_findings: true
  scope_verified: true
Reviewed 132 lines across CLAUDE.md (+83) and templates/agents/python-coder.md (+49). No high-confidence findings. All four error-handling rules present with correct Ruff rule IDs (E722, BLE001, TRY). Scope matches files_touched — no unexpected files staged. Escalation: not needed (0 medium findings, threshold > 3).

### 2026-06-01 12:10 — commit (status: ok)
feedback-id: fb_2026-06-01_2ec30ced
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
Committed SHA 624f53b "docs: add Error Handling Policy to CLAUDE.md and python-coder template". All 23 pre-commit hooks passed (secrets, ADR coverage, agent registry, feedback-id, glossary coverage, commit scope — all green). 3 files, 293 insertions.

## Implementation Tasks

### documentation-expert
- [x] Add a `## Error Handling Policy` section to
  `leafcutter-ai/CLAUDE.md` (or the template source that compiles to
  `CLAUDE.md` in target projects). The section must include:

  **Rule 1 — External I/O must be wrapped.**
  All calls to `requests.*`, `open()`, `cursor.execute()`, subprocess calls,
  and any other operation that can raise an OS/network/DB error must be
  wrapped in `try/except <SpecificExceptionType>`. Generic "external I/O"
  means any function call that crosses a process or system boundary.

  **Rule 2 — Never bare except.**
  `except:` (no exception type) is forbidden. Ruff rule E722 will block the
  commit. Always name at least one specific exception type.

  **Rule 3 — Never silently swallow.**
  Every `except` block must either (a) log the error at WARNING or higher via
  the project logger, or (b) re-raise the exception (as-is or as a new typed
  exception). An empty `except` block or one that only sets a flag without
  logging is a violation. Ruff rule BLE001 and TRY family catch common forms
  of this.

  **Rule 4 — No try/except on pure internal functions.**
  Functions that do not perform I/O, do not call external services, and do
  not mutate shared state must NOT be wrapped in try/except by default.
  Adding try/except to pure functions obscures bugs. If a pure function raises
  unexpectedly, let it propagate — the caller at the I/O boundary is
  responsible.

- [x] Add the same `## Error Handling Policy` section (verbatim or as a
  `{{skill.error_handling_policy}}` include, whichever `build.py` supports)
  to `leafcutter-ai/templates/agents/python-coder.md` under the "Constraints"
  or "Coding Standards" heading.
- [x] If a `leafcutter-ai/templates/skills/python-coder.md` skill exists,
  add the same section there.
- [x] Verify that `python scripts/build.py --validate-only` passes after the
  edits (no broken placeholder references).

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Documentation-only change; fully reversible by removing the
  section. The pre-commit hook (ticket 01) will continue to enforce the rules
  mechanically even if this policy text is removed, but without the upfront
  explanation the linter failures become harder to understand.
- Scope risk: the policy section must NOT duplicate the full Ruff documentation
  inline — it should reference rule IDs and link to `docs/` for deeper
  explanation if one is authored later.
