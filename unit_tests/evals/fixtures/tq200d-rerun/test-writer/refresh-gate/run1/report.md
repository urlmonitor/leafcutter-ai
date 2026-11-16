Non-zero exit confirms the suite is red exactly where expected — the discriminating test fails against today's unfixed gate, and the control/boundary rows already pass since they don't depend on the fix.

## Test Writer — Completion Report

### Tests Written
| File | Directory | Framework | Status |
|---|---|---|---|
| test_refresh_gate.py | tests/ | pytest | written |

### Verification Run
- Command: `python -m pytest tests/test_refresh_gate.py -v`
- Result: red (1 failure — expected; `refresh_gate.py` still has the old `if refresh_due:` gate, not yet changed to `if refresh_due and retry_due:`)

### Three Questions (per guarding test)
| Test | Q1 smallest wrong change | Q2 can it fail? | Q3 control row | Label |
|---|---|---|---|---|
| test_refresh_blocked_when_retry_not_due | Leaving the gate as `if refresh_due:` (i.e. not applying the fix at all) | Yes — observed above: `should_refresh(True, False)` returns `True`, failing the `is False` assertion | `test_refresh_fires_when_both_due` passes for a different reason (both inputs True) and would still pass under the old code too, so it cannot mask this failure | observed |

Vacuity checklist:
- Exact value, not a one-sided bound: each assertion checks an exact boolean (`is True` / `is False`) — done.
- Control row present: `test_refresh_fires_when_both_due` (both due → True) sits alongside the negative row — done.
- New input seeded distinct from old: `retry_due` is set to both `True` and `False` across cases, distinct from each other — done.
- Collaborator call-count: not applicable — `should_refresh` is a pure function with no collaborator to count calls on.

### Wrong versions the tests now catch
- The unfixed version where `retry_due` is ignored entirely (current code: `if refresh_due:`) — caught by `test_refresh_blocked_when_retry_not_due`, which fails against it (confirmed by the run above).

### Notes
No existing tests or `conftest.py` were touched (none existed). No AC store (`docs/acceptance-criteria/`) was found in the repo, but `TQ-9201` was supplied directly in the task, so it was used as-is for the `# covers:` tags rather than falling back to `UNKNOWN`.