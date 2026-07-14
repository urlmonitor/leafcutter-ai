---
title: "Wire precommit-probe dead helpers into run_checks + fix fail-open behaviour"
status: todo
components:
  - build_orchestration
created: 2026-07-14
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
source_ac: BO-1700g-1
ac_coverage:
  - BO-1700b-4
  - BO-1700c-1-iii
  - BO-1700d-1-i
  - BO-1700e-3
  - BO-1700f-1-ii
  - BO-1700g-1
  - BO-1700g-2
  - BO-1700g-3
  - BO-1700h-1
  - BO-1700h-3
files_touched:
  - templates/scripts/commit_guardian/verify_precommit_active.py
  - templates/agents/commit.md
  - templates/skills/building-epics/SKILL.md
  - unit_tests/commit_guardian/test_verify_precommit_active.py
agents:
  architect-review: needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 02: Wire precommit-probe dead helpers + fix fail-open

## Actor / Goal

As the worktree quality-gate probe, I want the tested helper functions to
actually run inside `run_checks()`, and the incomplete-build path to fail
**closed**, so the BO-1700 probe behaviours are real rather than dead code.

## Remediation Context (audit 2026-07-14)

**Phantom-done / opposite-behaviour.** Six helpers (`validate_hook_name`,
`validate_canary_stage`, `check_hook_freshness`, `resolve_hooks_path`,
`assert_no_allow_no_config_env`, `remove_canary_from_manifest`) are unit-tested
but **never called by `run_checks()`/check A–D** — dead code. `e-3` was
implemented as a fail-**open** `graceful_skip_if_incomplete`, the *opposite* of
its fail-closed criterion. The prompt gates in `commit.md` and
`building-epics/SKILL.md` parse `all_pass`/`results` JSON keys the probe **never
emits** (it emits `binary/config/git_hook/canary/failing_checks`) — contract
drift vs a-1. Check B does no required-hook-ID/content-hash validation; check C
ignores `core.hooksPath`.

**Do: wire the helpers into `run_checks`, flip e-3 to fail-closed, align the
prompt-gate JSON keys to what the probe emits.** Note: the existing subprocess
tests hardcode `leafcutter-ai/scripts/commit_guardian/...` — see Part C ticket
for the path-portability fix; coordinate so tests run green in the source checkout.

## Acceptance Criteria

Resolves the 10 leaf ACs in `ac_coverage` (verbatim Gherkin under the AC store
`.../BO-1700-worktree-quality-gate-guard/`). Done = each helper's behaviour is
reached from `run_checks()` and asserted by a test that names the AC.

## Test Requirements

```yaml
tests:
  - name: test_run_checks_invokes_hook_id_validation
    file: unit_tests/commit_guardian/test_verify_precommit_active.py
    covers: [BO-1700g-1, BO-1700h-1, BO-1700h-3]
    asserts: run_checks validates required hook IDs, freshness, and honours core.hooksPath.
  - name: test_incomplete_build_fails_closed
    file: unit_tests/commit_guardian/test_verify_precommit_active.py
    covers: [BO-1700e-3]
    asserts: an incomplete guardian-scripts build makes the probe fail closed, not skip.
```

## Sign-offs

- [ ] architect-review
- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
