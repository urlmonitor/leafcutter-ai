---
ac_coverage: 0/7
advances_current_outcome: true
agents:
  architect-review: not_needed
  commit: needed
  documentation-expert: not_needed
  frontend-coder: not_needed
  pr-reviewer: needed
  pull-request: needed
  python-coder: needed
  test-runner: needed
  test-writer: needed
  user-surface-smoker: not_needed
complexity: simple
components:
  - guardrail-engine
created: '2026-07-06'
depends_on: []
files_touched:
  - templates/scripts/commit_guardian/hooks/check_ac_limits.py
  - unit_tests/commit_guardian/test_check_ac_count_limits.py
origin_agent: create-ticket-v2
out_of_scope:
  - "Hook id/script name mismatch (check-ac-tree-limits vs check_ac_limits.py) — deferred to BP-100b-11"
  - "Per-agent cap (7) enforcement on the v1-flat path; only the 20-total cap governs flat tickets"
  - "Any changes to the tree-depth hook at templates/scripts/commit_guardian/check_ac_limits.py"
priority: high
requires_adr: false
requires_diagram: false
roadmap_phase: phase_1
status: todo
title: "Fix silent skip of 20-total AC cap for v1-flat ticket format in check_ac_limits hook"
user_facing_surface: null
---

# Fix silent skip of 20-total AC cap for v1-flat ticket format in check_ac_limits hook

## Goal

`templates/scripts/commit_guardian/hooks/check_ac_limits.py` enforces a 20-total AC cap per ticket and
a 7-per-agent cap per agent block. In `_analyse_ticket`, when a ticket has no `## Agent Contracts`
section (v1 flat format), the hook currently sets `result.skipped = True` and returns — silently
bypassing all caps. A v1-flat ticket with 30 ACs is never blocked.

Fix `_analyse_ticket` so that when `## Agent Contracts` is absent, it counts all `- [ ] AC-N:` lines
across the **full ticket body** (whole-body count is more robust to heading-name variance) and applies
the 20-total cap instead of skipping. Hard-block on violation (exit 1), matching v2 behaviour. The
per-agent cap (7) is NOT applied on the v1-flat path — it requires the `### <agent>` subsection
structure.

**Multiple template copies exist on disk.** Before editing any file, the implementer must confirm which
copy `build.py` reads as its canonical source:

- `templates/scripts/commit_guardian/hooks/check_ac_limits.py` — the ticket-body AC count hook
  (contains the `_analyse_ticket` function with the bug described above)
- `templates/scripts/commit_guardian/check_ac_limits.py` — the AC tree-depth hook (different function,
  different scope — do NOT edit this one)
- `scripts/commit_guardian/check_ac_limits.py` — built output (do NOT edit; `build.py` regenerates it)

**Pre-fix required scan.** Before finalising the hard-block behaviour, the implementer must scan
`tickets/` for any v1-flat ticket currently exceeding 20 `- [ ] AC-N:` lines and add
`ac_limit_override: true` to those tickets' frontmatter so the new block does not break them. Report
the count of affected tickets in the sign-off comment.

**Verification must use direct invocation.** Because the hook id `check-ac-tree-limits` and the script
name `check_ac_limits.py` do not match (id/name cleanup deferred to BP-100b-11), the precommit wiring
may not invoke this specific hook. Verify the fix by invoking the hook directly:

```
HOOK_TEST_DIFF=/path/to/fixture-diff.txt python templates/scripts/commit_guardian/hooks/check_ac_limits.py
```

## Acceptance Criteria

- [ ] AC-1: Given a staged ticket `.md` with no `## Agent Contracts` section and more than 20 lines
  matching `^\s*-\s*\[\s*\]\s*AC-\d+:` anywhere in the body, when `_analyse_ticket` runs, then
  `result.skipped` is `False`, `result.total_ac_count` is greater than 20, `result.total_violation`
  is `True`, and the hook exits 1.

- [ ] AC-2: Given a staged v1-flat ticket with no `## Agent Contracts` section and 20 or fewer
  `- [ ] AC-N:` lines in the body, when `_analyse_ticket` runs, then `result.skipped` is `False`,
  `result.total_violation` is `False`, `result.violations` is empty, and the hook exits 0.

- [ ] AC-3: Given a staged v1-flat ticket whose body exceeds 20 flat ACs and whose frontmatter
  contains `ac_limit_override: true`, when the hook runs, then `override_active` is `True`, the
  commit is not blocked (exit 0), and a warn-only message identifying the ticket is emitted to stderr.

- [ ] AC-4: Given a staged v1-flat ticket exceeding 20 flat ACs without the override flag, when the
  hook emits the JSON violation payload to stderr, then the shape is
  `{"hook": "check_ac_limits", "fix_agent": "it-po", "violations": [{"type": "total", "count": N, "limit": 20}]}`
  with no `per_agent` violation entries, so precommit-autofix routing is unchanged.

- [ ] AC-5: Given a staged ticket containing a `## Agent Contracts` section with `### <agent>`
  subsections, when `_analyse_ticket` runs after the fix, then per-agent counts and the total are
  computed identically to pre-fix behaviour — no regression on the v2 Agent Contracts path.

- [ ] AC-6: `result.skipped = True` is set only when the ticket file cannot be read from disk
  (`OSError`) — never solely because `## Agent Contracts` is absent from the ticket body.

- [ ] AC-7: All six new unit tests in `unit_tests/commit_guardian/test_check_ac_count_limits.py`
  pass under `pytest`; `ruff check templates/scripts/commit_guardian/hooks/check_ac_limits.py`
  exits 0 with no new E722/BLE001/TRY violations.

## AC Coverage

| AC   | Test | Implementation | Validated |
|------|------|----------------|-----------|
| AC-1 |      |                |           |
| AC-2 |      |                |           |
| AC-3 |      |                |           |
| AC-4 |      |                |           |
| AC-5 |      |                |           |
| AC-6 |      |                |           |
| AC-7 |      |                |           |

## Implementation Tasks

### python-coder

- [ ] Confirm which copy of `check_ac_limits.py` is the canonical source that `build.py` reads; edit
  only that copy. (The ticket-body hook with `_analyse_ticket` lives in
  `templates/scripts/commit_guardian/hooks/check_ac_limits.py`.)
- [ ] Scan `tickets/` for any v1-flat ticket currently exceeding 20 `- [ ] AC-N:` lines and add
  `ac_limit_override: true` to those tickets' frontmatter before the hard-block behaviour is
  finalised. Report the count in the sign-off comment.
- [ ] In `_analyse_ticket`: when the Agent Contracts section is absent, count `_AC_LINE_RE` matches
  across the full ticket body (not just the AC section) and apply the 20-total cap
  (`_MAX_ACS_TOTAL`). Set `result.total_violation = True` and populate `result.total_ac_count`.
  Do NOT set `result.skipped = True` on this path.
- [ ] Ensure the `ac_limit_override: true` branch also runs the flat AC count so the override path
  correctly identifies whether the total exceeds 20 (mirrors existing v2 override path behaviour).
- [ ] Verify the fix by invoking the hook directly with a test diff fixture (not via precommit
  wiring) — see the Goal section for the invocation form.
- [ ] Run `ruff check templates/scripts/commit_guardian/hooks/check_ac_limits.py` and confirm exit 0
  with no new E722/BLE001/TRY violations.

### test-writer

- [ ] Create `unit_tests/commit_guardian/test_check_ac_count_limits.py`; load the ticket-body hook
  from `templates/scripts/commit_guardian/hooks/check_ac_limits.py` via `importlib` (same pattern as
  `test_check_ac_limits.py` uses for the tree-depth hook — see lines 31–40 of that file for the
  shim pattern).
- [ ] Confirm RED baseline for each new test before the fix is applied; record the RED baseline in
  the sign-off comment.
- [ ] Write `test_v1_flat_over_20_acs_not_skipped`: v1-flat ticket body with 21 `- [ ] AC-N:` lines
  → `skipped=False`, `total_ac_count=21`, `total_violation=True`.
- [ ] Write `test_v1_flat_within_20_acs_passes`: v1-flat ticket with exactly 20 such lines →
  `skipped=False`, `total_violation=False`, `violations=[]`.
- [ ] Write `test_oserror_sets_skipped_not_missing_contracts`: monkeypatch `Path.read_text` to raise
  `OSError` → `skipped=True`; AND assert that a successful read with no Agent Contracts does NOT
  produce `skipped=True` after the fix.
- [ ] Write `test_v1_flat_override_warns_not_blocks`: v1-flat with 21 ACs and
  `ac_limit_override: true` in frontmatter → `override_active=True`, hook exits 0.
- [ ] Write `test_json_payload_shape_v1_flat_violation`: `_build_json_payload` (or equivalent) for a
  v1-flat total violation produces `{"hook": "check_ac_limits", "fix_agent": "it-po", "violations": [{"type": "total", "count": N, "limit": 20}]}`
  with no `per_agent` entries.
- [ ] Write `test_v2_agent_contracts_path_regression`: ticket with `## Agent Contracts` and a
  `### python-coder` subsection of 3 ACs → `per_agent = {"python-coder": 3}`, `total_ac_count=3`,
  `skipped=False`, `total_violation=False`.

## Test Requirements

```yaml
test_requirements:
  rationale: >
    The fix modifies a conditional branch in _analyse_ticket; unit tests must confirm
    the v1-flat path enforces the total cap at every boundary (over-limit, at-limit,
    OSError, override active) and must assert the v2 Agent Contracts path is not
    regressed. No existing test file covers the ticket-body hook
    (templates/scripts/commit_guardian/hooks/check_ac_limits.py).
  tests:
    - name: test_v1_flat_over_20_acs_not_skipped
      description: "v1-flat ticket body with 21 AC lines is not marked skipped and total_violation is True"
      type: unit
      target_dir: unit_tests/commit_guardian/
      covers: "_analyse_ticket — v1-flat path, total cap enforcement"

    - name: test_v1_flat_within_20_acs_passes
      description: "v1-flat ticket with exactly 20 AC lines produces no violation and exits 0"
      type: unit
      target_dir: unit_tests/commit_guardian/
      covers: "_analyse_ticket — v1-flat path, within cap"

    - name: test_oserror_sets_skipped_not_missing_contracts
      description: "skipped=True occurs only on OSError; absent Agent Contracts section alone does not set skipped=True after the fix"
      type: unit
      target_dir: unit_tests/commit_guardian/
      covers: "_analyse_ticket — OSError path and skipped=True guard"

    - name: test_v1_flat_override_warns_not_blocks
      description: "v1-flat ticket with >20 ACs and ac_limit_override: true sets override_active=True and does not block"
      type: unit
      target_dir: unit_tests/commit_guardian/
      covers: "_analyse_ticket — v1-flat with override"

    - name: test_json_payload_shape_v1_flat_violation
      description: "JSON payload for a v1-flat total violation contains type:total with no per_agent violation entries"
      type: unit
      target_dir: unit_tests/commit_guardian/
      covers: "_build_json_payload — v1-flat total violation shape"

    - name: test_v2_agent_contracts_path_regression
      description: "Ticket with ## Agent Contracts section produces correct per-agent counts and total — no regression from the flat-path fallback addition"
      type: unit
      target_dir: unit_tests/commit_guardian/
      covers: "_analyse_ticket — v2 Agent Contracts path regression guard"
```

## Open Questions

- The `test_requirements` block was synthesised during refinement (test-planner output was absent from
  the BA payload) and should be reviewed by `test-writer` before driving.
- Implementer must confirm and document the canonical source template path before editing any file —
  see the Goal section for the three candidate paths.
- Pre-fix ticket scan: report the count of v1-flat tickets that required `ac_limit_override: true`
  in the sign-off comment (per the hard-block resolution from the answered open question).

## Sign-offs

- [ ] python-coder
- [ ] test-writer
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
