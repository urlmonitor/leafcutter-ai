---
title: "EPIC-ErrorHandlingEnforcement — Exception-handling policy, commit-guardian AST hook, and Ruff pre-commit rules"
date: "2026-06-01"
time: "12:00"
type: epic_completion
components:
  - build_pipeline
  - config_loader
  - commit_guardian
summary: "Three-layer exception-handling enforcement landed: Ruff rules (E722, BLE001, TRY) in pre-commit, a new check_exception_handling.py AST hook in commit-guardian, and an explicit four-rule Error Handling Policy in CLAUDE.md and the python-coder agent template."
description: "10 commits across the EPIC-ErrorHandlingEnforcement branch (PR #27). Key changes: check_exception_handling.py added to leafcutter/scripts/commit_guardian/ with AST-based detection of bare except, blind except Exception, and silently-swallowed exceptions; hook registered in commit_guardian.json and settings.json/skills_config; Error Handling Policy section (4 rules: wrap external I/O, never bare except, never silently swallow, no try/except on pure functions) added to CLAUDE.md and templates/agents/python-coder.md with Ruff rule ID references (E722, BLE001, TRY). All three layers are portable — they install correctly into any target project via build.py. 3 sub-tickets completed: 01 (Ruff pre-commit rules), 02 (commit-guardian hook), 03 (CLAUDE.md policy)."
epic: "EPIC-ErrorHandlingEnforcement"
adrs: []
commits:
  - 624f53b
  - c31485a
  - bab5de3
  - 9c9e928
  - e23c781
  - f256583
  - 376c2b2
  - 6dae6b1
  - 2c31873
  - 89a220e
breaking: false
migration_steps: []
---

## Entry

EPIC-ErrorHandlingEnforcement introduces layered, mechanical enforcement of exception-handling discipline across all Python code in the leafcutter project and any project it is installed into.

### What was delivered

**Ticket 01 — Ruff pre-commit rules**

Ruff rules E722 (bare except), BLE001 (blind except Exception), and the TRY family (silently-swallowed exceptions) were enabled in the project pre-commit configuration. These rules block commits that contain the most common exception-handling anti-patterns before a human or agent review step.

**Ticket 02 — commit-guardian AST hook**

`check_exception_handling.py` was added to `leafcutter/scripts/commit_guardian/`. The hook uses Python's `ast` module to walk staged `.py` files and detect:
- `except:` (no exception type bound — E722 class)
- `except Exception:` without re-raise or logging (BLE001 class)
- `except` blocks with empty bodies or flag-only assignments

The hook is registered in `commit_guardian.json` and in `settings.json` / `skills_config` so it appears in both the commit-guardian pipeline and in agent-visible tool listings.

**Ticket 03 — Error Handling Policy in CLAUDE.md and python-coder template**

A `## Error Handling Policy` section was added to `CLAUDE.md` (the compiled artifact installed into target projects) and to `templates/agents/python-coder.md`. The section contains four explicit rules with Ruff rule ID references:

1. External I/O must be wrapped in `try/except <SpecificExceptionType>`.
2. Never bare `except:` — Ruff E722 will block the commit.
3. Never silently swallow — every `except` block must log (WARNING+) or re-raise.
4. No try/except on pure internal functions — let exceptions propagate to the I/O boundary.

The policy primes contributors at session start, reducing the frequency of violations before Ruff or the AST hook fires.

### Portability

All three layers install correctly via `build.py` into any target project. No target-project-specific configuration is required beyond the standard leafcutter install.

### Breaking changes

None. Existing committed code that already passes Ruff E722/BLE001/TRY is unaffected. The AST hook only runs on staged files at commit time.
