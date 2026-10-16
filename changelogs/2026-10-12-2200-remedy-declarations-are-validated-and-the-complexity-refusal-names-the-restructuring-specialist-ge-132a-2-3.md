---
title: "Remedy declarations are validated, and a complexity refusal names the restructuring specialist (GE-132a-2, GE-132a-3)"
date: "2026-10-12"
time: "22:00"
type: manual
components: 
  - commit_guardian
  - precommit_hooks
summary: "Commit checks' remedy declarations are now checked for a known disposition and a real agent and skill, and a too-complex function is refused with 'complexity X, only Y allowed' plus the declared next step: bring in the restructuring specialist with complexity-reduction."
description: "GE-132a-2: _remedy_declaration_validity.py, run inside check-hook-parity's remedy leg, refuses a declaration whose disposition is not author-clears, mechanical-autofix or engage-specialist; an author-clears declaration that names an agent or skills; a mechanical-autofix or engage-specialist declaration that names no agent; and an unknown agent or skill, naming it. commit_guardian.json declares the platform agents (general-purpose). precommit-autofix.json follows BrainCandy's 2026-10-12 table: check-complexity is engage-specialist with restructuring-specialist; check-ac-schema, check-contract-shrinking, check-exception-handling, check-file-size, check-ticket-ac-limits, check-glossary-coverage and check-sql-complexity stay engage-specialist with their existing agents; check-secrets, check-commit-scope and check-doc-links are author-clears with no agent; the eight mechanical-autofix rules that had a null agent name general-purpose, their existing subagent_type. GE-132a-2's it_requirements are amended to this table. GE-132a-3: check_complexity.py reads its remedy from the shared declaration loader, so a refusal reads 'X has complexity N, only M allowed' followed by the declared instruction, identical for every committer, and AUTOFIX_AGENT is restructuring-specialist (omitted when no agent is declared). The python-coder fallback is removed, and main() is split (report_refusal) to stay under its own complexity ceiling."
commits: []
breaking: false
---

## Entry
