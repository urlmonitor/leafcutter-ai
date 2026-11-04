Confirmed red (non-zero exit, `AssertionError` — assertion kind) against the current code. The other three tests happen to pass under current code too, which is expected since the current implementation only diverges from the target behavior on the `refresh_due=True, retry_due=False` case.

## Test Writer — Completion Report

### Tests Written
| File | Directory | Framework | Status |
|---|---|---|---|
| test_refresh_gate.py | tests/ | unittest | written |

### Verification Run
- Command: `python -m unittest discover -s tests -t . -p "test_*.py" -v`
- Result: red (1 failure — `test_no_refresh_when_retry_not_due`, `AssertionError: True is not false`, expected since `refresh_gate.py` still implements the old `if refresh_due:` gate)

### Three Questions (per guarding test)
| Test | Q1 smallest wrong change | Q2 can it fail? | Q3 control row | Label |
|---|---|---|---|---|
| test_no_refresh_when_retry_not_due | Revert to `if refresh_due:` (ignore `retry_due`) | Yes — observed above: current code returns `True`, test expects `False` | `test_refresh_runs_when_both_due` passes for a distinct reason (both inputs true) | observed |
| test_no_refresh_when_refresh_not_due | Use `if refresh_due or retry_due:` instead of `and` | Yes — reasoned: that version would return `True` for `(False, True)`, test expects `False` | Same control row, distinct reason (only `retry_due` true here) | reasoned |
| test_no_refresh_when_neither_due | Use `if retry_due:` alone (ignore `refresh_due`) | Yes — reasoned: that version returns `False` here too (coincidentally matches), but is caught instead by `test_no_refresh_when_retry_not_due` | Control row passes on both inputs true | reasoned |

Vacuity checklist per test:
- Exact result (`True`/`False`), not a one-sided bound: done, all 4 tests.
- Control row present (`test_refresh_runs_when_both_due`): done.
- New input (`retry_due`) seeded with values distinct from `refresh_due` across the 4 cases (full truth table): done.
- Collaborator call-count: not applicable — `should_refresh` is a pure function with no collaborator to count calls on.

Wrong versions the tests now catch:
1. Reverted gate `if refresh_due:` (ignores `retry_due`) — caught by `test_no_refresh_when_retry_not_due`.
2. `if refresh_due or retry_due:` (OR instead of AND) — caught by `test_no_refresh_when_refresh_not_due`.
3. `if retry_due:` alone (ignores `refresh_due`) — caught by `test_no_refresh_when_refresh_not_due` (and partially by `test_no_refresh_when_retry_not_due`, which that version would still fail since it'd return `False` there as well — actually re-checking: `if retry_due` with `refresh_due=True, retry_due=False` returns `False`, which matches expected, so this wrong version is only caught by the `(False, True)` case).

### Notes
No `.claude/skills_config.json`, AC store, or ticket context exists in this sandbox, so I used the AC id (`TQ-9201`) given directly in the request and created `tests/` + `tests/__init__.py` as a new test directory (unittest discovery requires it importable). No `ticket_path` was supplied, so no sign-off/completion-manifest was performed.