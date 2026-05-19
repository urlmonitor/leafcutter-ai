---
description: "Invoke via the test-runner agent. Type /test [auto|live-trader|sql-functions|manual|all|single <path>]."
---

# /test — Test Runner

This workflow is the slash-command surface for the `test-runner` agent.

Argument hint: `[auto|live-trader|sql-functions|manual|all|single <path>]`

Default action when no argument is supplied: `auto` (infers the right suite
from `git diff`).

## What Happens

1. The `test-runner` agent inspects `git diff --name-only HEAD` and routes to
   the appropriate test suite using the routing table in its system prompt.
2. It runs the suite and returns either a one-line success summary or a
   structured failure report grouped by failure type.

## Routing Summary

| Action | Command | Notes |
|---|---|---|
| `auto` | Inferred from diff | Default |
| `live-trader` | `poetry run python -m unittest discover -s unit_tests/live_trader -t . -p "test_*.py"` | Fast; runs on pre-commit |
| `sql-functions` | `poetry run python -m pytest unit_tests/sql_functions -v` | Requires running DB on port 5403 |
| `manual` | `python -m pytest unit_tests/ -k "_MANUAL"` | Very slow; compression + long-running |
| `all` | live-trader then sql-functions | Warns about DB requirement first |
| `single <path>` | `poetry run python -m pytest <path> -v` | Tight loop for one file |

## Output Contract

- **Success**: one-line summary (count, elapsed).
- **Failure**: one record per failure — file, test name, failure type, 5-line
  stacktrace excerpt, per-test rerun command. Grouped by failure type.
  Never dumps raw stdout.

Forward `$ARGUMENTS` verbatim to the `test-runner` agent.
