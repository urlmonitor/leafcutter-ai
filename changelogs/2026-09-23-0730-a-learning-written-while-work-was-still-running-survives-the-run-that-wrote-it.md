---
title: "A learning written while work was still running survives the run that wrote it"
date: "2026-09-23"
time: "07:30"
type: manual
components:
  - knowledge_system
  - build_orchestration
summary: "Four criteria close the in-flight half of the knowledge loop: a learning captured while a unit of work is still running is readable after it finishes, one that could not be published is said out loud instead of swallowed, one emitted too late for this run is counted and named rather than dropped, and two units of work finishing at the same moment do not both write the same learning."
description: "New scripts/knowledge/completion_routing.py (the routing decision) and completion_routing_state.py (the per-run state it arbitrates on), with four test suites and a shared fixture module under unit_tests/workflows/. Salvaged by hand from three fast-lane runs that each died on a network error after the build loop had already produced working code; the coupling between tests and modules was re-proved from scratch rather than inherited from the lane's own gates."
commits:
  - f9628120
breaking: false
---

## Entry

### What the four criteria cover

| criterion | what it guarantees |
|---|---|
| `INF-700a-5` | a learning written mid-flight is still readable once the work finishes |
| `INF-700a-5-i` | one that could not be published is said out loud, not swallowed |
| `INF-700a-5-ii` | one emitted too late for this run is counted and named, not dropped |
| `INF-700a-5-iii` | two units of work finishing together do not both write the same learning |

The last is the interesting one: it needs arbitration between concurrent runs,
which is why the state lives in its own module rather than inside the routing
decision.

### Salvaged, not rebuilt

Three fast-lane runs attempted this. Each died on a network error — twice
`EAI_AGAIN`, once `ECONNRESET` — and each died *after* the build loop had
produced working code: once at the context-bundle step, once at review. The lane
released its criteria back to `todo` cleanly every time, so the store was never
wrong. But the code sat uncommitted in the lane's worktree, and a fourth attempt
would have rebuilt from scratch what was already correct.

### The lane's own gates were not treated as evidence

Its red/green gates had passed before it died. A gate nobody watched run is not
proof, so the coupling was re-established directly:

| step | result |
|---|---|
| four suites, module present | 10 passed |
| `completion_routing.py` moved aside | **10 failed** |
| restored, `diff -q` against the backup | identical |
| whole `unit_tests/workflows/` suite | 782 passed, 71 subtests |

Every run under `AC_ENFORCE_STRICT=1`. Without it `pytest_ac_enforcement`
downgrades a failure covering a not-yet-`done` criterion to `xfail` — and all
four of these were `todo` until the commit, so that honest red would have
presented as green.

The revert step copied the module to a path outside the repository rather than
using `git stash`. The stash stack is shared by every session in this workspace,
and popping the top entry is how a concurrent session's uncommitted work was
destroyed once before.

### Seven files deliberately left behind

The worktree also carried 118 added lines across seven `docs/agents/cards/*.md`
files. None of it belongs to this feature — the cards are build output
regenerated from the criteria store, and what they had picked up was *other*
epics' records: `ACD-1200b-5-ii`, the `BO-1800f` family, `BO-2400c-1-ix`,
`KM-KGS-100a-3-viii`. Staging them would have filed another epic's listings
under this feature's name. Reverted.

### Store reconciled in the same commit

All four flipped to `done` with their real covering tests and implementing
files. `INF-700a-5` is a composite: its `covered_by` is its three children and
its proof derives from them, so it carries `implemented_by` but no direct covers
tag. The parent `INF-700a` was staged alongside per the store rule; its
`covered_by` already listed `-5`, so nothing there needed changing.

`validate_ac_schema.py` on the infrastructure subtree: `OK: all 281 valid`.
`ruff`: clean.
