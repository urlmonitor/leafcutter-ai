---
title: "Remediate the phantom-done acceptance criteria found by the 2026-08-25 known-issues triage"
status: todo
components:
  - build_orchestration
  - build_pipeline
  - testing_quality
created: 2026-08-25
depends_on: []
priority: high
requires_diagram: false
requires_adr: null
change_target: code
risk_surface: contract_boundary
roadmap_phase: phase_1
advances_current_outcome: true
tags:
  - phantom-done
  - triage-handover
  - known-issues
---

# Remediate the phantom-done acceptance criteria found by the 2026-08-25 known-issues triage

## Actor / Goal

In order to trust that a `done` acceptance criterion means the thing it claims,
we need the criteria falsified by the 2026-08-25 triage either satisfied or
honestly reworded, so that the store stops asserting properties the code does
not have.

## Context

This ticket is a **handover, not a work order**. It was raised from outside the
`build-orchestration` work queue by a read-only triage of all 65 entries across
five `docs/known-issues/` registers. The component owner should re-scope, split,
or reject any part of it — nothing here was written by someone holding the
context that produced these ACs.

Nothing in this ticket is new behaviour. Every item references an acceptance
criterion that **already exists and is already approved**; the work is making
each record true, either by building what it says or by narrowing it to what was
actually delivered. Per `CLAUDE.md` new work goes through `/plan-feature` first —
that rule is not being bypassed here, because no new criteria are proposed.

Linked from `KI-BO-025` in `docs/known-issues/build-orchestration.md` and
`KI-ACD-013` in `docs/known-issues/ac-driven-dev.md`.

**Two entries were already handled before this ticket was written.** `BO-2400f-10`
and `BO-2400c-1-iii` moved from `done` to `in_progress` while the triage was
running, so they are correctly classified and are excluded here. Re-check the
others the same way before starting — this register moves fast.

## The finding that matters more than the individual records

Three of the falsified ACs are held up by **presence-only assertions over
JavaScript source text**. `BO-2400f-10`'s entire covering evidence was
`self.assertIn("release", content)` at
`unit_tests/workflows/test_fast_lane_ship_structure.py:289` — which passes while
all eleven release dispatches go to an agent that refuses the role. Its
behavioural tests call `release_claim` directly, so the function works and its
caller is dead.

`BP-1100b-5` (`work_status: todo`) already specifies the guard that would catch
this, and its scanned-source globs already include
`templates/workflows-js/**/*.js`. **Building `BP-1100b-5` and running it
retroactively over existing stock is the highest-leverage item here** — it would
have caught three of the six. Consider doing that before the individual repairs,
so the repairs land against a gate that can hold them.

`KI-BO-008` files this same mechanism in its own right, so it is not a cosmetic
entry.

## Acceptance Criteria

- [ ] AC-1: `BP-600e-2` is either satisfied — the divergence gate pauses and waits for confirmation rather than returning `status: 'blocked'` — or its criteria are narrowed to the halt-without-resume behaviour that was actually built, with the `it_requirements` that demand a pause amended in the same change
- [ ] AC-2: `BO-2400f-3` is either satisfied — the worktree reconnect path cuts from `origin/main` rather than reusing the existing branch tip — or its "never from stale local main" clause is narrowed to the create path it actually covers
- [ ] AC-3: `BO-2400e-4` is either satisfied for CRLF records — read and write both pass `newline=""` — or its "every other part of the record keeps its original text" clause is scoped to the LF population it was closed against
- [ ] AC-4: `BO-2200c-5` is satisfied: the ticket generator emits the pipe-delimited contract line `documentation-verifier` parses, verified by a test that runs the generator and then runs the verifier's Step 2 parser over the output
- [ ] AC-5: `BO-202` is either satisfied for L3 ACs and for tags under `unit_tests/`, or its `covered_by` clause gains the L2-only and directory qualifiers that `BO-201` already carries
- [ ] AC-6: `BO-2300a-1` and `BO-2300a-2` are satisfied together: a gate answered by an agent's refusal pauses rather than cancelling, and a cancelled run returns `status: "cancelled"` rather than `"ok"`
- [ ] AC-7: `BO-1500f-1` is satisfied: a failed read of the agent registry is distinguishable from a genuine permission denial, and `worktree-agent` (`permits_shell: true`) is dispatched
- [ ] AC-8: No AC in this list is closed on a test that asserts only the presence of a string in source text

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |
| AC-6 | | | |
| AC-7 | | | |
| AC-8 | | | |

## Falsified criteria, with the evidence

Each was verified against the code at `origin/main` on 2026-08-25. Line numbers
were re-checked after PR #541 shifted `fast_lane.py`.

### `BP-600e-2` — "waits for user confirmation"

`templates/workflows-js/quick-fix.js:568-569` compares the **first whitespace
token** of the prose root cause against pytest output:

```js
const divergenceCheck = failureMsg.length > 0 &&
  !failureMsg.toLowerCase().includes(root_cause.toLowerCase().split(' ')[0])
```

`:571-581` then `return`s `{ status: 'blocked' }`. There is no confirmation
parameter, no persisted state, no wait. The AC's own `it_requirements` say "must
**pause** … not halt permanently" and "should use **LLM-based comparison**".
All four covering tests at `unit_tests/.../test_quick_fix_workflow.py:877-915`
are source greps.

### `BO-2400f-3` — "cut from the latest origin/main (never from stale local main)"

`templates/scripts/setup_ticket_worktree.py`, `_create_fastlane_worktree`: when
the branch already exists, `git worktree add <path> <branch>` runs with **no
start point** (`:519-529`). Only the `else` branch cuts from `origin/main`. The
sole origin/main test stubs `_branch_exists` to return empty, so the reconnect
path is never exercised by any of the seven `# covers: BO-2400f-3` tests.

### `BO-2400e-4` — "every other part of the record keeps its original text"

`scripts/build_orchestration/fast_lane.py`: the read at `:266` and the write at
`:186` are both default-newline, so a CRLF record is rewritten LF end-to-end —
154 changed lines from one `work_status` flip. Current exposure is **zero** (no
CRLF records in the store today) and the AC's own notes record the hole, so this
is the least urgent of the six. Listed for completeness.

### `BO-2200c-5` — "both agents draw from one block … in lockstep"

Producer, `scripts/ac_store/generate_ticket_from_ac.py:2064`:

```python
lines.append(f"- [ ] AC-{i}: [{genre}] {doc_path} — {constraint}")
```

Consumer, `templates/agents/documentation-verifier.md:144-157`: "parse the
target documentation path as the second **pipe-delimited** field … If a line has
no pipe separators … emit `(status: blocker)`".

The verifier's format spec *is* the "second, separately maintained list" the
criterion forbids. Four real generated tickets recorded the blocker, all dated
`2026-08-11` — a week before `KI-ACD-002`'s `First seen`, and its `Occurrences: 1`
undercounts by at least four.

### `BO-202` — "populates `covered_by` with test file paths from the diff"

`templates/agents/ac-fulfillment-gate.md:227-229` scopes the auto-fix to L2 ACs
only, and `:232` greps `tests/` alone. The criterion carries no L2-only qualifier
and no directory qualifier. `BO-201` is **not** a phantom here — its equivalent
clause explicitly exempts L3.

### `BO-2300a-1` + `BO-2300a-2` — one bug, two falsified ACs

Both live in `templates/workflows-js/plan-feature.js:2057-2097`. `resolveGate`
(`:1577`) accepts any object with a string `action` as a decision, so an agent's
refusal shaped as `{"action":"cancel", ...}` is read as the user choosing cancel;
`pauseAtGate` (`:1582`) is reached only when the reply is null. Then `:2089-2097`
returns `status: "ok"` on the cancel path, against a constraint that says
"**never 'ok'**".

Both went `done` in the same ticket. Fixing the gate-answerer without the return
status leaves `BO-2300a-2` false; fixing the status without the answerer leaves
`BO-2300a-1` false.

### `BO-1500f-1` — "dispatches it to an agent whose registered charter permits shell"

`config/agent_registry.json:1364-1368` gives `worktree-agent`
`"permits_shell": true`, yet the run halts before dispatch.
`plan-feature.js:1747-1773` `cat`s a **cwd-relative**
`.leafcutter/config/agent_registry.json` through an agent; in a worktree that
path does not exist, and a read failure, a parse failure and an API error all
collapse into "this agent is not permitted".

This sits downstream of `BO-1500e-2` (`in_progress`), whose `it_requirements`
already name the fix — resolve the repo root from the git toplevel of the
invocation cwd.

## Implementation Tasks

- [ ] Re-verify each AC is still `done` and still falsified before starting; two moved during the triage
- [ ] Decide per AC: satisfy, or narrow the criteria with an `amended_by` entry recording why
- [ ] Consider building `BP-1100b-5` first so the repairs land against a gate that can hold them
- [ ] Fix `BO-2300a-1` and `BO-2300a-2` in one change
- [ ] Replace the presence-only tests that held these ACs up, starting with `test_fast_lane_ship_structure.py:289`
- [ ] Update the corresponding known-issues entries when each lands

## Out of Scope

- `BO-2400f-10` and `BO-2400c-1-iii` — already `in_progress`
- `KI-BO-023` (`ValueError` raised at `fast_lane.py:281`, every handler in the release path catches `OSError`) — a real live defect, but it falsifies `BO-2400f-10`, which is already being worked
- Authoring any new acceptance criteria. Where a gap was found rather than a phantom, it is recorded in the registers and handled separately

## Risk & Safety

- Touches money? No.
- Touches data? `BO-2400e-4` concerns rewriting acceptance-criterion records in place; a regression there corrupts the store. Current CRLF exposure is zero, which makes it safe to fix and dangerous to fix carelessly.
- Reversibility? All changes are code plus AC-record edits, reversible by revert. Narrowing a criterion is a governance change and needs an `amended_by` entry so it is not mistaken for a silent relaxation.

## Comments

_(Append-only log — leave blank when authoring.)_
