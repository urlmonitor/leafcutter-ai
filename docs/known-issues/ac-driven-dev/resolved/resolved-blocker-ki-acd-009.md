---
title: "KI-ACD-009 — `/plan-feature` halts before any authoring agent and blames a registry field that is correct"
description: "KI-ACD-009 — `/plan-feature` halts before any authoring agent and blames a registry field that is correct. Partially fixed: the round-trip-removal site landed 2026-09-07 and the last sibling's coverage was migrated 2026-09-21, but the owning AC is still work_status: todo so the entry stays open."
type: reference
category: reference
status: active
created: '2026-08-19'
last_updated: '2026-09-23'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/known-issues/README.md
---

# KI-ACD-009 — `/plan-feature` halts before any authoring agent and blames a registry field that is correct

> One known issue, split out of `docs/known-issues/ac-driven-dev.md` on
> 2026-09-14. Index: [ac-driven-dev.md](../../ac-driven-dev.md).
> Filename severity is the three-level index bucket (`blocker`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** blocker
- **Status:** **open — partial.** The surface defect this entry's cause 2 names is gone: the
  `resolve-workspace-setup-permission` dispatch no longer exists (2026-09-07, `ACD-2100b-5`).
  What keeps the entry open is the closure condition the 2026-09-07 section set for itself —
  the sibling coverage that stubbed the retired dispatch had to be re-pointed *and* that
  remediation recorded in the store. The last sibling's tests were migrated on 2026-09-21 and
  pass, but its owning AC (`BO-1500f-1`) is still `work_status: todo`. See the two updates
  below; read them before quoting this line, which has been self-contradictory in the past.
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-19
- **Where:** `templates/workflows-js/plan-feature.js:1745-1790` — the `resolve-workspace-setup-permission` step and the `permitsShell` fail-closed branch

**Symptom.** Every run halts with:

> Workspace-setup step 'worktree-setup' is configured to dispatch to agent
> 'worktree-agent', whose registered charter does not permit running repository/shell
> commands. … Fix the workspace_setup_agent configuration or
> `config/agent_registry.json`'s `permits_shell` field for that agent.

**The message is false.** `worktree-agent` has `permits_shell: true`
(`config/agent_registry.json:1368`). Following the remedy leads an operator to a field
that is already correct, and there is nothing there to fix.

**Root cause — a lookup failure rendered as a permissions verdict.** The step reads the
registry by dispatching a `status-checker` agent to `cat` it, then:

```js
const match = entries.find((e) => e && e.id === workspaceSetupAgentId);
permitsShell = !!(match && match.permits_shell === true);
```

`permitsShell` is `false` for *four different reasons* — agent dispatch failed, output
unparseable, file unreadable, or the id genuinely absent — and only the last is a
permissions problem. All four print the permissions message. Failing closed is right;
asserting a specific false cause is not.

**Two independent causes were both present in the observed run**, which is why this is a
blocker rather than a flake:

1. **The path does not exist.** The deployed workflow reads
   `.leafcutter/config/agent_registry.json` (relative). Verified 2026-08-19: that file
   exists at the **workspace root** (`<workspace>/.leafcutter/config/`) but **not** in a
   worktree's `.leafcutter/`. So the `cat` fails for any run whose cwd is a worktree —
   deterministically, not intermittently. Same self-hosting-layout class as KI-ACD-004,
   different resolution site.
2. **The dispatch itself errored.** The run recorded
   `[resolve-workspace-setup-permission] failed: API Error: Connection lost
   mid-response`, so `permissionResult` was `null` and the parse could not have
   succeeded regardless.

Either alone produces the halt. Because a transient API error is indistinguishable in
the output from a real mis-assignment, a reader cannot tell a retryable failure from a
configuration one.

**Evidence.** Run `wf_359683cc-51a`, 2026-08-19, from
`worktrees/safety-security`. 3 agents dispatched, 2 completed, 1 errored; halted before
triage and before any authoring agent, so zero ACs were produced.

```
$ ls <worktree>/.leafcutter/config/agent_registry.json
ls: cannot access ...: No such file or directory
$ find <workspace> -name agent_registry.json -not -path '*/worktrees/*'
<workspace>/leafcutter-ai/config/agent_registry.json
<workspace>/.leafcutter/config/agent_registry.json
```

**Fix direction.** Three separable changes:

- **Distinguish the four outcomes.** Report `could not read the registry at <path>`,
  `could not parse it`, `agent <id> not found in it`, and `agent <id> has
  permits_shell: false` as different messages. Keep failing closed — the objection is to
  the diagnosis, not the caution. This is the same "green means checked" distinction
  `GE-120` draws, inverted: a check that could not run must not report a specific verdict
  about what it did not see.
- **Resolve the registry path, do not hardcode a relative one.** Use the same root
  resolution the guardian hooks use, so the read works from a worktree as well as the
  workspace root.
- **Do not gate startup on a live agent dispatch to read a static local file.**
  Routing it through a `status-checker` adds an API round-trip whose failure mode is a
  false halt. **Correction (recorded 2026-09-16):** this bullet used to say the workflow
  runtime can read the file directly. It cannot: the E2 engine gives a workflow body no
  filesystem or subprocess primitive (`docs/reference/workflow-authoring-contract.md` §1).
  `ACD-2100b-5` (`e4ee392d`) resolved it by moving the read into a pre-flight script the
  plan-feature skill runs before the workflow starts, passing the verdict in through `args`.

**Why it matters beyond the message.** `/plan-feature` is the mandated entry point for
all new work (`CLAUDE.md`, "New Work Goes Through ACs"). While this holds, that path is
closed from any worktree, and the only way to author ACs is to dispatch the PO/BA/IT-PO
agents by hand — which skips the triage, the gates, and the staged-commit invariant the
workflow exists to enforce.

**Fix landed 2026-09-07 (`ACD-2100b-5`).** All three "Fix direction" bullets above are
addressed by removing the round-trip entirely rather than by improving its failure
reporting:

- **Cause 2 (`API Error: Connection lost mid-response`) can no longer occur for this
  check.** There is no `resolve-workspace-setup-permission` agent dispatch left to fail.
  The startup check is now a local read performed by `/plan-feature`'s own pre-flight —
  `scripts/worktree/check_workspace_setup_permission.py` — invoked from §WSP
  (`templates/skills/plan-feature/SKILL.md`) BEFORE the workflow is invoked, not by a
  dispatch the workflow body makes. An operator who previously saw this message as a
  transport error now knows it is not this check: the E2 engine (ADR-030) contextifies
  the workflow body with no filesystem primitive at all, so the workflow physically could
  not have made this read itself, and no longer tries to reach it through an agent
  round-trip either. The verdict crosses from the pre-flight into
  `templates/workflows-js/plan-feature.js` through `args.workspace_setup_permission`,
  the only injected global that carries caller-supplied data.
- **"Distinguish the four outcomes" is implemented.** The script's verdict carries an
  `outcome` field distinguishing `granted`, `read_failure`, `parse_failure`,
  `agent_not_found`, `no_entries_collection`, and `permission_denied` — the causes named
  above are now reported apart from one another rather than collapsed into one
  permissions message.
- **"Resolve the registry path, do not hardcode a relative one" is implemented.** The
  script resolves the registry the same repository-anchored way `ACD-2100a-1` /
  `ACD-2100a-3` already established for the sibling sites named in `KI-ACD-004` — so it
  reaches the project's real registry from inside a linked git worktree that holds no
  `.leafcutter/` of its own, which is cause 1 above (the missing-path failure) closed the
  same way.

Covered by `unit_tests/ac_driven_dev/test_acd_2100b_5.py` and
`unit_tests/workflows/test_acd_2100b_5.py`. **This entry is not fully closed.** Landing
the surface change makes the pre-existing dispatch-based coverage for the sibling
outcome-distinction records (`ACD-2100b-1` through `-3`, `-3-i`, `-4`, plus
`ACD-2100a-1` / `-4` and `BO-1500f-1`'s own tests, all of which stub the retired
`resolve-workspace-setup-permission` label to get past this gate) fail — tracked in
`ACD-2100b-5`'s own ticket under its `### test-writer` Implementation Tasks section.
Leave `Status` above at partial until that remediation lands and those records' coverage
is re-pointed at the script's own outcome vocabulary directly, mirroring
`unit_tests/ac_driven_dev/test_acd_2100b_5.py`.

**Update 2026-09-14 — narrower than the epic's own "all 25 tickets done" claim, still not
closed.** Re-checked directly rather than taken on the epic's say-so, now that the epic
(`EPIC-StartingNewWorkTheProperWayAlways`, ACD-2100 family) reports every one of its own
tickets done:

- The `ACD-2100b` sibling records are genuinely re-pointed and pass for real:
  `unit_tests/workflows/test_acd_2100b_1.py`, `-2.py`, `-3.py`, `-3_i.py`, and `-4.py` all
  pass (re-run 2026-09-14: 12 passed + 12 passed, no xfail masking involved — `ACD-2100b-1`
  through `-4` and `-3-i` are all `work_status: done`). `ACD-2100a-1` and `-4` are likewise
  re-pointed and green (see `KI-ACD-004`'s own 2026-09-14 update, now in
  [`resolved/resolved-blocker-ki-acd-004.md`](resolved/resolved-blocker-ki-acd-004.md)).
- **`BO-1500f-1`'s own tests were, as of 2026-09-14, the one sibling still not re-pointed,
  and a real, live failure — not a hypothetical one.** `BO-1500f-1` belongs to a different
  ticket (outside this epic's 25), so its remediation was never in this epic's scope to begin
  with. `unit_tests/workflows/test_bo_1500f_1.py` and
  `unit_tests/workflows/test_bo_1500f_1_real_registry_read.py` still asserted a
  `resolve-workspace-setup-permission` agent dispatch that no longer exists. Run under
  `AC_ENFORCE_STRICT=1` (bypassing the xfail mask that normally hides this): 4 real
  `AssertionError`s in `test_bo_1500f_1.py` alone, each on exactly the retired-dispatch
  assertion. Without `AC_ENFORCE_STRICT=1` these were silently downgraded to `xfail` and the
  suite reported green — but only because `BO-1500f-1` itself is `work_status: todo`; per the
  `pytest_ac_enforcement` masking rule, a not-done AC's failures are hidden by design, not
  because the code works. **This bullet is superseded by the 2026-09-21 update below; it is
  kept because it states the closure condition the next update measures against.**

**Update 2026-09-21 — the last sibling's coverage has landed; what remains is a store
record, not a code defect.** Re-checked by running the code, not by reading the commit:

- **The migration is real.** `f3d4630b` ("test(ac-driven-dev): migrate gate mocks to the
  resume-answer protocol") rewrote both `unit_tests/workflows/test_bo_1500f_1.py` and
  `unit_tests/workflows/test_bo_1500f_1_real_registry_read.py` onto the real pause/resume
  protocol, driving the actual on-disk `check_workspace_setup_permission.py` pre-flight and
  feeding its parsed verdict through `args.workspace_setup_permission`. It also added the
  shared `unit_tests/_plan_feature_gate_harness.py`, consolidating scaffolding six files had
  each reimplemented. No production code changed.
- **Verified green, with the mask off.**
  `AC_ENFORCE_STRICT=1 python -m pytest unit_tests/workflows/test_bo_1500f_1.py unit_tests/workflows/test_bo_1500f_1_real_registry_read.py -q`
  → **8 passed**. Strict mode is the load-bearing part: under the default run these files are
  still xfail-maskable, so a plain green would not have distinguished "fixed" from "hidden".
  The four `AssertionError`s the 2026-09-14 bullet counted are gone. The three surviving
  mentions of `resolve-workspace-setup-permission` in those files are docstring prose
  explaining what the tests were migrated *away from* — they are not assertions.
- **Why this entry nevertheless stays open.** `BO-1500f-1` is still `readiness: approved`,
  `work_status: todo`; `f3d4630b` states its criteria and `work_status` were deliberately
  left untouched and the amendment was surface-only (`it_requirements`, `doc_links`, `notes`,
  `test_spec`). The 2026-09-07 closure condition above is not "the tests pass" but "those
  records' coverage is re-pointed" *and recorded as such*. Until `BO-1500f-1` is marked done
  against its migrated coverage, the store still says this remediation has not happened, the
  xfail mask remains nominally in force over both files, and closing this entry would assert
  a completion no store record backs — the precise shape of phantom-done this register
  exists to catch. **The remaining scope is one store transition, and no known code defect.**

The standing reference page for `/plan-feature`'s layout and startup-time checks now exists
at [`docs/reference/plan-feature-layout-and-startup-checks.md`](../../../reference/plan-feature-layout-and-startup-checks.md)
(planned per `ACD-2100d-4`, authored 2026-09-09). It should state this fix and cross-link
back here rather than duplicating this narrative.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M8, inverted — not a check
reporting success it did not establish, but a check reporting a *specific failure cause*
it did not establish.

**Update 2026-09-23 — closed.** The remaining scope named by the 2026-09-21 update was one
store transition, and it has now landed: `BO-1500f-1` is marked `work_status: done` via
`scripts/ac_store/mark_ac_done.py`, recording against the store the remediation that the
migrated coverage in `f3d4630b` ("test(ac-driven-dev): migrate gate mocks to the
resume-answer protocol") already established behaviorally. That commit merged to `main` in
PR #864. With the store now recording what the code and tests have shown since 2026-09-21,
this entry is closed and moved to `resolved/`.

**Third cause — a charter refusal, not an I/O failure (recorded 2026-09-16 on `acs/bo-3200f-chartered-executor` against the open entry; carried into this resolved entry when that branch merged main on 2026-09-30).** Two `/plan-feature`
reproductions on 2026-09-16 (`wf_6e6de02b-3f9`, `wf_82e1655d-e68`) halted at
`resolve-workspace-setup-permission` before any authoring agent ran, reporting that the registry
could not be read. The file was present and readable at both candidate locations (131 KB,
`.leafcutter/config/` and `config/`). The step read the registry by dispatching `status-checker`
to `cat` it, and `status-checker` (`permits_shell: false`) refused both times:

```
run 1: {"status":"failed","payload":{"blocker_summary":"out-of-scope-request: arbitrary cat command with no ticket context"}}
run 2: {"output":"","exit_code":1,"error":"out-of-scope: status-checker only executes commands within the ticket-investigation protocol... I will not run arbitrary file-read commands outside that scope."}
```

In run 2 the refusing agent put `exit_code: 1` inside its refusal, so the run reported "exit code
1, no stdout", which is indistinguishable from an unreadable file. The halt message's "lookup
failure, not a permissions verdict" wording had landed, but it could not tell a refusal from an I/O
error. That day `plan-feature.js` still dispatched about 20 shell steps to `status-checker`.

This startup dispatch is gone: `ACD-2100b-5`'s pre-flight (`e4ee392d`, on main after 2026-09-22)
reads the registry before the workflow starts. The other shell dispatches are tracked in
`KI-BO-20260927-status-checker-runs-workflow-shell-commands`. AC coverage for the refusal class:
`BO-3200g` (a refusal is reported as a refusal), `BO-3200f` (mechanical errands go to a chartered
executor), `AR-200c` (every agent states its limits).

---
