---
title: "EPIC: Error Handling Enforcement"
type: epic
status: done
change_target: pipeline
risk_surface: internal
components:
  - build_pipeline
  - config_loader
created: 2026-05-31
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
---

# EPIC: Error Handling Enforcement

Enforce consistent, principled exception-handling discipline across the
leafcutter project through three complementary layers: static analysis in
pre-commit, immediate agent feedback via a Claude Code hook, and explicit
policy in CLAUDE.md and coder skill templates. All three layers must be
portable so they work correctly when leafcutter is installed into any target
project.

## Background

Today nothing prevents bare `except:`, blind `except Exception:`, or silently
swallowed exceptions from landing in committed code. Agent-authored Python
files have shown this pattern repeatedly. The fix needs to be:

1. **Mechanical** — caught by automation before any human review.
2. **Immediate** — agents see the violation the moment they write the file.
3. **Declarative** — new contributors (human or AI) read the rule before
   writing their first line of code.

The three-layer approach covers all surfaces: committed code, mid-session agent
edits, and upfront behavioural priming.

## Success Criteria

- `ruff check` with E722, BLE001, and TRY-family rules returns zero violations
  on the entire `leafcutter-ai/` tree at the commit gate.
- Any bare `except` or blind `except Exception` written via an Edit/Write tool
  call triggers a Claude Code PostToolUse hook message within the same turn.
- `CLAUDE.md` and the relevant coder skill templates contain an explicit
  error-handling policy section that unambiguously defines: "wrap all external
  I/O in try/except with specific exception types; never swallow silently; no
  try/except on pure internal functions."

## Sub-Tickets

| # | File | Description | Status |
|---|------|-------------|--------|
| 01 | [01_ruff_precommit_exception_rules.md](./01_ruff_precommit_exception_rules.md) | Configure Ruff E722/BLE001/TRY + AST I/O boundary check in pre-commit | `[x]` |
| 02 | [02_claude_code_hook_ruff_feedback.md](./02_claude_code_hook_ruff_feedback.md) | PostToolUse Claude Code hook: run ruff on Edit/Write for immediate feedback | `[x]` |
| 03 | [03_error_handling_policy_claudemd.md](./03_error_handling_policy_claudemd.md) | Add error-handling policy to CLAUDE.md and coder skill templates | `[x]` |

## Phases

### Phase 1 — Policy (ticket 03)

Author the error-handling policy first. This becomes the normative source for
what the linters and hooks enforce. Tickets 01 and 02 reference it.

### Phase 2 — Static gate (ticket 01)

Wire the Ruff rules and optional AST boundary check into the pre-commit hook
scaffold. Depends logically on Phase 1 (policy defines the rules; hook enforces
them) but can be parallelised if the policy wording is stable.

### Phase 3 — Live feedback (ticket 02)

Add the Claude Code PostToolUse hook. Independent of tickets 01 and 03 at the
file level; parallelisable once the Ruff rule set from ticket 01 is agreed.
