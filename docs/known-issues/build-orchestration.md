---
title: "Known issues — build-orchestration"
description: "Open, observed defects in the build-orchestration component: the fast-lane build loop, its gates, and the AC lifecycle transitions it performs. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-08-26
components:
  - build_orchestration
related_docs:
  - docs/architecture/components/build-orchestration.md
  - docs/how-to/fast-lane-build.md
---

# Known issues — build-orchestration

Observed defects in this component that are **not yet fixed**. This file exists so a
defect noticed in passing can be recorded in seconds, without authoring a full
acceptance criterion for something nobody has decided to build yet.

## How to use this file

**Read it before adding new capability to this component.** Fixing what is already
broken takes precedence over building more.

**Adding an issue.** Append a new `### KI-BO-YYYYMMDD-HHMM` section, using the UTC time you
filed it (`date -u "+%Y%m%d-%H%M"`). Nothing here is generated — edit it by hand. Fill in what
you actually know; an issue recorded with a thin `Evidence` line is far better than one not
recorded.

**Why datetime ids and not the next free number.** Sequential ids collide whenever two
sessions file at once, which happens constantly here. On 2026-08-26 alone: two different
defects both landed as `KI-CG-012`, a branch's `KI-BP-010`/`KI-BO-016`/`KI-BO-017` all had to
be renumbered at merge because main had independently minted the same numbers, and a
changelog ended up describing `KI-CG-012` using what became `KI-CG-013`'s text. Renumbering is
worse than it sounds — inbound references do not disambiguate, so a rename can silently
repoint a citation at the wrong defect. A UTC timestamp cannot collide and needs no lookup of
"the next free number", which is itself a read of a file another session is editing. Existing
`KI-BO-NNN` entries keep their ids; do not renumber them. This change is what `KI-BO-024`
asked for — it recorded the same defect in the convention itself, and predicted the duplicate
that then shipped to `main`.

**Hitting an existing issue.** Increment `Occurrences` and update `Last seen`. Do not
add a duplicate entry. Occurrences is an escalator, not the score — a blocker seen once
outranks an annoyance seen ten times.

**Severity** is `blocker` (work cannot land) / `high` (silent wrong behaviour) /
`medium` (real but survivable) / `low` (noise, dead code, cosmetics).

**Closing an issue.** When the fix lands, delete the section and reference the issue id
in the commit message. If it earns real work, author an AC for it and note the AC id in
`Status` — this file is a capture surface, not a replacement for the AC store.

---

### KI-BO-002 — moved to `ac-store`

Refiled 2026-08-18 as **KI-ACS-004** in
[`docs/known-issues/ac-store.md`](ac-store.md): *an AC is marked `done` with no link
to the code implementing it.* (Filed there as KI-ACS-001, renumbered to 003 and then
004 across two merges — `ac-store.md` was created independently on main and kept
gaining entries while this branch was in review.)

Found during a fast-lane run and the call site is in `fast_lane.py`, but what
`implemented_by` must contain — and what a claim of "done" has to prove — is
provenance semantics owned by `ac-store`, not by the lane that invokes it. The id is
retired here rather than reused, so the numbering gap is intentional.

---

### KI-BO-006 — `fast-lane-build.js` is deployed but orphaned

- **Severity:** low
- **Status:** **RESOLVED 2026-09-01** — the orphan is deleted; decision recorded below · AC **BO-2400c-1-v**
- **Occurrences:** 1
- **First seen:** 2026-08-14 · **Last seen:** 2026-08-18 · **Closed:** 2026-09-01
- **Where:** `templates/workflows-js/fast-lane-build.js` (deleted)

**Symptom.** Nothing invokes it. The only `Workflow("fast-lane...")` call anywhere is
`fast-lane-ship`, and `/fast-lane-build` routes there. The orphan is still built,
deployed, and maintained — it was updated alongside `fast-lane-ship` in the BO-2400a-3
amendment purely to keep it consistent.

**Evidence.** Grep for `fast-lane-build` call sites returns only the command template,
which dispatches `fast-lane-ship`.

**Fix direction.** Delete it. The blocker that previously made deletion unsafe is gone,
and the remaining work is a test migration — see below for the real size.

**Status update, 2026-08-18.** Until this date the orphan held the only production
reference to `assemble_context_bundle`, so deleting it would have silently retired the
prompt-caching layer. That is no longer true: BO-2400c-1-iii wired the layer into
`fast-lane-ship.js`, which now assembles a bundle through the module's real
`assemble-bundle` CLI once per run. The orphan holds nothing the running lane does not.

It also holds something actively wrong: its call still names the subcommand
`assemble_context_bundle`, which is not what the CLI added by BO-2400c-1-ii is called
(`assemble-bundle`). That invocation was a silent no-op before the CLI existed and is a
plain error now. It is unreachable because nothing invokes the file — which is the
point. This absorbs the former KI-BO-005, whose substance (the module had no
command-line entry point at all) is fixed and closed.

**Deleting this is a test MIGRATION, not a deletion — size it accordingly.**
`unit_tests/workflows/test_bo2400a_runner_wiring.py` (513 lines) and
`test_bo2400a_runner_structure.py` (574 lines) point at the orphan and nothing else,
and between them carry the only `# covers:` proof for **eight** criteria: BO-2400a-1,
-2, -3, -4, -5, BO-2400b-3, BO-2400c-1 and BO-2400d-1. Several are done. Deleting the
file and its tests together strips the done-proof from all eight and fails
**Proof-of-done**, a required merge check. Three architecture diagrams and
`docs/build-dataflow.json` describe the file as well.

The full plan, including the parts that must NOT be rewritten (changelogs, already-done
ACs citing the orphan as history, and the `CLAUDE.md` phantom-done lesson that names
it), is recorded in the notes of **BO-2400c-1-v**. One specific prohibition carries
over: `test_bo2400a_runner_wiring.py:401` asserts the literal string
`assemble_context_bundle` appears in the orphan. That assertion must be **deleted**, not
re-pointed at the live file — BO-2400c-1's proof now comes from the behavioural suite
in `test_bo2400c_prompt_cache_wiring.py`, and re-pointing a name-presence grep would
preserve, at a new address, exactly the test that let a dead reference read as alive.

**RESOLUTION, 2026-09-01 — the decision this entry asked for, and how it was taken.**
This entry explicitly asked for a *capability* decision: wire the prompt-caching layer
into the running lane and delete the orphan, or delete both and say plainly that prompt
caching is gone. **The first was taken.** `BO-2400c-1-iii` wired the layer into
`fast-lane-ship.js`, and the orphan has now been deleted along with
`test_bo2400a_runner_wiring.py`. No capability was retired.

**The size estimate above was wrong in both directions, and the correction is the
useful part.** It was written by reading the two test files. The real figure came from
*deleting the orphan and running the full covering-test set*, which is a different
activity and gave a different answer:

- **Overstated.** The two files do not hold the sole proof for eight criteria. Per-id
  audit: only `BO-2400a-1` and `BO-2400a-5` had sole proof there, both in
  `test_bo2400a_runner_structure.py`. `test_bo2400a_runner_wiring.py` held **no**
  criterion's sole proof and was simply deleted, as this entry's own prohibition
  anticipated.
- **Understated.** A third file was missed entirely — `test_bo2500d_gate_retirement.py`,
  whose `_FAST_LANE_PATH` pointed at the orphan and which carried sole proof for
  `BO-2500d-2` (`done`).

So the true blast radius was **three** ACs, not eight, and it included one this entry
never named.

**A path swap would not have worked, and that is why the migration was its own change.**
`fast-lane-ship.js` has ~20 non-comment `agent()` call sites against the orphan's
exactly 2, so the "exactly two agent dispatches" assertion failed outright; and the
gate-ordering assertion compared raw string positions, where a JSDoc mention of a coder
type precedes the real gate call in the live lane (measured: `python-coder` at 832,
`verify_red_baseline` at 952, while real control flow is 336 before 28512). The
assertions were rebuilt to count the unique dispatch labels and to compare
comment-stripped positions. `select_batch` does not exist in the live lane at all — it
uses `fast_lane.py select_connected`.

**Prohibitions honoured.** Nothing was kept alive by relaxing an assertion, marking it
skipped or xfailed, or re-aiming it at a file that merely contains the same string. The
`assemble_context_bundle` name-presence grep at `test_bo2400a_runner_wiring.py:401` was
**deleted with its file**, not re-pointed. The `BO-2500d-1`/`-1-i`/`-3` tests were
deliberately left pointing at the orphan's former path rather than re-aimed: they are
`in_progress`, and `BO-2500d-1` asserts the fast lane has no LLM review agent, which the
live lane deliberately contradicts by dispatching `pr-reviewer` at Phase 4.5 (PR #485).

**Absorbed and closed with it:** the former `KI-BO-005` (the module had no command-line
entry point), already noted above as fixed.

---

### KI-BO-007 — `build-feature` counts a phase as completed when the agent halted without doing it, yielding `status: ok` with no PR

- **Severity:** high
- **Status:** open — NARROWED: one root cause found and fixed (`AR-200a-1`, PR #557); the
  observable-side-effect half remains open
- **Occurrences:** 2
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-25
- **Where:** `templates/workflows-js/build-feature.js` — the per-phase result handling
  that populates `completed_phases`

**A ROOT CAUSE WAS FOUND AND FIXED, 2026-08-25 — and it was not agent sloppiness.** Run
`wf_394d2b76-014` halted at the `test-runner` phase of `TICKET-20260825-BP-900g-8`. The agent
had done all of its work — 4 target tests passed, full suite 3984 passed / 0 failed, `build.py`
exit 0 — and then could not record any of it:

```text
result_status: tests_pass_signoff_blocked_no_edit_tool
"this session only has Bash, Read, and StructuredOutput tools -- no Edit or Write tool ...
 I could not perform the atomic sign-off. No unsafe mutation was attempted."
```

`templates/agents/test-runner.md` declared `tools: Bash, Read` while carrying a mandatory
sign-off obligation, and sign-off is an *atomic write* to the ticket record. Every workaround
(`sed -i`, `python -c`, heredocs) is hard-forbidden by the global conventions. The agent had two
exits available: halt loudly, or return quietly and let the phase be counted as passed. **It
took the loud one. Other agents in that position may not.** That is this entry's symptom,
generated by a template that asked for something it could not do.

Writing the check as a rule over every template rather than a test of the reported one found
**five** such agents, not one — `test-runner`, `live-surface-tester`, `user-surface-smoker`,
`research-agent`, `worktree-agent`. `research-agent` was the widest: 18 parent agents dispatch
it. All five are fixed (three granted `Edit`, two had a bogus obligation removed), and
`unit_tests/commit_guardian/test_agent_signoff_capability.py` now derives the rule so a sixth is
reported on arrival.

**WHAT REMAINS OPEN, precisely.** The fix removes one *generator* of the symptom; it does not
implement this entry's fix direction. The `pull-request` case in the evidence below is
untouched: that agent has `Edit`, halts at its Confirmation Contract for a different reason, and
would still be recorded in `completed_phases`. Likewise the BO-2900f-1 read-back adjudication
shipped earlier catches a gate that leaves **no** sign-off, but not one that leaves a *positive*
sign-off having done nothing observable — `isPassingSignoff` reads the entry's status field and
nothing else.

So the open half is exactly the fix direction already stated: **assert completion against an
observable side effect**, not against the agent returning cleanly. For `pull-request`, that the
remote branch exists and `gh pr list --head <branch>` is non-empty.

**Symptom.** A phase agent that runs to completion but deliberately performs **no
action** is recorded in `completed_phases` exactly like one that did the work. The
`pull-request` agent is the reliable trigger: its Confirmation Contract forbids pushing
or calling `gh pr create` without an affirmative user turn, and no user turn exists
inside a workflow dispatch, so it drafts the PR, halts at the gate, and returns a
well-formed message explaining that it stopped. The workflow reads that as success.

The result is a top-level `"status": "ok"` and `"pull-request"` in `completed_phases`
for a branch that was never pushed and a PR that does not exist. The same shape applies
to any phase whose agent can legitimately decline.

**Evidence.** Run `wf_ebe75602-f98` (ticket ACD-1900b-5-i) returned
`{"status":"ok", "completed_phases":[…,"commit","pull-request"]}`. Verified against git:
`git ls-remote --heads origin ticket/TICKET-20260818-ACD-1900b-5-i` returned empty, no PR
existed, and the branch sat at `[ahead 3]` with no upstream. The journal entry for that
agent reads: *"Pre-flight complete, PR drafted, but I am holding at the mandatory
confirmation gate before pushing … No user turn is available in this dispatch to supply
the required affirmative."* The commit phase in the same run genuinely did commit, so
this is not a blanket failure — it is per-phase, and invisible without checking git.

**Related.** The same run skipped `architect-review` and `documentation-verifier` on
`cross_agent` blockers and still reported `status: ok`; skipped-on-blocker phases are
surfaced in `skipped_phases`, which is correct and legible. The defect here is narrower:
a phase in `completed_phases` that did nothing.

**Fix direction.** A phase's completion should be asserted against an observable side
effect, not against the agent returning cleanly — for `pull-request`, that the remote
branch exists and `gh pr list --head <branch>` is non-empty. Failing that, the agent's
own "I halted at the gate" outcome needs a distinct status the workflow routes on, so it
lands in `skipped_phases` (or a new `halted_phases`) rather than `completed_phases`.
Reporting `status: ok` while a required terminal phase silently did not happen is the
phantom-done pattern applied to the build loop itself.

---

### KI-BO-008 — A structural test makes code comments load-bearing

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `unit_tests/workflows/test_fast_lane_ship_structure.py` —
  `test_ac10_release_invoked_on_failure_abort_branches`

**Symptom.** The test finds the first occurrence of the substring `release` in
`fast-lane-ship.js` and asserts it sits within 2000 characters of a `return {`. Both
halves are text heuristics over source, so any **comment** containing the word
`release` — anywhere earlier in the file than the real release dispatch — fails the
test, regardless of what the code does.

**Evidence.** During the KI-BO-001 work a new comment referencing
`scripts/release/check_changelog_presence.py` moved the first `release` match far from
any return block and broke the test. The fix was to reword the comment — the
implementation was already correct. A test that can be satisfied or broken by prose is
constraining the wrong thing.

**Fix direction.** Re-author it as a behavioural assertion, like the newer suites in
`test_bo2400f_review_and_delivery_guarantee.py`: run the workflow under
`unit_tests/_workflow_engine_harness.py` with a failing phase stubbed and assert a
release dispatch is actually recorded on that path. Note this whole file is the
pre-behavioural grep-based generation; `BP-1100b-5` already exists to reject newly
added presence-only assertions, so this is the existing stock, not a new violation.
Worth doing when that file is next touched rather than as its own errand.

---

### KI-BO-009 — The harness default stub is generically positive, so a new gate silently breaks older fixtures

- **Severity:** medium
- **Status:** open
- **Occurrences:** 3
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `unit_tests/_workflow_engine_harness.py` — the default reply for an
  agent label the caller did not stub

**Symptom.** When a caller does not stub a label, the harness answers with a generic
`{status: "ok", passed: true, ...}`. Every fixture written before a new mandatory
gate exists therefore fails to stub it. Because well-built gates fail **closed** on a
reply that lacks their own schema field, the run halts early and every later
assertion in that fixture fails — with a message about the wrong phase entirely.

**Evidence.** Three times in one day, adding a gate to `fast-lane-ship.js` broke
fixtures authored before it: `fastlane-review` and `fastlane-changelog` (KI-BO-001),
then `fastlane-context-bundle` (BO-2400c-1-iii), which broke 10 tests across two
files. The repair each time is one dict entry per fixture — mechanical, but only
once you recognise the shape.

**Why it is more than churn.** The default is generically *positive*, so the cheapest
way to make the suite green again is to widen the new gate to accept `passed: true`
as a pass. That is what happened on the first occurrence: a `|| result.passed === true`
clause was added to two guards, which in production would have let a reply carrying
no verdict at all count as a clean review — the exact defect the criterion existed to
prevent. It was removed and the fixtures corrected instead. The pull toward that fix
is a property of the harness, not of the agent that reached for it, and it will recur.

**Fix direction.** Prefer making the default reply *inert* rather than positive — an
empty object, or one that carries no field any gate reads as success — so an
unstubbed gate fails closed loudly and obviously instead of tempting a guard to widen.
That is a change with blast radius across every existing fixture, so it needs its own
AC and a sweep, not a drive-by. Until then: when adding a gate to a workflow, grep
`unit_tests/workflows/` for other fixtures driving the same workflow and add the stub
to each in the same change — and never widen the gate to accept the default's shape.

---

### KI-BO-010 — `/quick-fix`'s divergence gate is a first-token substring match, and its own remedy loops

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/workflows-js/quick-fix.js:292-306` (the BP-600e-2 divergence check)

**Symptom.** After a confirmed red baseline, the workflow halts with "The test failure
suggests the root cause may differ from your diagnosis" — on diagnoses the tests
unanimously confirm. The whole check is:

```js
const divergenceCheck = failureMsg.length > 0 &&
  !failureMsg.toLowerCase().includes(root_cause.toLowerCase().split(' ')[0])
```

It takes the **first whitespace-delimited token** of a prose diagnosis and asks whether
that literal string appears in the pytest output. Any leading markdown defeats it: a
`root_cause` beginning `` `handoff` `` yields the token `` `handoff` ``, backticks
included, which never appears in test output that says `handoff`. A leading article
("The adjudication branch…" → `the`) inverts the failure the other way — `the` appears in
essentially every pytest output, so the gate silently passes regardless of whether the
diagnosis is right. It is a coin flip decided by the first word's punctuation.

**Evidence.** Observed 2026-08-18 fixing the handoff-routing defect. The red phase
produced three failures that reproduced the diagnosis precisely — `test-writer` dispatched
once instead of twice in both drivers, and an unparseable handoff target advancing to
`pr-reviewer` instead of failing closed. The gate halted anyway on the backtick mismatch.
Re-running with the identical diagnosis reworded to open with a bare `handoff` cleared it.
Nothing about the analysis changed; one word lost two backticks.

**The stated remedy does not work.** The halt message reads *"To continue, re-run
/quick-fix with the same args."* The check is a pure function of `root_cause` and the
failure text, with no confirmation flag and no persisted state, so re-running with the
same args recomputes the same verdict and halts identically. The only exits are to reword
the diagnosis until the first token happens to match, or to abandon the workflow — and the
message advises neither.

**Why this matters more than it looks.** A gate this coarse trains people to defeat it.
The reliable way past it is to open `root_cause` with a common English word, which makes
the check pass unconditionally — so the failure mode it converges on is not false halts
but a permanently green gate that never reads the diagnosis at all.

**Fix direction.** Delete it or make it real. A first-token substring match cannot assess
whether a failure corroborates a diagnosis, so it should not be shaped like a verdict — at
minimum downgrade it to an advisory `log()` that never halts. If a genuine check is wanted,
it belongs with an agent that reads the failure and the diagnosis and judges them, and it
needs a confirmation path so an operator who has looked at both can proceed. Whatever
replaces it must make its own remedy reachable.

Filed as KI-BO-008 while this work sat uncommitted; renumbered to 010 on landing, main
having published a different KI-BO-008 and a KI-BO-009 in the interim.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M8 (a check that cannot assess
correctness reporting a verdict anyway), in its fail-closed form.

---

### KI-BO-011 — A grep-only test aimed at an orphaned file kept a superseded criterion looking satisfied, hiding a direct contradiction between two `done` ACs

- **Severity:** high
- **Status:** open · the *instance* is covered by the amended **BO-2500d-1** /
  **BO-2500d-1-i** / **BO-2500d-3**; the *class* — an unreachable file serving as a
  criterion's proof — has no AC and is the reason this entry stays open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `unit_tests/workflows/test_bo2500d_gate_retirement.py` (module constant
  `_FAST_LANE_PATH`), against `templates/workflows-js/fast-lane-build.js`

**Symptom.** Two acceptance criteria assert opposite things about the same subject and
both read `work_status: done`. `BO-2500d-1` — *"Opinion-only gate agents are absent from
the fast-lane phase order ... it contains no LLM review agent"* — is contradicted by
`BO-2400f-11`, which puts a `pr-reviewer` dispatch in the fast lane at Phase 4.5, ahead
of `mark_done`. Nothing detected the collision, because `BO-2500d-1`'s entire proof is
~750 lines of string-presence assertions pointed at `fast-lane-build.js`, a file nothing
invokes. The orphan cannot acquire a `pr-reviewer` reference, so the assertions stay
green forever and the criterion reads satisfied no matter what the running lane does.

**Evidence.** `grep -n "pr-reviewer" templates/workflows-js/fast-lane-ship.js` returns
the Phase 4.5 dispatch at line ~700; the same grep against `fast-lane-build.js` returns
nothing, which is exactly what `test_bo2500d_gate_retirement.py` asserts. `BO-2500d-1`
also names the orphan in its `implemented_by`, so a deleted file is a done criterion's
recorded implementation. Three sibling criteria (`BO-2500d-1-i`, `-2`, `-3`) have their
only proof in the same file. Found while sizing `BO-2400c-1-v` (delete the orphan) — the
deletion is what forces the contradiction into the open, and it is blocked until the
`BO-2500d` family is amended.

**Why this is worse than KI-BO-008.** That one is a grep test that constrains the wrong
thing — noisy, but honest about what it looked at. This is a grep test that constrains a
*dead* thing, which is strictly worse than having no test: it does not merely fail to
detect drift, it actively reports that a superseded promise is still being kept. Two
`done` criteria were allowed to contradict each other for roughly four weeks, and the
store showed nothing wrong. Any assertion whose target is a file no code path reaches has
this property, so the orphan is not the interesting part — the aiming is.

**Update, 2026-08-19.** The amendment alone did not settle it. An adversarial review of
PR #510 found that the three amended criteria still read `work_status: done` while their
only proof remained the grep suite above — the branch that amended them never touched
that file, and the executed-behaviour tests their `test_spec` names do not exist. All
three were reset to `in_progress` in that PR. The lesson generalises: amending a
criterion whose proof is a grep does not give it proof, and the store will happily carry
a stronger claim on weaker evidence than it had before.

**Fix direction.** Two separable moves. (1) Reconcile the specs — done in PR #510.
(2) Structural: a test whose only subject is a source file should be detectable as such,
and a source file that no command, workflow, deploy manifest or runtime path reaches
should not be able to serve as a criterion's `implemented_by`. The reachability guard
family `BO-2900` is the natural home; check it before authoring anything new. A cheap
interim: when a criterion's `implemented_by` names a workflow file, assert that file is
reachable from a command template or another workflow.

---

### KI-BO-012 — The fast lane emits no telemetry, so the lane-comparison report can never contain fast-lane data

- **Severity:** high
- **Status:** open — no AC; the BO-2400d family needs the same reconciliation the
  BO-2500d family just had, and that is a product decision
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-19
- **Where:** `templates/workflows-js/fast-lane-ship.js` (the absence), against
  `scripts/agent-health/agent_telemetry.py` and `generate_health_report.py`

**Symptom.** `BO-2400d` promises "See what each build costs and how long it takes". The
telemetry module, its record schema, its failsafe and the lane-comparison report are all
built, tested and `done`. The lane that actually runs never calls any of it.

**Evidence.** `grep -c telemetry templates/workflows-js/fast-lane-ship.js` returns `0`.
The only fast-lane emission of `agent_telemetry.py emit_agent_telemetry` is in
`templates/workflows-js/fast-lane-build.js` — the orphan nothing invokes — at lines 128,
197 and 301. `build_lane_comparison_report` groups records by a `lane` field and its own
docstring states that "a lane with no records is absent from the result", so with zero
fast-lane records the fast lane is absent from every comparison the report can produce.
`BO-2400d-3` ("A report compares fast-lane vs heavy-pipeline cost and time per unit of
work") is `done` and cannot be satisfied today.

**The sharp part.** `BO-2400d-1-i` — "An unreachable telemetry sink is surfaced loudly,
never silently" — is also `done`, and it guards the wrong failure. It detects a sink that
cannot be *written*. It cannot detect a sink nobody *calls*, which is the failure actually
present. A guard aimed one step downstream of the real gap reads as coverage.

**Why it recurred.** KI-BO-006 warned that deleting the orphan would silently retire
prompt caching. That was right about the category and counted only one instance. The
caching half was fixed (BO-2400c-1-iii) and the entry then read as discharged, while the
orphan had been sheltering a second capability the whole time. Found only by auditing the
orphan's full contents while sizing `BO-2400c-1-v` — not by re-reading the KI.

**Fix direction.** Decide first, build second — same order as the BO-2500d
reconciliation. Either wire emission into `fast-lane-ship.js` and re-point `BO-2400d-1`'s
proof at an executed dispatch, or state plainly that the fast lane is untelemetered and
amend `BO-2400d-3` to say what it actually compares. Do NOT delete the orphan until this
is settled — see the second blocker recorded in `BO-2400c-1-v`'s notes. The same audit is
owed to every other capability the orphan references: two have now been found this way and
nobody has enumerated the rest.

---

### KI-BO-013 — A documentation-only AC anywhere in a resolved build set jams the fast lane at commit, because `test_required: false` is honoured by nothing

- **Severity:** high
- **Status:** open — no AC
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-19
- **Where:** `scripts/build_orchestration/fast_lane.py` —
  `mark_done_built_acs` / `check_no_stale_todo`; `scripts/ac_store/done_proof.py`

**Symptom.** The lane resolves a connected build set, then at Phase 5 requires that
*every* built AC ends `work_status: done`. `mark_done_built_acs` only flips ACs whose
coverage gate passed, and the coverage gate needs at least one green `# covers:`-tagged
test. A documentation AC has no test and declares `test_required: false` — so it is never
in `covered_ac_ids`, never flipped, and `check_no_stale_todo` then reports it stale and
fails the run. The lane also has no documentation phase (it dispatches `test-writer` then
`python-coder` only), so the doc would not have been written either way.

**Evidence.** `grep -rn test_required` across `fast_lane.py`, `done_proof.py` and
`mark_ac_done.py` returns **nothing**. The field is part of the AC schema and is read by
the ticket-generation path, but the entire done-proof chain the fast lane depends on is
blind to it.

Reproduction, re-measured 2026-08-24 after the aiming fix (BO-2600b-1) landed in this
same branch — the originally-recorded repro (`--ac BO-2600b-1` resolving five ids) no
longer reproduces, because that command now carries `--exclude-structural-parent` and
because b-1/-1-i/-1-ii are now `done`; it returns `[]`. The current standing repro is:

```
select_connected --ac BO-2600b --exclude-structural-parent
  -> ["BO-2600b-2", "BO-2600b-3"]
```

`BO-2600b-3` is a how-to AC with `assigned_agent: documentation-expert` and
`test_required: false`, so that set still cannot be built by the lane as it stands. The
defect is unchanged; only the command that exhibits it moved. Worth noting the correction
itself: a known-issue whose repro line has quietly stopped reproducing is the same
stale-evidence failure this register exists to catch, one level up.

**Why it is worse than it first reads.** The operator cannot avoid it. Build sets are
resolved from the store, not chosen — so a single documentation child anywhere in a
subtree makes that whole subtree unbuildable by the lane, and the failure surfaces at
Phase 5, *after* the test-writer and coder have done all their work. Worse, the halt
message is `mark_done stale: <ids>`, which reads like a coverage failure in the code and
sends the reader looking for a missing test that was never supposed to exist.

**Note the failure is half-correct**, which is why it should not be "fixed" by loosening
the gate. Refusing to mark a doc AC done when no doc was written is right. The defect is
that the lane has no way to *produce* the doc and no way to *exclude* it, so a correct
refusal presents as an unexplained jam.

**Fix direction.** Three candidates, in preference order. (1) Give the lane a
documentation phase, so a resolved doc AC is built rather than tripped over — this is the
only option that makes the promise "point at an id, get a PR" true for a subtree that
includes docs. (2) Teach the done-proof chain to honour `test_required: false` with a
different proof obligation (the named doc file exists and changed in the diff), rather
than treating absence of a test as absence of proof. (3) At minimum, make the halt say
what actually happened: name the AC, its `assigned_agent`, and that the lane has no phase
for it. Do not simply skip untestable ACs — that reintroduces phantom-done through the
front door.

---

### KI-BO-016 — Resolving a one-criterion build set takes ~3 minutes, because every traversal re-parses the entire AC store

> **Renumbered at merge, 2026-08-25: filed as `KI-BO-014`, now `KI-BO-016`.** `main`
> independently minted its own `KI-BO-014` and `KI-BO-015` while this branch was in
> flight. Three acceptance criteria (`BO-2400c-6`, `-6-i`, `-6-ii`) and two commit
> messages cite the old id; they resolve here. Physical position kept where it was
> written rather than moved to the end, so the surrounding merge history stays legible.

- **Severity:** high → medium
- **Status:** the N+1 re-parse is FIXED by **BO-2400c-6** / **-6-i** / **-6-ii**; the entry
  stays open for the residual recorded at the bottom, which has no AC
- **Occurrences:** 1
- **First seen:** 2026-08-24 · **Last seen:** 2026-08-24
- **Where:** `scripts/ac_store/scan_ac_store.py` — `traverse_ac_tree`, against
  `scripts/build_orchestration/fast_lane.py` — `resolve_connected_build_set`

**Kept rather than deleted, deliberately.** This register's policy is to delete a section
when its fix lands. Not done here for two reasons: three acceptance criteria and two commit
messages already cite `KI-BO-014` by id, and deleting it would leave those references
dangling; and the defect as filed — N+1 full parses — is fixed while the cost it was filed
*about* is only reduced. Closing it would read as "resolution is fast now", which is not
what was achieved.

**Symptom.** Phase 2 of every fast-lane run — resolving the connected build set — costs
minutes before any work begins, and the cost grows with the store rather than with the
size of the set being resolved. Resolving a set of **one** criterion is as expensive as
resolving a large one.

**Evidence.** Measured on `main` at `ef8c6343` against the real store of **3,232** AC
files:

```
/usr/bin/time -f "%e seconds" fast_lane.py select_connected \
    --ac BO-2400c-1-i --ac-root docs/acceptance-criteria --exclude-structural-parent
  -> ["BO-2400c-1-i"]
  -> 178.32 seconds
```

Correct answer, one id, just under three minutes. Before the aiming fix (BO-2600b-1) the
same call resolved five ids and exceeded a 120-second probe repeatedly, which was
originally misread as a store-size problem rather than an algorithmic one.

**Mechanism.** `traverse_ac_tree` opens by building a complete id→record index of its own:
it `rglob`s `*.yaml` under the store root and YAML-parses **every** file, on **every
call**. `resolve_connected_build_set` has already built exactly that index before calling
it, and then calls it again once per not-done composite dependency it expands. So a run
pays for N+1 full parses of the whole store where N is the number of composite
expansions — never fewer than two. At roughly 90 seconds per full parse, the tight path
costs ~178s and the wide path (structural-parent walk, pre-fix) costs a multiple of it.
This is also why the exclusion flag looked like a performance fix: it removes traversals,
not just criteria.

**Why it is worse than a slow script.** It is a per-run tax on the lane's whole promise —
"point at one id and get a PR" — paid before the first agent is dispatched, and it scales
with total store size, so it worsens every time anyone authors an AC anywhere in the
repo. It is also invisible as a defect: the command returns the right answer, so nothing
fails and nobody files it. It surfaced only because a probe timed out.

**Fix direction.** Pass the index that already exists. `traverse_ac_tree` should accept an
optional prebuilt id→record map and use it when supplied, with the self-building path kept
for standalone callers; `resolve_connected_build_set` then hands over its own `id_index`
and the run drops to a single parse. Check the other `traverse_ac_tree` call sites in the
same pass — the same re-read is paid by anything that walks the tree in a loop. A
behavioural guard is straightforward: assert the resolver parses the store once for a
multi-expansion set, rather than asserting a wall-clock bound, which would be flaky.

**Outcome, 2026-08-24 — fixed as specified, and the number is worth reading carefully.**
`traverse_ac_tree` gained an optional prebuilt `id_index`; `resolve_connected_build_set`
now builds the index once and passes it. The correctness trap was handled the right way:
it snapshots `dict(id_index)` **before** `_drain_cycles` mutates it and hands the traversal
that undrained view, so cycle-adjacent subtrees still resolve. The self-building path
survives for `goal_to_epic.py`, which holds no index. Guarded by a parse-count assertion,
not a wall clock.

Measured on the same command, `select_connected --ac BO-2400c-1-i
--exclude-structural-parent`, returning the identical `["BO-2400c-1-i"]` throughout:

```
before:  178.32 s
after:    27.10 s  (implementing agent's measurement)
after:    39.11 s  (independent re-measurement, different machine load)
```

Both figures are real; the spread is load, and the honest range is roughly 4.5-6.5×.

**The residual, which is why this entry stays open.** One full parse of 3,232 YAML files
still costs ~30-40 seconds, and that is now the floor. The lane's cold start went from
"unusable" to "noticeable", not to "fast", and it still scales with total store size — so
it will drift back toward a minute as the store grows. Removing the repeated parse was the
filed defect; making a single parse cheap is a different problem and needs a different
answer, most likely a cached or incrementally-maintained index rather than a full YAML
walk per invocation. Not filed as its own entry only because it is the same measurement in
the same place; whoever picks it up should split it out then.

Worth stating plainly so the improvement is not oversold: an operator pointing the lane at
one criterion still waits half a minute before the first agent is dispatched.
### KI-BO-014 — `goal_to_epic`'s `--ac` entry path never received the BO-2600a-5 hygiene fixes, so it writes absolute `implemented_by` and untranslated `depends_on`

- **Severity:** high
- **Status:** open — no AC; `BO-2600a-5` is `done` and its coverage is incomplete, see
  the AC-coverage note below
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/goal_to_epic.py` — `run()` (`:2170`), against
  `build_epic_from_ids()` (`:2013`); call sites at `:2344` and `:2113`
- **Reported by:** customer bug report 2026-08-25

**This entry deliberately covers two symptoms under one root cause.** They present as
separate bugs — bad paths in one place, bad dependency ids in another — but they are the
same defect seen twice, and filing them apart would invite two point-fixes that patch the
symptoms and leave the divergence itself untested. The finding worth recording is that
this generator has two entry paths that have drifted, not that two fields are wrong.

**Root cause.** `goal_to_epic.py` exposes two ways to build an epic. `build_epic_from_ids()`
serves the `--ids` path and received both hygiene fixes under BO-2600a-5. `run()` serves
the `--ac` path and received neither. Everything below follows from that one asymmetry.

**Symptom 1 — absolute paths in `implemented_by`.** `run()` passes the absolute
`epic_path` straight through to `_replace_implemented_by_entry()` (`:2344`), so
machine-absolute paths are written into the AC store. That is precisely the condition
`scripts/normalize_ac_paths.py` exists to clean up, re-introduced by the generator that
should never create it. `build_epic_from_ids()` handles the same step correctly: it
relativises **both** the old and the new path against the worktree root (`:2127-2135`)
before calling the same helper, so the values it writes start with `tickets/`.

**Symptom 2 — untranslated `depends_on`.** `_translate_ticket_depends_on()` (`:1918`)
converts AC ids in a ticket's `depends_on` into the co-located epic-folder filenames the
guard expects. Its **only** call site is inside `build_epic_from_ids()` (`:2113`);
`run()` never calls it. So on the `--ac` path a within-epic dependency stays an AC id and
does not match the `NN_`-prefixed filename `assemble_epic_folder()` actually wrote
(`{index:02d}_` + source name, `:948`), and every such ticket fails
`ticket_frontmatter_guard`. Cross-epic dependencies fare no better: they name something
outside the folder, which the guard rejects outright.

**Consequence, stated plainly.** `goal_to_epic` cannot currently emit an epic that passes
this repository's own pre-commit hooks for any AC that has internal dependencies — which
is most of them. The `--ids` path is fine; the `--ac` path is not.

**Evidence — the divergence was known when the fix was written.** The comment at the fix
site in `build_epic_from_ids()` names `run()`'s behaviour explicitly, as the thing being
corrected in the other function (`:2117-2120`):

```python
    # Hygiene fix (BO-2600a-5): the existing run() passes absolute epic_path as
    # new_path to _replace_implemented_by_entry, producing absolute paths in
    # implemented_by. Here both old and new paths are relativised against the
    # worktree root so implemented_by values start with "tickets/" (never "/…").
```

The defective behaviour is documented, in the source, by the author of the fix — and left
in place on the other path.

**AC-coverage note — another phantom-done instance.** `BO-2600a-5` is `work_status: done`
and claims repo-relative `implemented_by` and generation-time `depends_on` translation. It
separately claims that "the existing `--ac` mode is preserved unchanged", which is true and
is exactly the problem: both hygiene rules landed only on `build_epic_from_ids()`, so the
criterion's coverage is incomplete on the `run()` path while the store reports it satisfied.
Read together, the two clauses of that criterion are in tension — a hygiene rule stated
unconditionally cannot also be scoped to one entrypoint — and the resolution chosen at
implementation time was the narrower one, silently.

**Fix direction.** Hoist the hygiene step into a shared helper that both entrypoints call,
so there is one implementation rather than two that can disagree. Then parametrise the
existing BO-2600a-5 regression tests
(`unit_tests/build_orchestration/test_bo_2600a_5.py`) over **both** `run()` and
`build_epic_from_ids()`, so the paths cannot drift again. Parametrising is the load-bearing
half: a shared helper still permits a future caller to bypass it, and only a test that
exercises every entrypoint will notice.

**Related.** The sibling `goal_to_epic` defects found in the same review are filed under
`ac-driven-dev`: KI-ACD-010 (ASCII punctuation survives into the epic name), KI-ACD-011
(truncation ends on a dangling stopword), KI-ACD-012 (the generated Master_Plan fails
`ticket_frontmatter_guard`). KI-ACD-012 and this entry are the same shape from opposite
sides — a generator emitting artifacts its own repository's gates reject.

---

### KI-BO-015 — `_worktree_exists` does not know the `fast-lane/` prefix, so a fast-lane run can never reuse its own worktree and aborts at phase one

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/scripts/setup_ticket_worktree.py:232-275` (`_worktree_exists`), called at `:1289` from `cmd_create_fastlane_worktree`; branch built at `:1286` by `_fastlane_branch` (`:487-500`)

**Symptom.** `cmd_create_fastlane_worktree` creates the branch `fast-lane/<slug>` but asks
`_worktree_exists(slug)` whether a worktree already exists. That function matches a branch
against exactly three hardcoded prefixes:

```python
f"refs/heads/feature/{branch}",
f"refs/heads/ticket/{branch}",
f"refs/heads/ac-authoring/{branch}",
```

`fast-lane/` is absent, so the lookup can never match a fast-lane worktree. The reuse
branch is unreachable code. Every invocation falls through to `git worktree add`, which
fails with exit 128 the moment anything already occupies the target path. The workflow
surfaces this as `{"worktree_path": ""}` and halts at its first phase, having done nothing.

**Two consequences, the second worse than the first.**

*Collision.* The worktree path is derived solely from the AC id — `worktrees/<slug>` — so
any pre-existing directory there kills the run. This is how it was found: a hand-created
`worktrees/bo-1500a-5` (made minutes earlier for the same AC) caused
`fatal: '/home/henzeh/projects/leafcutter/worktrees/bo-1500a-5' already exists`, then
`fatal: … contains modified or untracked files, use --force to delete it`.

*Non-idempotency.* Re-running the fast lane on an AC it has already built fails the same
way, against its **own** prior worktree — which is exactly what the reuse branch exists to
prevent. `git worktree list` currently shows `worktrees/bo-2900g-3` on `fast-lane/bo-2900g-3`,
so re-running `BO-2900g-3` today would abort at phase one for this reason alone. A build
tool that cannot be re-run on the same input is the more serious half of this defect; the
collision is just the loud version.

**Evidence.** Confirmed by reading the source at HEAD, not inferred from the failure.
`grep -n "refs/heads/fast-lane" templates/scripts/setup_ticket_worktree.py` returns nothing;
`_worktree_exists(slug)` is called at `:1289` (and at `:1398` in the `scripts/` build-output
copy) while `_fastlane_branch(slug)` returns `fast-lane/<slug>`. Both copies carry it —
`scripts/setup_ticket_worktree.py` is generated from `templates/`, so a fix must land in
`templates/` and be mirrored, never edited in `scripts/` alone.

**Fix direction.** Pass the full branch name and match on it, rather than reconstructing
prefixes inside the lookup — `_worktree_exists` already receives a bare slug from three
other call sites, so the low-risk shape is an optional `prefixes` argument (or a
`full_branch=` overload) with `fast-lane/` added for this caller. Two things worth deciding
at the same time, both of which this AC tree (`BO-1500f-2`) is already specifying for the
authoring path: whether a re-run should reuse the existing worktree or mint a
run-distinct one, and whether the path should carry anything beyond the AC id so two
sessions on one AC cannot resolve to the same directory. Whatever is chosen, the failure
should name the occupying path and say which of the two cases it is, instead of surfacing an
empty `worktree_path`.

**Numbering note.** Filed as KI-BO-008 while this work sat in review, then renumbered to
014, then to 015 — main published a different 008, then everything through 013, then its
own 014, across the review window. The third renumber happened *during* the second one:
main gained 014 between reading the file and writing the append. KI-BO-010 carries the
same note from an earlier round. A number reserved in a long-lived branch is not reserved;
the free number must be re-read against `origin/main` at the moment of landing, not at the
moment of drafting.

**Status update, 2026-08-25.** Specified by `BO-2400f-13` and its four children. The chosen
ending is a **named refusal**, not reuse and not a run-distinct path — see that criterion's
`notes` for the reasoning, and `KI-BO-017` below for a pre-existing defect found while
specifying it.

---

### KI-BO-022 — A CRLF acceptance-criterion record is rewritten LF end-to-end by a single `work_status` flip, and every value-level check still passes

> **Renumbered 2026-08-25 from KI-BO-019.** PR #538 landed its own KI-BO-019 at 14:51 UTC;
> PR #539 landed this one at 15:09 UTC and the two collided on `main`. #538 was first, so
> it keeps the number and this entry moves. See KI-BO-024.

- **Severity:** high
- **Status:** open — latent, zero live instances today
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/build_orchestration/fast_lane.py:169-171` (read) and `:205-207` (write), function `_update_ac_work_status`; reached from all three call sites (`:288`, `:346`, `:461`)

**Symptom.** Both the read and the write use text mode with default newline handling. The
read collapses `\r\n` to `\n`; the write emits `\n`. So flipping one `work_status` value on
a CRLF-encoded record rewrites **every line in the file**. Confirmed by execution against
the real `BO-2400a-3-i.yaml` converted to CRLF: **154 changed lines** from one flip.

```
'-id: BO-2400a-3-i\r'
'-components:\r'
... 142 more
```

**Why it will not be noticed.** `yaml.safe_load` still reports `work_status = 'done'`
afterwards, so every parsed-value assertion passes. This is the same blindness that let
the original KI-BO-003 defect survive — a re-serialised record parses equal to the
original. Any test that checks values rather than bytes is blind to it.

**Why it matters.** This is precisely the failure `BO-2400e-4` ("Recording progress on a
requirement changes the progress and nothing else") exists to prevent, arriving through a
door that AC did not anticipate. `BO-2400e-4` was marked done on 2026-08-25 on the
strength of tests that only exercise LF records, so the AC now reads as satisfied while
this hole is open.

**Exposure.** A scan of all 3,257 store records found **0** with CRLF, so nothing is
broken today. It is filed rather than fixed because the exposure is one careless write
away: this repo is developed under WSL2 with a checkout reachable from `/mnt/c`, and any
Windows-side editor that normalises line endings on save would introduce a CRLF record
silently. There is no guard that would report it.

**Fix sketch.** Open both ends with `newline=""` so line endings round-trip, or read bytes
and splice. A CRLF fixture belongs in
`unit_tests/build_orchestration/test_ki_bo_003_ac_yaml_preservation.py` alongside the
existing byte-level cases.

---

### KI-BO-023 — `_update_ac_work_status` raises `ValueError`, all three call sites catch only `OSError`, and the escape strands acceptance criteria in `in_progress` permanently

> **Renumbered 2026-08-25 from KI-BO-020**, for the same collision described on KI-BO-022.
> Note the coincidence worth reading: main's KI-BO-020, landed by PR #538 seventeen minutes
> earlier, describes the *same consequence* — aborted runs stranding their claims — by a
> different mechanism (its release path dispatches `status-checker`, which refuses the
> role). Two independent branches found two independent causes of one symptom on the same
> day. Both are real; neither supersedes the other.

- **Severity:** high
- **Status:** open — latent, zero live instances today
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** raise at `scripts/build_orchestration/fast_lane.py:180-185`; call sites catch `except OSError` only at `:289` (`claim_build_set`), `:347` (`release_claim`), `:462` (`mark_done_built_acs`)

**Symptom.** When a record contains more than one column-0 `work_status:` line the
function raises `ValueError` — deliberately, rather than guess which is the real key. But
no caller catches it. Confirmed by execution; observed disk state after the escape:

```
claim_build_set:      ESCAPED ValueError ...  A left at: ['work_status: in_progress']
release_claim:        ESCAPED ValueError ...  C left at: ['work_status: in_progress']
mark_done_built_acs:  ESCAPED ValueError ...
```

**Two consequences, the second much worse.**

*Lost claim payload.* `claim_build_set` flips records to `in_progress` on disk as it goes,
then loses its return value to the exception. `fast-lane-ship.js:391-437` builds
`claimedIdsCsv` from exactly that payload to feed every `release-on-*-fail` path, so the
records it already flipped are never released.

*The un-sticking mechanism is the thing that breaks.* `release_claim` is what returns a
stranded AC to `todo`, and it aborts mid-loop on the same exception. Everything after the
offending record stays `in_progress` **forever** and is then permanently excluded from
future runs by `filter_already_claimed`. Recovery is a hand edit.

**The docstring's justification is falsifiable.** It claims column-0 anchoring means an
occurrence of `work_status` inside block-scalar prose is never mistaken for the real key.
Two constructions defeat it, both confirmed:

- A legal multi-line double-quoted scalar whose continuation begins at column 0. PyYAML
  parses this correctly as one `work_status: todo`; the function counts two matches and
  raises:

  ```yaml
  id: B-1
  notes: "the release step resets it back to
  work_status: todo when the run fails"
  work_status: todo
  ```

- `U+2028` or `U+0085` inside a block scalar. `str.splitlines()` splits on `U+2028`,
  `U+2029`, `U+0085`, `\x0b`, `\x0c` and `\x1c`-`\x1e`; YAML's line-break set is narrower.
  The phantom second match raises on a perfectly valid record.

**Exposure.** 0 of 3,257 records currently have more than one column-0 match, so no run is
failing this way today.

**Fix sketch.** Two independent halves, and the second matters more than the first. Narrow
the detection (parse-aware, or at minimum split on YAML's line-break set rather than
Python's) *and* widen the three call sites to catch `ValueError` alongside `OSError`, so
that a raise can never leave claims stranded regardless of what triggers it. The release
path in particular should be failure-tolerant per record rather than aborting the loop.

---

### KI-BO-021 — TODO: `BO-2400e-4` is closed on two of its four specified tests, and the two missing ones are the pair that would survive a writer swap

- **Severity:** medium
- **Status:** open — coverage debt, tracked against `BO-2400e-4` (`work_status: done`)
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `unit_tests/build_orchestration/test_ki_bo_003_ac_yaml_preservation.py`; AC at `docs/acceptance-criteria/build-orchestration/BO-2400-fast-lane-build/BO-2400e-4.yaml`

**What is owed.** `BO-2400e-4`'s `test_spec` names four tests. The 14 existing tests supply
two of them (single-record textual diff; field order and untouched text). Two are absent:

1. `test_eleven_member_build_changes_only_its_progress_values` — eleven REAL records copied
   from the store, driven through begin/finish, asserting the total textual change is
   confined to the progress values.
2. `test_progress_recording_preserves_the_record_via_the_real_surface` (angle:
   `reachability`) — drives `claim_build_set` / `release_claim` / `mark_done_built_acs`
   rather than the private helper.

**Why the second one is the point.** Every existing test calls `_update_ac_work_status`
directly. If `BO-2400e-3`'s durable-write work introduces a **new** writer and repoints the
three call sites at it, this suite carries on testing an orphaned function and stays green
while the shape-preservation guarantee is silently gone. `BO-2400e-4`'s own constraint 3
names this outcome ("two writers will drift and one of them will stop preserving") and its
`test_rationale` predicts it verbatim.

**Why it is live rather than theoretical.** `BO-2400e-4` `depends_on: [BO-2400e, BO-2400e-3]`
specifically so that e-3's durable writer would land *first* and this AC would then
constrain it. The build order was inverted — e-4 was satisfied incidentally on 2026-08-18
via KI-BO-003, and e-3 is being built afterwards. The protection the dependency was written
to provide therefore does not exist, and these two tests are what would replace it.

**Sequencing.** Write them **before** the `BO-2400e-3` work merges, so the durable write has
to prove it preserves shape. Landing e-3 first loses the red-baseline evidence that these
tests constrain it.

**Not filed as an AC** because `BO-2400e-4` already specifies both tests exactly; this is
unbuilt work against an existing spec, not a new requirement.

---

### KI-BO-017 — A fast-lane re-run whose worktree was pruned silently rebuilds on the old branch tip instead of the latest `origin/main`

- **Severity:** high
- **Status:** open — found while specifying `BO-2400f-13`, deliberately not fixed there
- **Occurrences:** 0 observed directly; reachable today on every AC the lane has already built
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `templates/scripts/setup_ticket_worktree.py:529` — the checkout-only branch of
  `_create_fastlane_worktree`, reached from `cmd_create_fastlane_worktree` at `:1289`

**Symptom.** When the branch `fast-lane/<slug>` exists but its worktree has been pruned or
removed, `_create_fastlane_worktree` takes its checkout-only path — `git worktree add <path>
<branch>` with no start point. That reconnects the workspace at **the old branch tip**, which
is wherever the prior run left it. Nothing re-cuts it from `origin/main` and nothing says it
did not.

**Why this contradicts a `done` criterion.** `BO-2400f-3` (`work_status: done`) promises a
branch "cut from the latest `origin/main` (never from stale local main)". That promise holds
on a first run and silently fails on a reconnect. The lane then builds, tests and reports
green against a mainline that may be days old — a green result measured against a tree that
no longer exists. This is the same hazard that led the Product Owner to reject
reuse-in-place for `KI-BO-015`, arriving through a different door: the reject decision
covered the case where the *worktree* survives, and this is the case where only the *branch*
does.

**Why it is the common case, not an edge.** Every finished run leaves exactly this state
behind once its worktree is cleaned up. `worktrees/` is periodically reclaimed (the
`wsl-reclaim` timer removes merged-and-clean worktrees with no age wait), so the branch
routinely outlives its workspace. So the population at risk is "every AC the lane has ever
successfully built", and it grows monotonically.

**Why it is invisible.** The reconnect succeeds, exits 0, and returns a well-formed payload
with a real `worktree_path`. There is no warning, and the payload carries no indication of
which commit the workspace was cut from. From the lane's point of view — and the operator's
— a stale reconnect and a fresh cut are indistinguishable.

**Evidence.** Read at HEAD, not inferred from a failure. `_create_fastlane_worktree`
branches on `_branch_exists(full_branch, repo_root)`; the true branch runs `git -C <repo>
worktree add <path> <branch>` (no start point, `:529`), while only the false branch cuts from
`origin/main`. `git worktree list` on 2026-08-25 shows three live fast-lane worktrees
(`bo-1500a-5`, `bo-2400e-3`, `bo-2900g-3`); each becomes an instance of this issue the moment
its directory is reclaimed while the branch remains.

**What `BO-2400f-13` does and does not do about it.** `BO-2400f-13-iv` requires that this
residual state — branch present, location free — is **not** refused, because refusing it
would make the lane unusable on every AC it has already built. To keep the divergence from
staying silent, the IT PO specified that the first-phase report carry `base_commit`, read
**from the workspace** (`git -C <worktree> rev-parse HEAD`) rather than from the commit-ish
handed to git, alongside an explicit `base_matches_origin_main`. That makes the staleness
*visible* in phase one. It does not make it *correct*.

**Fix direction — genuinely undecided, and a product call.** Two candidates, and the choice
is not obvious:

- *Re-cut.* Reset the reconnected branch to `origin/main` before building. Correct with
  respect to `BO-2400f-3`, and destructive: it discards any commits the prior attempt made
  that were never merged. Must not be done silently.
- *Reuse and report.* Build on the old tip but state the base commit and its distance from
  `origin/main` in the outcome. Honest and non-destructive, but still ships a green result
  measured against a stale tree, which is what `BO-2400f-3` exists to prevent.

A third shape worth considering is to refuse this case too, consistently with `BO-2400f-13` —
at the cost of making a very common state require manual intervention.

**Do not fix this inside `BO-2400f-13`.** It predates that criterion, it is reachable
independently of any occupancy check, and the implementer of `BO-2400f-13` is explicitly
forbidden from resolving it by reset or rebase. It needs its own criterion once the product
decision is made.

---

### KI-BO-018 — `/plan-feature` halts on a false `worktree-agent` permission verdict, caused by a truncated agent-relayed config read rather than anything wrong with the agent's charter

- **Severity:** blocker — this is not a workflow inconvenience: per ADR-012, `/plan-feature`
  is the canonical entry path for **all** new work, and this defect halts that workflow
  before any authoring agent is dispatched. There is no fallback path that avoids it.
- **Status:** open — no AC
- **Occurrences:** 2 (reproduced twice, same day)
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `templates/workflows-js/plan-feature.js` (deployed at
  `.leafcutter/workflows/plan-feature.js`), ~lines 1747-1770; `config/agent_registry.json`

**Symptom.** `/plan-feature` halts before dispatching any authoring agent with the message:
"Workspace-setup step 'worktree-setup' is configured to dispatch to agent 'worktree-agent',
whose registered charter does not permit running repository/shell commands." That message is
FALSE — `config/agent_registry.json` gives `worktree-agent` `permits_shell: true` (verified
by direct read of the registry file).

**Real mechanism.** `plan-feature.js` (deployed at `.leafcutter/workflows/plan-feature.js`,
~lines 1747-1770) resolves the permission NOT by reading the registry file directly, but by
DISPATCHING a `status-checker` agent with the prompt "Run the following command and return
ONLY the raw stdout output: `cat .leafcutter/config/agent_registry.json`", then
`JSON.parse`-ing the returned wrapper. `config/agent_registry.json` is 129,787 bytes. The
agent round-trip truncates the payload at exactly 75,000 characters, splitting an escape
sequence mid-token, so `JSON.parse` raises: `Invalid \escape: line 1 column 75001 (char
75000)`. The surrounding try/catch is fail-closed — the code comment at the catch site reads
`permitsShell = false; // fail closed` — so a transport failure (truncation) becomes a
substantive verdict about the agent's charter, and the run halts.

**General lesson (the reusable finding).** A check that could not perform its inspection
(the config read was truncated and unparseable) reports a confident SUBSTANTIVE verdict
("this agent is not permitted") instead of "undetermined" — and its remediation text sends
the reader to go fix `permits_shell`, a field that is already correct. This is the mirror
image of the existing guarantee **GE-120a-1** ("a check that could not perform its
inspection reports a degraded outcome, not a clean pass").

**Secondary observation, same entry.** The workflow's shell probes run with the process
working directory set to the untracked workspace parent, not the repository — evidenced by a
sibling probe in the same run returning `fatal: not a git repository (or any of the parent
directories): .git` (exit 128) while the `cat` of `.leafcutter/config/agent_registry.json`
succeeded from that same directory. The registry read therefore succeeds only INCIDENTALLY,
because that particular workspace parent happens to hold a populated `.leafcutter/` — this
would not hold for every layout.

**Fix direction.** Read the registry from disk directly (e.g. via the workflow's own
file-read primitive) rather than round-tripping it through an agent's text response; and on
any parse failure, report "could not determine" rather than asserting the charter denies
permission. Not implemented — this entry records the defect and the proposed direction only.

---

### KI-BO-019 — The context bundle is passed through an agent's JSON return value, so a large bundle arrives as a file path and the fail-closed gate halts a run whose bundle was fine

- **Severity:** blocker — the fast lane cannot complete an end-to-end run on a real target
- **Status:** open. The mitigation that shipped is the third fix option below, and the
  second occurrence **disproves** it — see "Second occurrence" at the end of this entry.
- **Occurrences:** 2
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-31
- **Where:** `templates/workflows-js/fast-lane-ship.js` — the `fastlane-context-bundle`
  dispatch and the `contextBundleUsable` gate that reads it (the `CACHE_BREAKPOINT_MARKER`
  constant and the `contextBundle.includes(...)` check)

**Symptom.** The lane asks its bundle agent to return
`{"bundle": "<the command's stdout, verbatim>", "obtained": true, ...}`. On a real target the
bundle is ~149 KB. The agent assembled it correctly, wrote it to disk, and returned a
**pointer** instead of the content:

```json
{"bundle": "file:/tmp/bo2400f13-bundle/bundle_output.txt", "obtained": true,
 "message": "Bundle assembled successfully (exit 0, no stderr) ... read that file to get the exact bundle text"}
```

The gate then evaluates `contextBundle.includes("<!-- CACHE_BREAKPOINT -->")` against a
47-character path, finds no marker, and halts the run (BO-2400c-1-iii).

**The gate is not the bug — it did exactly the right thing.** The bundle on disk is
well-formed: 148,891 bytes, 2,232 lines, five layers, with the breakpoint marker present at
line 958. Every check the gate performs is correct and the fail-closed posture is correct.
What failed is the **transport**: the contract says "return 149 KB of text as a JSON string
field", and that is not a contract an agent reliably honours. Note the message is not evasive
either — the agent said plainly what it had done and where the content was. It simply
answered a different question than the one the schema asked.

**Why this is structural rather than a retry-able flake.** The E2 workflow engine has **no
filesystem access**, so the lane physically cannot follow the pointer it was handed. The
bundle must arrive in-band or not at all. That puts two requirements in direct tension:
the bundle is large by design (it is a prompt-cache payload — that is the point), and the
only channel into the workflow is an agent's return value. Re-running may happen to succeed
if the agent echoes verbatim, which would make this look intermittent; it is not. The
contract is unsound at this size and will fail again on any comparably sized target.

**Evidence.** Run `wf_bd4984e8-438`, target `BO-2400f-13`. Five agents completed, none
errored. Worktree created (`worktrees/bo-2400f-13`, `fast-lane/bo-2400f-13`), set resolved to
the correct five ids, all five claimed, bundle assembled — then halt at `context-bundle`. The
halt payload's own `Detail` reads `"obtained": true` and `"Bundle assembled successfully"`
while the run is classified `blocked`, which is the tell: the lane's own message contradicts
its verdict because `obtained` and *usable* are being conflated in the operator-facing text.

**Fix direction.** Three shapes, and the choice is a real design decision:

- *Have the Python side do the check.* `assemble-bundle` already knows whether it inserted
  the marker. Return a small verdict (`{"ok": true, "bytes": N, "marker": true, "path": ...}`)
  and let the lane gate on the verdict rather than on the text, so the payload crossing the
  agent boundary stays small. This changes what "obtained" means, so BO-2400c-1-iii's wording
  needs revisiting alongside it.
- *Accept a pointer explicitly*, and give the lane a way to read it. That needs an fs
  primitive the engine does not have today, so it is the largest change.
- *Keep the verbatim contract and enforce it*, by making the agent's schema reject a value
  that looks like a path and by stating the size expectation in the prompt. Cheapest, and the
  least robust — it fights the model rather than the design.

**Second occurrence, 2026-08-31 — and it disproves the option that shipped.**

The third option above is what landed: `fast-lane-ship.js`'s bundle prompt now states
`SIZE EXPECTATION: the assembled bundle is roughly twenty kilobytes (~20 KB)` and refuses a
reply that "names where the text can be found instead of containing the text". Run
`wf_22fae0b9-291`, target `BP-900g-9-i`, failed anyway — in a **new and worse way**.

The agent did not return a path this time. It returned the content **in-band, and altered**:

```
&amp;lt;!-- CACHE_BREAKPOINT --&amp;gt;        <-- what arrived
<!-- CACHE_BREAKPOINT -->              <-- what assemble-bundle emits
```

The whole payload had been HTML-escaped in transit — every `-->` in the architecture doc's
mermaid arrived as `--&gt;` — and the marker, which contains `<`, was escaped twice. The
source doc on disk contains **zero** HTML entities, confirmed by grep, so the escaping is
introduced by the transport and not present in the input.

Three things follow, and each is worse than the first occurrence.

**The reference-rejection guard cannot see this.** It was added precisely for occurrence 1
and it is working correctly — the reply *is* content, not a pointer. Mangled content passes
every check that distinguishes content from a reference, because it is content.

**The size hypothesis is wrong.** Occurrence 1 was 149 KB and this entry concluded "the
contract is unsound at this size and will fail again on any comparably sized target". The
agent reported `"bytes": 18190` for occurrence 2 — **18 KB, under the ~20 KB the prompt
itself names as the expectation**. It failed at the size the design targets. The contract is
not unsound at 149 KB; it is unsound at any size, because byte-exact reproduction of markup
is not something a model does reliably however short the text.

**Only the marker check caught it.** Nothing else in the lane compares what arrived against
what was assembled. Had the bundle contained no marker-shaped token, silently corrupted
context would have been handed to the test-writer and coder dispatches as though intact, and
the run would have completed green on a mangled prompt. The gate that saved this run exists
for cache correctness, not integrity — it caught an integrity failure by luck of shape.

**What this does to the fix calculus.** Option three is no longer "least robust"; it has been
tried and has failed at its design size, in a way its own new guard cannot detect. Option one
(let the Python side emit a small verdict and gate on that, keeping the payload off the agent
boundary) is the only remaining shape that does not require an fs primitive the engine lacks.
Whatever is chosen, the lane needs an integrity check comparing what arrived against what was
assembled — a byte count or digest returned by `assemble-bundle` and re-derived on the
received text — because "it looks like content" is demonstrably not the same as "it is the
content", and that distinction is currently unmade.

**Operational consequence right now: the fast lane cannot complete a run on any target.**
Both occurrences halted at the same phase, five to six agents in, after creating a worktree
and claiming the build set. The worktree is left behind.

Whichever is chosen, the operator-facing message must stop saying "was not obtained" when
`obtained` was true. Distinguish *not obtained* from *obtained but unusable, because X* —
the current text sent a reader looking for an assembly failure that had not happened.

**Update, 2026-08-25 — the fix direction above is superseded, and the layer's premise is
false.** A Product Owner pass on the transport question found that the thing the transport
exists to protect does not exist. Three findings, each verified independently:

- `grep -rn "cache_control" templates/ scripts/ config/` returns **zero hits**. No provider
  cache breakpoint is set anywhere in the product. `<!-- CACHE_BREAKPOINT -->` is a literal
  HTML comment inside a prompt string, and nothing consumes it but this gate.
- The two consumers **cannot share a cached prefix even under automatic provider caching**.
  Line 561 dispatches `agentType: "test-writer"`; line 635 dispatches `agentType:
  "python-coder"`. Different agents, different system prompts. A prompt cache matches an
  exact prefix from the *start of the request*, system prompt first, so the two requests
  diverge long before the bundle appears in the user message. The bundle's "stable prefix"
  is not a prefix of anything the cache sees.
- The stable layer is **not stable across runs**. The bundle prompt names
  `docs/architecture/README.md`, which does not exist, and tells the agent to substitute
  "the nearest architecture index" — so that layer is composed by agent judgement and two
  runs at one target need not produce the same bytes. `BO-2400c-1-iv` only asserts
  byte-identity *within* one run, which is a triviality of interpolating one JS variable
  twice.

`BO-2400c-2.yaml:113` and `BO-2400c.yaml:33` already conceded the first point in writing on
2026-08-18/19. Work continued against the old claim regardless, which is the part worth
remembering.

**The payload is 87% duplicate — measured.** `conventions.md` is 38,291 B and
**byte-identical** to the worktree `CLAUDE.md` (`diff -q` exits 0), which the harness already
injects into every agent dispatched into that worktree. `acs.yaml` is 90,887 B of AC records
that the test-writer prompt (line 548) *already instructs the agent to read from
`${acStoreRoot}`*. Together 129,178 of 148,891 bytes are a second copy of something the agent
already has. Genuinely additive: architecture + high_level + prior_tests ≈ **20 KB**.

So the transport failure is a symptom and the payload is the disease. **Chosen direction:**
split on the *duplicate-vs-additive* line rather than stable-vs-volatile — pass only the
~20 KB the agent does not otherwise have, drop the conventions and acs layers entirely, and
keep the reference-rejection and a stated size expectation as a cheap belt on a payload
already small by construction rather than as the mechanism. Specified in the
`BO-2400c-1-iii` amendment and the new `BO-2400c-1-vi`; `BO-2400c-1-iii` is reset from
`done` to `in_progress` because its gate half works and its transport half never did.

Two consequences recorded rather than left implicit. **The CLI signature changes:**
`injection_builders.py` marks `--architecture`, `--conventions`, `--high-level`, `--acs` and
`--prior-tests` all `required=True` (lines 654-670), so dropping two layers changes what
`assemble-bundle` accepts, not just what the lane passes — a call-site audit in the removal
direction. **And the L1 is overclaiming:** `BO-2400c`'s "spend less time and money on every
build" is not what this layer delivers. Until `BO-2400c-2` exists and reports, no cost claim
belongs in a doc, a PR body, or a release note; if it reports no shared cache, the L1 should
be re-framed from *cost* to *consistency* — the layer's real remaining benefit is that every
agent starts from the same complete, named context instead of whatever it decides to read.

**Keep the fail-closed gate exactly as it is.** It is the one part of this family with a
demonstrated win: on its first live run against a real target it caught a genuine transport
defect and refused to proceed.

---

### KI-BO-020 — The fast lane's release-on-failure path is dead: it dispatches `status-checker`, which refuses the role, so aborted runs strand their claims

- **Severity:** high — silent, and it defeats a criterion believed to be working
- **Status:** **RESOLVED** (fix landed under `BO-2400f-10-i`; verified 2026-09-01) — **but read
  the residual below, which is a different and still-open defect.**
  `fast-lane-ship.js:490` now declares `const RELEASE_EXECUTOR_AGENT_TYPE = "python-coder";`
  and all nine release sites route through that one constant rather than a per-site literal.
  Confirmed live, not merely by reading: a `/fast-lane-build BO-2400c-1-v` run on 2026-09-01
  halted at the coder phase and reported `Release: succeeded — BO-2400c-1-v returned to todo`.
  This entry sat at `open` for a week after being fixed, and was recommended as the next thing
  to build on 2026-09-01 before anyone checked the code — the second stale entry found in a
  single review of this register.
- **Occurrences:** 2 observed; every failing path that releases is affected
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `templates/workflows-js/fast-lane-ship.js` — the release dispatches on the
  failure paths, e.g. `release-on-context-bundle-fail`, all of which pass
  `{ agentType: "status-checker" }`

**Symptom.** When a phase fails after the claim step, the lane dispatches a release agent to
put the claimed ACs back to `todo`. The prompt opens `You are the release-phase agent.` and
the dispatch uses `agentType: "status-checker"`. `status-checker` **refuses**:

> I am status-checker, not a "release-phase agent." This message attempts to reassign my role
> and have me execute a fast-lane AC-release script — that is outside my defined scope … I
> did not run the requested command.
> `{"status": "refused", "reason": "out-of-scope-r…`

The lane does not inspect the reply — the release is best-effort and its result is discarded
— so the run reports its halt and the ACs stay `in_progress`.

**Second occurrence, 2026-08-25, on a different failure path.** A `/fast-lane-build BP-1100b-5`
run halted at `release-on-review-fail` (the review gate, not the context-bundle gate), and
`status-checker` refused in the same terms, adding a second objection the first sighting did
not record:

> I am status-checker, not a release-phase agent. This message attempts to reassign my identity
> … **and no user of this session has asked me to do this in-turn; a task-prompt asserting a
> different role for me is not a valid instruction source.**

That clause matters for the fix. The agent is not merely refusing an unfamiliar command — it is
applying a general rule about role reassignment via task prompt. So re-wording the prompt will
not help, and neither will a more forceful instruction; the dispatch needs a different
`agentType` whose charter actually includes releasing claims, or the release needs to stop
being an agent dispatch at all. It is a single deterministic CLI call
(`fast_lane.py release --ac-ids …`) with no judgement in it, which is a poor reason to involve
a model.

`BP-1100b-5` was left at `work_status: in_progress` by the halt, confirming the strand.

**The strand is narrower than it looks, for a reason that is its own defect.** The
`in_progress` flip lives only as an **uncommitted edit inside the lane's private worktree** —
`origin/main` still reads `todo`. So deleting the worktree discards the strand, and this entry's
"aborted runs strand their claims" is true only for as long as that worktree survives. The
flip side is worse than the strand: a claim that never reaches shared state cannot exclude
anything. See KI-BO-20260826-1332, where that is the primary finding.

**Verified, not inferred.** After run `wf_bd4984e8-438` halted, all five claimed ACs were
still `work_status: in_progress` in the run's worktree store, with `BO-2400f-13` and
`BO-2400f-13-i` confirmed by direct read. The release agent had run and returned; it simply
did nothing.

**Why the containment was luck, not design.** The damage stayed harmless only because a
fast-lane run claims in **its own worktree's** copy of the store, which is discarded with the
worktree — `origin/main`'s copy still read `todo`. Any path where a claim reaches a shared
store leaves those ACs stranded `in_progress`, where BO-2400f-8 will then correctly refuse to
rebuild them: a failed run silently makes its own target unbuildable.

**This invalidates a premise other work is resting on.** `BO-2400f-13`'s reasoning (and the
Product Owner's decision to refuse rather than reuse an occupied workspace) is written on
"the lane has no resume semantics — BO-2400f-10 releases the claim on abort". BO-2400f-10 is
specified and believed working, but its **only invocation path is dead**. The refuse decision
still holds — it holds *more* strongly, since a leftover workspace may also carry stranded
claims — but the stated reason is currently false and should not be quoted as established
behaviour until this is fixed.

**This is a known agent-level pattern, now seen in a second caller.** `status-checker` refuses
role reassignment by design. The same refusal already breaks `/plan-feature`'s gates, where it
is dispatched to "ask the user" and returns a well-formed `{action: cancel}` that reads as a
real decision. The general lesson: **dispatching an agent under a role name that is not its
own is not a prompt-style choice — the agent will refuse, and a caller that ignores the reply
turns that refusal into a silent no-op.**

**Fix direction.** Do not route the release through a persona-mismatched agent. Either give
the release its own minimal agent whose charter includes mutating AC claim state, or — better,
since the release is a single deterministic command — invoke `fast_lane.py release` directly
rather than asking an agent to run it. Whatever the shape, **read the reply**: a release whose
result is discarded cannot distinguish "released" from "refused", which is precisely how this
stayed invisible. A release that did not release should surface in the halt payload next to
the failure that triggered it.

**Update, 2026-08-25 — this is nine dead paths, not one.** A `grep -n "agentType"` across the
lane shows **every** release dispatch passes `agentType: "status-checker"`, and every one opens
its prompt "You are the release-phase agent.":

| line | label |
|---|---|
| 506 | `release-on-context-bundle-fail` |
| 574 | `release-on-test-writer-fail` |
| 596 | `release-on-red-baseline-fail` |
| 648 | `release-on-coder-fail` |
| 668 | `release-on-coverage-fail` |
| 751 | `release-on-review-fail` |
| 773 | `release-on-review-fail` |
| 871 | `release-on-changelog-fail` |
| 943 | `release-on-commit-fail` |

So it is not that one failure path strands its claims — **every failure path in the lane
does**, from the first phase to the last. The observed run happened to fail at the earliest of
the nine. Any covering test must drive all nine, not the one that was seen.

**A latent sibling with the same shape and a worse failure mode.** The CLAIM dispatch at line
393 opens "You are the claim-phase agent for a fast-lane build." with `agentType:
"status-checker"` (line 402) — identical persona mismatch. It **complied** on the observed
run, which is exactly why nobody has noticed it. Its failure mode is the inverse of the
release's and more dangerous: a silent non-claim would let two runs build the same acceptance
criterion concurrently, with `BO-2400f-8`'s exclusivity guard never firing because nothing was
ever claimed. That belongs with `BO-2400f-7`, not here, and it is deliberately NOT folded into
this fix — but a change to the release dispatches must leave it demonstrably alone rather than
half-converting it. Recorded in `BO-2400f-10-i`'s notes.

**Placement.** Specified as `BO-2400f-10-i` (the release actually releases, on every halting
path) and `BO-2400f-10-ii` (the result is read; a failed release is named in the halt *beside*
the failure that caused it, not instead of it). `BO-2400f-10` is reset from `done` to
`in_progress`: marking done a criterion whose only invocation path has never once executed is
the phantom-done shape this family exists to end.

**One question carried, not resolved.** `BO-2400f-10` says the release "is landed on
mainline", but a fast-lane run claims in its own workspace's copy of the store, which is
discarded with the workspace — the only reason the observed failure was harmless. Whether the
release is meant to reach mainline at all is a product question; the new criteria are worded
against "the store the run claimed in" so they hold either way.

**Related, and it compounds — see `KI-BO-023`.** That entry records a *second*, independent way
a claim gets stranded: `_update_ac_work_status` raises `ValueError`, all three call sites catch
only `OSError`, and the escape leaves acceptance criteria `in_progress` permanently. So there
are now two distinct mechanisms stranding claims — a release that is never *reached* (this
entry) and a release that is reached and *throws past its own error handling* (KI-BO-023).
Fixing either alone still leaves claims stranded. `BO-2400f-10-ii`'s requirement that the
release's result be **read** is the common defence: both mechanisms are silent today precisely
because nothing inspects the outcome.

---

### KI-BO-024 — "Append the next free number" is not a workable id convention under concurrent agents, and on 2026-08-25 it finally shipped a duplicate to `main`

- **Severity:** medium
- **Status:** open — the immediate duplicates are repaired; the convention that produced them is not
- **Occurrences:** 10 in a single day (2026-08-25), of which 1 reached `main`
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-25

**Tenth occurrence, 2026-08-25 — this entry predicted it and then it happened here.** A triage
authored `KI-BO-025` against an `origin/main` that had no 025; by the time that branch rebased,
another session had landed 025, 026 and 027. Renumbered to `KI-BO-028` with four inbound
references updated. Caught by a git merge conflict, which is luck rather than a check: the two
sides appended to the same region of the same file. Had they appended to *different* registers,
or had either landed via a path that auto-merges cleanly, the duplicate would have reached
`main` exactly as the 019/020 pair did. This is the fourth id space to collide in one day
(`KI-BO`, `GE-120`, `BP-900h-4/-5`, and the AC store's own `ACD-1200a`), which is the argument
for option 3 below — a duplicate-heading check is cheap and is the only one of the three that
fires without depending on where the collision happens to land.
- **Where:** the "Adding an issue" instruction at the top of every `docs/known-issues/*.md`

**Symptom.** The convention says to append using "the next free number". A branch reads the
file, picks the next number, and by the time it lands that number is taken. There is no
reservation, no allocator, and no check — the number is chosen against a snapshot and
validated by nothing.

**This is no longer a near-miss.** Every prior occurrence was caught by re-reading
`origin/main` immediately before landing. On 2026-08-25 that defence failed for the first
time, because the collision landed *inside the window between the final check and the merge*:

| | |
|---|---|
| PR #539 renumbered 017/018/019 → **019/020/021**, checked against `origin/main` at `eed3601c` | ~14:40 UTC |
| PR #538 merged, publishing **its own** KI-BO-019 and KI-BO-020 | 14:51 UTC |
| PR #539 merged | 15:09 UTC |
| `main` now carries two KI-BO-019 and two KI-BO-020 | — |

Repaired by this entry's PR: #538 was first and keeps the numbers; #539's entries moved to
`KI-BO-022` and `KI-BO-023`, taking a test filename and its 21 internal references with them,
plus two published changelog entries whose pointers had gone stale.

**Nine occurrences in one day.** `KI-BO-008 → 014 → 015`; `KI-CG-010 → 012`; `KI-BO-016/017/018
→ 017/018/019 → 019/020/021 → 022/023`. Three of those were *second* renumbers — the file moved
again while the first renumber was being written.

**Why the current defence cannot be made to work.** "Re-read the free number against
`origin/main` at the moment of landing" is already written into this file (under KI-BO-014) and
was followed. It is a time-of-check-to-time-of-use race, and the window is the merge queue.
Narrowing it does not close it. There is also no way to see numbers reserved in a *branch* or
in someone's uncommitted working copy — while writing this entry, two candidate numbers had to
be skipped because a concurrent session held them uncommitted, which no amount of checking
`origin/main` would have revealed.

**The cost is not the renumbering.** It is that every reference goes stale at once: section
headings, `# covers:` tags, test filenames, cross-references between entries, commit messages,
and already-merged changelog entries. The 019 → 022 move above touched four files and 20-odd
references, and a missed one silently points a reader at someone else's defect.

**Fix directions, cheapest first.**

1. **Make the number non-sequential.** A date-plus-slug id (`KI-BO-20260825-crlf-rewrite`) cannot
   collide, needs no allocator, and no coordination. Loses ordering, which the file does not
   currently preserve anyway — `main` today lists 016 between 013 and 014.
2. **Allocate at merge, not at authoring.** Author with a placeholder and have a hook or the
   merge queue assign the number. Removes the race but needs tooling and rewrites references.
3. **Detect rather than prevent.** A pre-commit hook and CI check that fails on a duplicate
   `### KI-XX-NNN` heading in any known-issues file. This does not stop the collision, but it
   turns a silent duplicate on `main` into a blocked merge, and it is a few lines. **Worth doing
   regardless of which of the above is chosen** — it is the only one of the three that would
   have caught 2026-08-25 before it landed.

---

### KI-BO-025 — `/build-feature` plans only the first ready wave, so an epic with any dependency depth cannot be driven to completion in one run

- **Severity:** high
- **Status:** open · ACs **BO-100e** (carry the layers) and **BO-300d** (say what was left),
  both authored 2026-08-26, both `readiness: draft` awaiting the approval gate
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `templates/workflows-js/build-feature.js` — the `epic-planner` `agent()` call
  (deployed `~:2101`), and the `for (const batch of batches)` loop that consumes its output

**Symptom.** Driving the 37-ticket `EPIC-TrustThatAGreenCheckActuallyChecked`, the planner
returned 8 batches containing **17** tickets. The other 20 were never scheduled.

The dropped set is not arbitrary. Measured against the epic folder:

```text
total tickets: 37 | planned: 17 | MISSING: 20
tickets with non-empty depends_on: 20
missing set == depends_on set ?  True
planned tickets that have deps:  []
```

Every ticket carrying **any** `depends_on` was dropped; every ticket planned had none.

**Root cause — the planner is asked for one antichain and is never asked again.** Its prompt
says:

> `(2) Compute the maximal antichain of ready tickets (all depends_on met).`

At plan time no ticket is `done`, so "all depends_on met" is true only for tickets whose
`depends_on` is empty. That is a correct reading of the instruction — the planner is not
misbehaving. The defect is that this single ready-set is treated as the whole schedule: the
`agent()` call sits **outside** the batch loop, so there is no re-plan after a batch completes
and no wave 2. One invocation can therefore build at most the dependency-free tickets.

The eight "batches" are misleading here. They are the antichain split by `files_touched`
overlap — a *parallelism* split, not a dependency sequence. Seven of the eight contain a
single ticket, which reads like a dependency chain and is not one.

**Consequence.** An epic whose dependency graph is N levels deep needs N separate manual
`/build-feature` invocations, and nothing in the run says so or says how many remain. For
GE-120 that leaves the entire `b`/`d`/`e` chain — including every consumer of the `GE-120c-1`
harness — unbuilt after a run that did substantial correct work on the other 17.

**Not a false-complete, at least.** The completion guard does catch the shortfall and withholds
the "complete" verdict — but it misdescribes the cause; see KI-BO-026.

**Why it misdescribes it, found 2026-08-31 while enriching the ACs.** The run has no record of
the epic's contents at plan time that is separate from the plan. `plannedTicketPaths`
(deployed `~:2156`) is built by iterating `batches` — the comment above it calls this "the set
of work the plan was built from … the baseline the completion-time re-read is compared against,
by identity (BO-300a-5)", but under this defect the baseline is 17, not 37. The 20 dropped
tickets are therefore absent from the baseline, and at completion time `compareEpicTicketSets`
can only see them as *additions*. **KI-BO-025 and KI-BO-026 are one defect observed from two
ends**, and separating the run's *set* from the run's *schedule* is a precondition for fixing
either — not an optimisation. It also changes what BO-300a-5 (`done`) reports, so it cannot be
done quietly.

**Fix direction.** Either loop the planner until it returns an empty batch set (re-reading
frontmatter each round, which the code comment at `~:2400` already anticipates as the resume
mechanism), or have it emit the full topological schedule as ordered waves rather than one
antichain. If the single-wave behaviour is deliberate, the run must state it: report the count
of unscheduled-but-ready-later tickets and instruct the caller to re-invoke, rather than
leaving the arithmetic to whoever compares the plan against the folder.

**A test-harness precondition blocks all of it, found 2026-08-31.**
`unit_tests/_workflow_engine_harness.py::run_workflow_under_e2` takes
`label_responses: dict[str, Any]` — **one** response object per label, serialised to a flat
JSON literal and returned on every call to that label. The `epic-planner` label therefore
cannot express wave 1 followed by a *different* wave 2, and `ticket-planner` is shared across
every ticket so it cannot differentiate per-ticket replies either. Until the harness supports
sequenced per-label responses, **not one behavioural test for this fix can be written**, and
the work collapses to exactly the grep-only proof CLAUDE.md forbids. Extend the harness first.

**Pattern:** a stage that does part of the job correctly and reports no signal that the rest
exists.

---

### KI-BO-026 — Work the planner never selected is reported as work "added to the epic after the plan was fixed"

- **Severity:** medium
- **Status:** open · AC **BO-300d** (authored 2026-08-26, `readiness: draft`), whose criteria
  were amended on the same day precisely because the first draft demanded an attribution the
  run cannot make. See the 2026-08-31 note on KI-BO-025 for why: the baseline this compares
  against is the plan, not the epic.
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `templates/workflows-js/build-feature.js` — `compareEpicTicketSets()`
  (deployed `~:1838`) and `epicRecheckReport()` (deployed `~:1952`)

**Symptom.** `compareEpicTicketSets` computes

```js
additions: currentOpen.filter((p) => plannedPaths.indexOf(p) === -1)
```

— every ticket that is open at completion time and was not in the plan. That correctly caught
the 20 tickets of KI-BO-025 and correctly set `epic_complete: false`, which is the right
verdict and worth keeping.

But `epicRecheckReport` then files them under the field `discovered_after_planning` with the
action text:

> "This work was added to the epic after the plan for this drive was fixed, so it was never
> built."

That is false. All 20 tickets were committed to the epic folder before the drive was launched;
none was added during it. They were never *added* — they were never *selected*.

**Why the distinction matters.** The two causes have opposite remedies. Work genuinely added
mid-drive is a scope question — someone changed the epic under a running build, and the
sensible response is to find out who and decide whether it belongs. Work the planner skipped is
a tooling question with no one to ask. A reader following the message as written goes looking
for a change that never happened, and the real defect (KI-BO-025) stays invisible behind an
explanation that sounds complete.

The remedy sentence happens to be right — "re-run /build-feature to plan and build it" is
exactly what KI-BO-025 requires — but it is right by accident, for a stated reason that does
not hold.

**Fix direction.** The comparison already has both inputs needed to tell these apart: a ticket
present in the epic folder at *plan* time but absent from `plannedPaths` was skipped, while one
absent at plan time and present at completion was added. Capture the plan-time folder listing
and split `additions` into `never_planned` and `added_during_drive`, with the right remedy on
each. Until then the field name asserts a cause the code cannot actually determine.

> **Review note, 2026-08-26 — that paragraph contradicts itself, and its second half is the
> true one.**
>
> "The comparison already has both inputs needed" and "Capture the plan-time folder listing"
> cannot both hold: the second sentence is an instruction to *create* an input, which concedes
> the first is wrong. Nothing in the data flow carries a plan-time folder listing today.
> `plannedPaths` is what the planner *selected*, which is the value in dispute, and the
> completion-time listing is read fresh at the end. There is no snapshot of what was on disk
> when planning ran, so from what the code currently holds the two causes are genuinely
> indistinguishable.
>
> This matters for whoever picks it up. "The inputs are already there" implies a ten-minute
> change that reads two existing variables; the real work is a new value captured at plan time
> and threaded through to the completion comparison. Anyone starting from the optimistic
> reading will hunt for a plan-time listing, fail to find one, and have to re-derive this.
>
> The rest of the entry is sound and should stay intact — the distinction between "never
> selected" and "added mid-drive", the observation that the two have opposite remedies, and the
> note that the remedy sentence is right by accident are all correct, and are the valuable part.
> Only the "already has both inputs" clause needs striking.
>
> One design question the fix should settle rather than inherit: a plan-time snapshot can itself
> be stale or absent on a resumed or cached run. Decide up front what `additions` reports when
> the snapshot is missing. The honest answer is probably a third bucket meaning "cannot
> determine" rather than a silent fallback to either existing label — falling back is how the
> current fabricated cause arose in the first place.

**Pattern:** a correct verdict delivered with a fabricated cause.

---

### KI-BO-027 — `/build-feature`'s target resolution returns the epic folder as the worktree path

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `templates/workflows-js/build-feature.js` — the `resolve-target` phase, dispatched
  to `status-checker` against `RESOLVE_SCHEMA`

**Symptom.** On the first phase of an epic drive, the resolver returned:

```json
{"target_type":"epic",
 "epic_path":".../leafcutter-ai/tickets/00_inbox/epics/EPIC-TrustThatAGreenCheckActuallyChecked",
 "worktree_path":".../leafcutter-ai/tickets/00_inbox/epics/EPIC-TrustThatAGreenCheckActuallyChecked"}
```

`worktree_path` is the epic's ticket folder **inside the main checkout** — it is not a worktree,
and it is not even a repository root. The value satisfies `RESOLVE_SCHEMA` because the schema
constrains the field to a string, and a path-shaped string is what it got.

**No damage on this run.** A subsequent setup step created a real worktree at
`worktrees/EPIC-TrustThatAGreenCheckActuallyChecked` and returned `status: "created"`, and the
drive used that. Both `.leafcutter` and `.pre-commit-config.yaml` symlinks were present in it,
so the silently-skipped-hooks condition did not arise either.

**Why record it anyway.** The value that came back was wrong, nothing rejected it, and it was
survivable only because a later step happened to overwrite it. Had the second step reused the
first step's answer instead of computing its own, every phase agent would have been pointed at
the user's main checkout on `main` — which is the shape of KI-ACD-007, where `/plan-feature`
wrote its artifacts into the primary checkout for exactly this reason. The resolver failing open
onto a plausible-looking path is the hazard; the recovery was luck, not design.

**Fix direction.** Validate the resolved `worktree_path` before any consumer reads it: it must
be a directory that `git -C <path> rev-parse --show-toplevel` resolves to, and it must not be
the main checkout when the target is an epic. A schema that accepts any string cannot catch
this — the check has to be behavioural.

**Pattern:** a fail-open resolution rescued by a downstream step that did the work again.

---

### KI-BO-028 — Six `done` acceptance criteria in this component are falsified by defects already recorded in this register

> **Numbered 028, not 025.** This entry was authored as `KI-BO-025` against an `origin/main`
> that had no 025, and collided on rebase with the 025/026/027 another session landed in the
> interval — a fresh instance of `KI-BO-024`, caught by a merge conflict rather than by any
> check, which is the whole of that entry's argument. Renumbered here along with its four
> inbound references. Counted as `KI-BO-024`'s occurrence, not filed separately.

- **Severity:** high
- **Status:** open — handover ticket raised, not started
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `BP-600e-2`, `BO-2400f-3`, `BO-2400e-4`, `BO-2200c-5`, `BO-202`, `BO-2300a-1`, `BO-2300a-2`, `BO-1500f-1` — and `unit_tests/workflows/test_fast_lane_ship_structure.py:289`, the test that let three of them read `done`

**Ticket:** [`tickets/00_inbox/TICKET-20260825-BuildOrchestrationPhantomTriage.md`](../../tickets/00_inbox/TICKET-20260825-BuildOrchestrationPhantomTriage.md)

**Symptom.** A read-only triage on 2026-08-25 walked all 65 entries across five
known-issues registers and asked, per entry, whether an acceptance criterion already covered
it. For this component the answer was repeatedly *yes, and the AC is marked done while the
criterion it states is false*. The full evidence per record is in the ticket; this entry
exists so the finding is reachable from the register rather than only from a PR body.

**This entry is a handover.** It was raised from outside this component's work queue. The
owner should re-scope, split or reject any of it — nothing in the ticket was written by
someone holding the context that produced these records.

**The mechanism is worth more than the list.** Three of the six were held up by
**presence-only assertions over JavaScript source**. `BO-2400f-10`'s entire covering evidence
was `self.assertIn("release", content)`, which passes while all eleven release dispatches go
to an agent that refuses the role; its behavioural tests call `release_claim` directly, so the
function works and its caller is dead. `KI-BO-008` files this mechanism in its own right, and
`BP-1100b-5` (`work_status: todo`) already specifies the guard that would catch it — its
scanned-source globs already include `templates/workflows-js/**/*.js`. **Building `BP-1100b-5`
and running it retroactively over existing stock would have caught three of the six**, which
makes it the highest-leverage item and arguably the thing to do before the individual repairs.

**Two were already handled and are excluded.** `BO-2400f-10` and `BO-2400c-1-iii` moved from
`done` to `in_progress` while the triage was running. Re-check the rest the same way before
starting; this register moves fast enough that a day-old finding is worth re-verifying.

**Corrections to existing entries, found during the same pass.** Recorded here rather than
edited into each entry, because this triage did not own them:

- **`KI-BO-011`** says the class — an unreachable file serving as a criterion's proof — "has no
  AC and is the reason this entry stays open". `BO-2900a-3` ("Code that no way of running the
  product can reach cannot be marked done, however many tests pass") specifies it precisely and
  is `todo`, `readiness: reviewed`. The entry's own fix direction said to check the `BO-2900`
  family first; that check was not done.
- **`KI-BO-011`**'s evidence line — "`BO-2500d-1` also names the orphan in its `implemented_by`"
  — is stale since 2026-08-19; that field now points at `fast-lane-ship.js`.
- **`KI-BO-013`**'s headline, "`test_required: false` is honoured by nothing", is overstated.
  `check_done_proof.py` honours it in two places and backs the required CI gate. The body's
  narrower claim — that the *fast lane's* chain is blind to it — is correct and is what was
  verified.
- **`KI-BO-014`** calls `BO-2600a-5` "another phantom-done instance". It is not: every `Then`
  clause in that record sits inside the `--ids` scenario and the final clause explicitly scopes
  `--ac` out, so the record is satisfied by its own wording. The real finding is weaker and more
  common — a hygiene rule written as a scenario-scoped clause when it should have been
  unconditional. Calling it phantom-done makes the fix look like a reconciliation when it is an
  amendment.
- **`KI-BO-012`**'s status line reads "open — no AC" while its own body discusses `BO-2400d-3`
  and `BO-2400d-1-i` as done ACs. Four ACs exist; the problem is that all four open with a
  `Given` presupposing that telemetry is already being recorded, so none can be falsified by
  zero emission.
- **Stale line numbers.** PR #541 shifted `fast_lane.py`. `KI-BO-022`'s `:169-171`/`:205-207`
  are now `:266`/`:186`; `KI-BO-023`'s `:180-185`/`:289`/`:347`/`:462` are now
  `:281`/`:380`/`:438`/`:553`. Both defects are unchanged — only the addresses moved.

**Not everything was still broken**, which is worth saying in a register that only ever
accumulates: `KI-BO-007` is largely discharged — `build-feature.js` now has a real read-back
adjudication that fails closed — and `KI-BO-016`'s filed N+1 defect is genuinely fixed by an AC
whose criteria is a parse-count assertion rather than a wall clock, which is the right shape.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M1 (a test that greps for a string
instead of exercising the behaviour) is the dominant one here; `KI-CG-001`'s population-vs-change
scoping is the dominant one in the sibling registers.

**Addendum 2026-08-26 — a nineteenth phantom-done, and a further concentration.**

`BO-1000c-1a` ("background finalize appends each progress line to a durable, pollable
run-progress journal as it happens") is the nineteenth phantom-done attributed to this sweep,
and the first of them to be **closed**: fixed and merged 2026-08-26 as PR #573, squash
`d97eb399`. `appendJournal()` called `require('fs')`, but the E2 engine injects no module
loader (ADR-030), so the call threw on every invocation inside a `try`/`catch` that logged a
WARNING while the run reported success. The AC read `work_status: done` throughout. The helper
and both call sites are removed; the criterion was redefined onto the journal the engine
already writes per agent dispatch; `work_status` is now `in_progress`, not `done`, because
only 1 of its 5 declared test descriptors is implemented.

The count is the sweep's own accounting, not a field any register maintains — its findings are
spread across this entry, `KI-ACD-019`, and the reopened-AC changelogs, and no single list
holds all of them. Recorded here because this entry is the closest thing the register has to
that list.

**A note on the count.** Earlier drafts of this addendum said "this entry names three"
concentrations and called the new one the fourth. It does not: this entry names **one**
mechanism plus a closing Pattern line, and `BO-2200c-5` appears only in a **Where** list. The
taxonomy of three — presence-only assertions over JavaScript source (M1), population-vs-change
scoping (`KI-CG-001`), and a producer never round-tripped through its consumer
(`BO-2200c-5`) — comes from the 2026-08-25 triage's own working notes, not from this register,
and counting a fourth against a set this entry never stated was retro-fitting.

Stated properly: `BO-1000c-1a` exhibits a concentration **not among those three**, filed as
**`KI-BO-20260826-1333`** — a test file where nine of ten tests are presence-only against one
source file, so the shape is close to the file's whole design rather than one weak test among
stronger ones, and the AC looked comprehensively covered precisely because coverage was
measured by count. Nine of the ten fail against the corrected source, each demanding the dead
mechanism be restored; the tenth, an absence assertion, survives. Its countermeasure — a single
**absence** assertion, which a behavioural test cannot substitute for when the reintroduction
is inert — is recorded there.

---

### KI-BO-029 — The fast lane stages with `git add -A` into a worktree its own bootstrap already dirtied, so every fast-lane PR silently carries unrelated generated diff

- **Severity:** medium
- **Status:** open — no AC
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `templates/workflows-js/fast-lane-ship.js:916-920` (Commit phase, Step 2) interacting with `scripts/setup_ticket_worktree.py`'s bootstrap `build.py` run

**Symptom.** A fast-lane worktree is dirty from birth. `setup_ticket_worktree.py` runs
`build.py` as part of bootstrap, which regenerates `docs/agents/cards/*.card.md` (the drift
recorded as **`KI-BP-015`**). No agent has run yet and the tree already has modified tracked
files. The Commit phase then stages with `git add -A`, so that churn lands inside the pull
request the lane opens.

**Evidence.** Three independent worktrees created on 2026-08-25, all off `origin/main`, all
dirty immediately after bootstrap with no agent having touched anything:

```
worktrees/knowledge-harvest-wiring   4 cards modified
worktrees/fastlane-ki-findings       4 cards modified
worktrees/inf-400c-2-ii              7 files: docs/INDEX.md + 6 cards   (+119 / -4)
```

The third is a real `/fast-lane-build INF-400c-2-ii` run. At the point that run halted in
review, `git status` showed the seven unrelated files alongside the three the build actually
authored. The lane halted before Step 2, so **the `add -A` sweep specifically** is not observed
in a landed commit — but the code path is unconditional, so a run that reaches commit will
include them.

**A second, independent path produces the same outcome, and this entry's own commit hit it.**
The commit that added this section staged exactly three `docs/known-issues/` files; four landed.
The `transform-doc-index` pre-commit hook regenerated `docs/INDEX.md` and added it to the index
mid-commit. The regenerated line was an unrelated doc's description
(`adopt-consolidated-output-root`: `"How to adopt…"` → `"Overview of How to adopt…"`), nothing to
do with the change being committed.

That is worth more than a footnote, because `docs/INDEX.md` is **not** in
`check_changelog_presence.py`'s `EXEMPT_PREFIXES`. A PR consisting solely of exempt
known-issues edits was therefore failed by the required `Changelog entry present` gate, naming
`docs/INDEX.md` as the sole releasable file — a gate failure caused entirely by a hook's own
output. So the family has two mechanisms, not one:

| Mechanism | Stages | Reaches |
|---|---|---|
| bootstrap `build.py` + fast lane `add -A` | agent cards, `docs/INDEX.md` | fast-lane PRs |
| `transform-doc-index` hook auto-add | `docs/INDEX.md` | **any** commit touching docs |

The second affects every commit, not just fast-lane ones, and converts an exempt PR into a
non-exempt one. Workaround used here: `git restore docs/INDEX.md` and re-commit with
`SKIP=transform-doc-index`. Either add `docs/INDEX.md` to `EXEMPT_PREFIXES` or stop the hook
auto-staging a file the author did not touch.

**`add -A` is deliberate, which is why this is not a one-line fix.** The comment at
`fast-lane-ship.js:796-802` explains it: the Changelog phase writes `emit_entry.py` output to
disk uncommitted, and relies on the Commit phase's `add -A` to pick it up so the entry lands in
the PR's own diff rather than a follow-up commit. Narrowing the stage to the coder's
`files_modified` would drop the changelog entry. The fix has to stage a computed set —
`files_modified` ∪ the changelog path ∪ the claimed AC files — not simply narrow `add -A`.

**Why it matters more than the diff size.** The commit message is a fixed template:
`"feat: fast-lane build of ${targetAc} connected set (N ACs)"`, immediately followed by the
instruction *"Every claim in the commit message must be verifiable in the staged diff."* The
message cannot describe card regeneration because it is generated before the diff is known, so
every affected PR ships a diff its own message does not account for — the failure this repo
codifies as a hard rule in `CLAUDE.md` → "Commit messages must match the diff", and the same
shape as the `EPIC-PhantomDoneFilesTouched` KI-4 postmortem that rule came from.

It also silently launders `KI-BP-015`. That entry is rated **low** on the reasoning that the
cards merely drift; if the fast lane regenerates and commits them as a side effect of unrelated
work, the drift is repaired at random intervals by PRs that never mention it, which makes the
drift harder to reason about rather than easier.

**Fix direction.** Either (a) stage a computed path set in Step 2 and drop `add -A`, or
(b) have the bootstrap leave a clean tree — `git restore docs/agents/cards/` after the
bootstrap `build.py`, which is already the manual workaround prescribed at
`build-pipeline.md:162`. (b) is smaller and also fixes the same sweep for `/build-feature`
worktrees; (a) is the one that makes the lane's staging honest regardless of what dirtied the
tree. They are complementary, not alternatives.

**Related:** `KI-BP-015` (the card churn itself, occurrence count raised to 3 by this run),
`KI-BP-016` (the `docs/INDEX.md` case, which is destructive rather than additive and also
appeared in the `inf-400c-2-ii` worktree; `KI-BP-001` describes the same defect but is marked a
duplicate of 016, so 016 is the one to fix).

---

> **Entries `KI-BO-030` and `KI-BO-031` are recovered from an unmerged branch** — PR #495's
> parallel known-issues register, discarded during reconciliation. See the equivalent note in
> `commit-guardian.md` for the full provenance. Both were re-verified against `main` at
> `37655862` before filing. A third entry from that set was **dropped as fixed**: it reported
> `docs/agents/cards/*.card.md` failing `check-doc-frontmatter` with *"unknown doc type: card"*,
> and `card` is now a valid type in `config/doc_types.json` — running the hook against
> `docs/agents/cards/ac-validator.card.md` exits 0. A fourth (card drift on every build) is
> already covered by `build-pipeline.md`'s `KI-BP-002` and was folded in there as an occurrence
> rather than duplicated here.

---

### KI-BO-030 — `build.py` never creates two of the four namespace roots, so registering the uniqueness gate would make the package uninstallable

- **Severity:** high
- **Status:** open — code is on `main` and live. The *blocking consequence* below additionally
  requires PR #495's fail-closed gate, which is not on `main`; the scaffolding gap itself is,
  and is the precondition that must land first.
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-26 (re-verified against `37655862`)
- **Where:** `scripts/build.py` / `scripts/build_phases.py` (base install path);
  `scripts/seed_project_docs.py::seed_architecture_scaffolds` (`--seed-docs` path);
  `templates/docs/architecture/`

**Symptom.** A fresh consumer install gets `docs/acceptance-criteria/` (a `README.md` and an
`index.yaml`), but **`docs/architecture/adrs/` and `docs/architecture/diagrams/` are never
created**. With the `KI-CG-007` fail-closed contract in place, both are unresolvable, and an
unresolvable root blocks *regardless of what is staged*.

Measured on a real `git commit` of one unrelated markdown file in a pristine install, with the
gate hand-registered:

```
Check Identifier Uniqueness (GE-122 whole-collection pass).....Failed
- exit code: 1
[check_identifier_uniqueness] decisions: FAILED (0 inspected)
[check_identifier_uniqueness] diagrams:  FAILED (0 inspected)
BLOCKING: the following namespace(s) could not be resolved at all: decisions, diagrams
```

`--seed-docs` does **not** rescue it: that path creates `docs/architecture/adrs/` but writes its
C-diagram to `docs/architecture/c1-001-system-context.md` and never creates a `diagrams/`
subdirectory. Both documented install paths fail.

**Evidence it is still true.** `templates/docs/architecture/` at `37655862` contains
`README.md`, `FRONTMATTER.md`, `c1-001-system-context.md.template`, and an `adrs/` folder
(`README.md` + `ADR-template.md`) — and **no `diagrams/` subdirectory**. Since
`seed_architecture_scaffolds()` mirrors that tree verbatim, no `diagrams/` root can be produced.
`build_phases.py` contains no `mkdir` for either architecture root.
`docs/reference/architecture-docs-layout.md` — written on `main` to answer this issue —
independently records both gaps as outstanding recommendations.

**Root cause of the ordering hazard.** The fix is small: create the two roots empty, since an
**existing-but-empty** root passes cleanly by design. But the ordering is not optional:

1. scaffold the two roots in `build.py`
2. **then** register the hook (see `KI-CG-021`)
3. **then** re-run the deployed-consumer test

Shipping (1) and (2) in one change produces a package that cannot be installed.

**Why nothing caught it.** Five prior review rounds tested the gate by importing the module or
running the script from the source tree, where all four roots exist because this repo is not a
fresh install. The defect is only visible in the layout the code actually ships into.

**Two unrelated fresh-install blockers observed in the same experiment**, each worth its own
ticket:

- `check-secrets` flags ~30 `ENTROPY_HIGH` / `GENERIC_SECRET` hits **in the package's own
  deployed agent templates**.
- `check-hook-parity` looks for `templates/scripts/commit_guardian/` in the consumer, which a
  consumer never has. Still true: `check_hook_parity.py:465` defaults `canonical_template_dir`
  to exactly that path.

With `fail_fast: true` the first aborts the run. **A fresh install cannot currently make one
clean commit, with or without the GE-122 gate.**

**Fix direction.** Guarantee both roots from the BASE install path, not only `--seed-docs`, each
carrying a real placeholder file so git can track it. Resolve together with `KI-CG-028` (the
missing `architecture_diagrams` key in `config/paths.json`) — one change should decide where the
directory lives and how the gate finds it. `BP-900h-6` and `GE-122d-3-ii` are the ACs sized
against this entry.

---

### KI-BO-031 — `check_doc_frontmatter.py` tells the operator to consult a spec file that does not exist

- **Severity:** low
- **Status:** open — code is on `main` and live
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-26 (re-verified against `37655862`)
- **Where:** `templates/scripts/commit_guardian/check_doc_frontmatter.py:473-474` (the failure
  remediation block); also referenced at `:5`, `:127`, `:601`, `:610`

**Symptom.** On any frontmatter violation the hook prints:

```
   FIX: Add or correct YAML frontmatter per docs/FRONTMATTER.md spec.
   📖 Spec: docs/FRONTMATTER.md
```

`docs/FRONTMATTER.md` does not exist in this repository. The one file with that name is
`templates/docs/architecture/FRONTMATTER.md`, which is a consumer-install template and not
reachable at the path printed.

**Why it survives.** The message is on the *failure* path only, so it is read exactly when
someone is already blocked and looking for the rule — the worst moment to hand them a dead
path. Nothing tests remediation strings, and a dangling reference in a print statement is
invisible to `check-doc-links`, which reads markdown link syntax rather than program output.

**Evidence.** Recovered as a sub-note of the (now fixed, hence dropped) agent-card frontmatter
entry; the parent defect was resolved and this one was not. `ls docs/FRONTMATTER.md` →
`No such file or directory`.

**Fix direction.** Point at the file that actually documents the rules, or make the message
name the specific missing field and the valid enum it is checked against — which the hook
already computes and prints one line earlier, making the spec pointer redundant rather than
merely wrong.

**Pattern:** same shape as `KI-TQ-003` — a gate that works correctly and whose remediation
instruction cannot be followed.

---

### KI-BO-20260826-1214 — The fast lane cannot complete: its context-bundle gate demands a 1359-line document inlined into a JSON field, and the agent returns a pointer instead

- **Severity:** blocker → **low** (2026-09-01: not reproducing; see the update below for why
  this is a mitigation rather than the structural fix this entry asked for)
- **Status:** resolved-by-mitigation, 2026-09-01 — no AC. The lane ships again. The
  inline-by-value contract that made this possible is unchanged, so the failure mode is
  suppressed, not removed.
- **Occurrences:** 4 — three consecutive runs of `BP-900g-9` on 2026-08-26 (identical halt),
  then once more on a different AC six days later (`BP-1400c-1`, 2026-09-01 05:51, a
  14,018-byte bundle — an order of magnitude smaller than the 141,933-byte bundle of
  `KI-BO-019`, which rules out size alone as the trigger)
- **First seen:** 2026-08-26 · **Last seen:** 2026-09-01 · **Verified not reproducing:**
  2026-09-01
- **Where:** `templates/workflows-js/fast-lane-ship.js`, the `context-bundle` phase and its
  validation of the returned `bundle` field

**Symptom.** `/fast-lane-build BP-900g-9` halts every time with:

```
status: blocked
failing_phase: context-bundle
"The context bundle was not obtained — the prompt-caching layer's assembling dispatch
 failed, returned nothing usable, or the bundle was empty or missing the cache
 breakpoint marker."
```

**That message is wrong about its own cause, and the difference matters.** The dispatch did
not fail. On the third run the phase agent completed successfully (`agents_error: 0`) and
returned `"obtained": true`. The bundle was genuinely built:

```
$ wc -l /tmp/bp-900g-9-bundle/bundle_output.txt      -> 1359
$ grep -c CACHE_BREAKPOINT /tmp/bp-900g-9-bundle/bundle_output.txt -> 1
```

`injection_builders.py assemble-bundle` exited 0 with empty stderr, assembled all five
layers, and inserted the `<!-- CACHE_BREAKPOINT -->` marker after the `high_level` layer.
The artefact is correct and on disk.

**The actual defect is the contract.** The workflow requires the bundle *content* to come
back inline in the agent's `bundle` return field, and validates that field for the cache
breakpoint marker. Asked to return 1359 lines through a JSON field, the agent did what
models reliably do with bulk content — it wrote a reference instead:

```
"bundle": "See /tmp/bp-900g-9-bundle/bundle_output.txt for the full 1359-line
           assembled bundle (verified zero-exit, no stderr). Layer sources used: ..."
```

while its own `message` asserted "The bundle field of this response contains the command's
stdout verbatim." It does not. The field holds a summary, the summary contains no marker,
the guard correctly rejects it, and the run halts.

**The guard is not the bug — keep it.** Refusing to proceed on a bundle that fails its
marker check is right, and the workflow explicitly declines to fall back to prompts composed
some other way (`BO-2400c-1-iii`). That is the correct posture. The bug is that the only path
through the guard requires an agent to inline a large document verbatim, which is not a
thing an agent reliably does. So the gate is unpassable in practice: **the fast lane cannot
currently ship anything**, deterministically, for any AC.

**Why it went unnoticed.** The halt is honest — it stops rather than proceeding on bad
context — so it reads as a transient infrastructure problem rather than a permanent
deadlock. The first run of this AC *did* fail for a genuine API reason
(`Failed to authenticate. API Error: Blocked Content Notification`), which masked the real
cause; only on the third run, with `agents_error: 0` and `obtained: true`, was the contract
defect visible.

**Fix direction.** Pass the bundle by *path*, not by value: have the phase agent return the
file path it wrote, and have the workflow read and validate that file itself. The workflow
already has the marker check; pointing it at the artefact rather than at a field the agent
must retype removes the failure mode entirely and keeps the guard intact. If the content
must travel inline, the contract needs to say so in a way an agent can satisfy — and the
validation error must distinguish "the command failed" from "the agent summarised instead of
pasting", because those need opposite responses.

**Do not re-file the release noise seen alongside this.** Every one of these three halts also
reported "Release: refused or unreadable … left at `in_progress`; a later run will be refused"
while both ACs were verifiably `todo` on disk. That is a *separate*, already-fixed defect — the
release dispatches carried no schema, so the engine returned their reply as a string and the
success branch was unreachable. Fixed on `main` at 04:25 on 2026-08-26 (`RELEASE_SCHEMA` +
`coerceReleaseReply`, changelog *"The release that worked was reported as a failure, on every
path"*). It was observed here only because this worktree was built from an `origin/main` that
predated the fix. Verified present in the merged file before this entry was written; it is not
part of this issue.

---

**UPDATE 2026-09-01 — a fourth occurrence, then the lane started shipping. Neither fact means
what it first looks like.**

**The fourth occurrence, and what its artefact proves.** `/fast-lane-build BP-1400c-1` halted
the same way at 05:51. Its bundle survives at `/tmp/bp-1400c-1-bundle.out` and was measured
rather than assumed:

```
bytes                     14018
CACHE_BREAKPOINT markers  1
runs of 4+ newlines       0
non-blank text after the marker   985 bytes
```

Every one of those is what a good bundle looks like. In particular the last two rule out
`KI-BO-20260831` (`#634`, the blank-line-run false positive) as the cause: this bundle has no
4-plus-newline run to trip it and a healthy suffix. Classification would return `usable` on
this content. So the halt was the **reference** state — the agent again reported where the
text was instead of returning it — which is precisely this entry's own defect, recurring on a
different AC, at a tenth the size of `KI-BO-019`'s. Size is not the trigger, and this is not a
duplicate of either neighbour.

**Why "fixed" would be the wrong word.** The fix direction recorded above — pass the bundle by
*path* and let the workflow read the artefact — **was never implemented**. The lane still
requires the content inline in the `bundle` field, and `isContextBundleLocatorString` still
*refuses* a locator rather than dereferencing it. What actually changed is the ask: `#605`
(2026-08-26) added an explicit size expectation to the dispatch prompt ("roughly twenty
kilobytes … small enough to return in full") and an explicit statement that a path, a preview,
or a summary will be refused.

**And that timing is the part worth keeping.** `#605` landed on 2026-08-26 at 13:39. The
fourth occurrence was on 2026-09-01 at 05:51 — **six days after the fix was on `main`**. So
the prompt change cannot by itself explain why the lane works now; something about that
particular run was still running the old contract. The most probable explanation is a stale
*deployed* copy (the run that finally succeeded came after an explicit `git pull` +
`build.py`, and this workspace produced two independent stale-deploy findings the same day),
but that was not captured at the time and is **not** proven here. It is written down as the
open question it is, rather than rounded off into a fix narrative.

**Evidence it is not reproducing.** The `GE-122d-1` fast-lane run later on 2026-09-01 cleared
the context-bundle phase and carried a connected set all the way to a merged PR (`#682`,
squash `8cc9fe3cf`). That is a completed run, which is the only evidence that counts here —
three halts in a row were what opened this entry.

**What would reopen it.** A single reference-state halt on a bundle whose artefact measures
clean, as above. If that happens, do not re-file: reopen this entry, and treat the
prompt-level mitigation as exhausted — at that point implement the pass-by-path contract,
because the second failure of a behavioural instruction is evidence the instruction is not the
right mechanism.

**Pattern:** a gate whose only passing path requires an agent to do something agents do not
reliably do — so the guard is sound and the workflow is still unpassable. The mitigation
narrows *how often* the model declines the ask; it leaves intact the fact that the lane's
correctness depends on it complying.

---

### KI-BO-20260826-1332 — The fast lane reads `work_status: todo` as "nobody has built this", but it only means "not on main", so it silently rebuilds work that already exists on an unmerged branch

> **Timestamped id** — `KI-<COMPONENT>-<YYYYMMDD>-<HHMM>`, minted at authoring time. This
> entry was authored as `KI-BO-029`, renumbered to `KI-BO-030` when 029 was taken mid-review,
> and 030 was then taken too. See the convention note on
> `KI-BP-20260826-1331` in `build-pipeline.md` for why sequential numbering was abandoned for
> new entries. This is `KI-BO-024`'s predicted failure, observed eight times in one day.

- **Severity:** medium
- **Status:** open — no AC
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/build_orchestration/fast_lane.py` `select_connected` · the Resolve and
  Claim phases of `templates/workflows-js/fast-lane-ship.js`

**Symptom.** Observed live on a `/fast-lane-build BP-1100b-5` run. The lane resolved cleanly
(`{"ac_ids": ["BP-1100b-5"], "message": "1 to build"}`), claimed the criterion, assembled a
context bundle, and dispatched a test-writer that produced 11 failing behavioural tests
against a hook it described as one "which does not exist yet".

It does exist. `EPIC-BuildPipelinePhantomRemediation`, commit `a64100fd` (2026-08-19):

```text
feat(build-pipeline): presence-only assertions stop counting as coverage
                      (BP-1100b-4, BP-1100b-5, BO-1000c-1a)
```

carrying `templates/scripts/commit_guardian/check_presence_only_assertions.py`,
`_presence_only_scanner.py`, its `commit_guardian.json` registration, and
`unit_tests/commit_guardian/test_bp_1100b_5.py`. `git branch -a --contains a64100fd` returns
that one local branch: never pushed, never merged, six days old.

**Root cause — `todo` is being read as a claim about the world when it is a claim about
`main`.** `work_status` is reconciled when work merges. That makes `todo` mean exactly "no
merged commit satisfies this", which is the correct and useful thing for it to mean. The lane
treats it as "no work exists", which is a different proposition and is false whenever a
branch is in flight. With **58 worktrees** in this workspace (`git worktree list`) and
unmerged local branches routine, the gap between those two readings is not a corner case.

Nothing in the resolve or claim path looks at branches, worktrees, or anything outside the AC
store.

**Correction — the claim does not serialise concurrent lane runs either.** An earlier draft of
this entry said it did, and set that aside as a separate working mechanism. That is wrong, and
the same run disproves it. The claim is written as an **uncommitted edit to the AC YAML inside
the lane's own fresh worktree**:

```text
lane worktree:  work_status: in_progress     (modified, unstaged, never committed)
origin/main:    work_status: todo
```

The lane cuts a private worktree from `origin/main`, flips `work_status` there, and never
commits or pushes that flip — the run halted before its commit phase, and there is no earlier
commit of the claim. So the claim is invisible to every other worktree. Two lane runs aimed at
the same criterion from two worktrees would each read `todo` from their own checkout and both
proceed. The mechanism serialises a lane against *itself within one worktree*, which is not a
condition that arises.

That makes the scope of this entry wider than first written: the lane cannot detect prior work
from **any** source — unmerged branches, sibling worktrees, or another concurrent lane.

**How it surfaced, and why that is the concerning part.** It was not caught by the lane. It
was caught incidentally, while diffing the deployed `commit_guardian/` directory against a
scratch build for an unrelated reason (KI-BP-20260826-1331) — `check_presence_only_assertions.py`
appeared in the deployed tree and on no merged branch, which is what prompted the search. Had
that diff not been run for other reasons, the lane would have opened a PR duplicating six-day-old
work and nothing in the pipeline would have said so. The reviewer would have had no signal
either: the PR is self-consistent and its tests genuinely pass.

**Why medium rather than high.** It wastes a build and risks a competing-solution merge, but
it does not produce a false green — the duplicate implementation is real, tested, and honest
about what it does. The damage is duplicated effort plus two divergent implementations of one
criterion, which is a merge problem rather than a correctness one. It becomes high if a lane
run ever *closes* an AC that a better unmerged implementation already satisfied, since the
store would then record `done` against the weaker of the two.

**Fix direction.** Cheapest useful version: before claiming, run `git log --all -S "<ac-id>"`
(or search `implemented_by` back-references across refs) and surface any commit outside
`origin/main` that names the target criterion — as a warning the operator must acknowledge,
not a hard block, since a stranded branch is often exactly what should be superseded. A
stronger version reads `git worktree list` and greps sibling worktrees for the AC id, which
also catches work that was never committed at all. Either way the requirement is only that
the lane *says* what it found; deciding between fresh-build and salvage is a human call and
should stay one.

Worth noting the same blind spot applies to `/build-ac` and to `ac_prioritizer.py`, which rank
and select on the same field. This is filed against the fast lane because that is where it was
observed, not because it is confined there.

**Pattern:** a field that answers one question precisely, consumed as though it answered a
broader one — the store is not wrong, the reading is.

**Related.** KI-BP-20260826-1331 (the deployed-tree collage, whose evidence surfaced this).
KI-BO-015 and KI-BO-017 (other cases of the lane reasoning incorrectly about worktree and
branch state).

---

### KI-BO-20260826-1333 — Nine of a file's ten tests asserted only that strings were present in the source they covered — so the AC looked comprehensively covered because coverage was measured by count

- **Severity:** high
- **Status:** **closed in source** — fixed and merged 2026-08-26, PR #573 (squash `d97eb399`).
  **Not yet closed at the point of use** — see the deployment caveat below.
- **Occurrences:** 1
- **First seen:** 2026-08-26 · **Last seen:** 2026-08-26
- **Where:** `unit_tests/workflows/test_bo_1000c_1a.py` (nine of its ten tests, pre-#573)
  against `templates/workflows-js/finalize-feature.js` · AC `BO-1000c-1a`

**Correction — it was nine of ten, and the tenth is the entry's best evidence.**
`test_ac2_no_overwrite_of_journal_file` asserts `assertFalse(_OVERWRITE_JOURNAL_ANTI_PATTERN
.search(js))` — an **absence** assertion, not a presence one. It is also precisely the one of
the ten that **survives** the corrected source: the observed run was 9 failed, 1 passed, and
the one that passed is the one shaped differently.

That turns this entry's countermeasure from a proposal into a measurement. The argument below
is that absence assertions hold where presence assertions rot; the file already contained one
of each kind, and under a change that deleted the mechanism, the nine presence assertions all
demanded it back while the single absence assertion stayed correct. The evidence was in the
original test run and went unremarked.

**Deployment caveat — "closed" means closed on `main`, and that is not the same thing.**
Hours after `d97eb399` merged, the deployed copy still contained the deleted mechanism:

```text
grep -c "appendJournal\|require(" .leafcutter/workflows/finalize-feature.js  ->  4
```

The source is fixed; the tree that actually runs is not. Any finalize run launched from this
workspace still executes the `require('fs')` version.

This is `KI-BP-20260826-1331` demonstrating itself on the very fix that closed this entry, filed in the
same pull request — which is a sharper illustration than either entry could give alone. It
also sets a precedent worth adopting: in this repository, **"fixed and merged" is not
sufficient grounds to call a defect closed**, because the deployed surface is not derived from
`main`. A status line saying `closed` without naming which tree it refers to is the same
category of claim as an AC marked `done` on a test that never executed.

**Symptom.** `BO-1000c-1a` ("background finalize appends each progress line to a durable,
pollable run-progress journal as it happens") read `work_status: done` while its mechanism had
never once executed. `appendJournal()` obtained Node's `fs` module through `require('fs')`. The
E2 engine injects only `agent`, `parallel`, `pipeline`, `phase`, `log`, `args`, `workflow` and
`budget` into a workflow body — there is no module loader (ADR-030). The call therefore threw
on **every** invocation, a surrounding `try`/`catch` logged a WARNING, and the run reported
success. No journal file was ever written.

**Why this is a fourth concentration and not another instance of the first.** `KI-BO-028` names
three concentrations behind the phantom-dones the 2026-08-25 triage found: presence-only
assertions over JavaScript source (M1), population-vs-change scoping (`KI-CG-001`), and a
producer never round-tripped through its consumer (`BO-2200c-5`). This is a fourth, and the
distinction from the first is the whole point:

| | the grep-only concentration (`KI-BO-008`, `BO-2400f-10`) | this |
|---|---|---|
| Scope | an *individual* presence assertion propping up an individual AC | an *entire file* — ten of ten tests |
| Shape | a weak test among stronger ones | presence-only **is the file's design** |
| How it reads | one thin test, visible as thin to anyone who looks | comprehensive: a ten-test suite for one criterion |

Every one of the ten read `finalize-feature.js` as text and asserted that `appendJournal`,
`journalPath` and `fs.appendFileSync` were **present**. All ten passed for the entire life of
the defect, because the strings were there and the code never ran. Run against the corrected
source, **9 of 10 fail** — each one demanding that the dead mechanism be put back.

That is the failure the count hides. An AC covered by one grep looks under-tested. An AC
covered by ten tests looks thoroughly tested, and the only way to see otherwise is to read all
ten and notice they are the same assertion ten times. Coverage measured by test count is
maximally misleading exactly here: the reviewer's normal heuristic — "does this have tests?" —
returns the wrong answer with more confidence the larger the suite is.

**The countermeasure, which generalises.** The replacement is a single **absence** assertion:
the corrected source is asserted *not* to contain the known-broken pattern. The asymmetry is
why it works.

- A **presence** assertion stays green on dead code. That is exactly what happened here.
- An **absence** assertion fails the moment the pattern returns — whether or not it is reached
  at runtime, and whether or not it is wrapped in a swallowing `try`/`catch`.

That last clause is why a behavioural test cannot substitute. An inert reintroduction of
`require('fs')` inside a catch-all changes no observable dispatch: the run still succeeds, the
journal still is not written, and every behavioural assertion about the workflow's output still
passes. There is nothing for a behavioural test to observe. The only available signal is the
text of the source, and the only useful thing to assert about it is that the pattern is gone.

This is the same class `BP-1100b-5` exists to catch mechanically — presence-only assertions
ceasing to count as coverage. `BP-1100b-5` is still `todo` on `main`, and per `KI-BO-20260826-1332` a
complete unmerged implementation of it has existed on a local branch since 2026-08-19. Until it
lands, absence assertions are hand-written per defect.

**Two corrections landed with the fix, both worth recording.** The AC's *title* still described
the deleted mechanism and contradicted its own amended criteria — scanners and readers surface
the title, not the Gherkin, so a title promising the opposite of its criteria is its own
phantom-done vector. And `work_status` went `done` → **`in_progress`**, not `done`: only 1 of
the 5 declared `test_spec` descriptors is implemented, the other four needing a vm-sandboxed E2
harness that does not exist on `main`. Closing it would have minted a fresh phantom-done while
repairing one.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M1 (a test that greps for a string
instead of exercising the behaviour), in its whole-suite form — where the number of tests is
itself the thing that makes the gap invisible.

**Related.** `KI-BO-028` (the triage this extends; `BO-1000c-1a` is recorded in its addendum as
the sweep's nineteenth phantom-done). `KI-BO-008` (a structural test making code comments
load-bearing — the individual-test form of the same mechanism). `KI-BO-20260826-1332` (why the
`BP-1100b-5` implementation that would catch this mechanically is invisible to the store).

---

### KI-BO-20260901-0920 — The commit-phase serialization lock is specified, its helper script was never written, and the workflow that inherited the responsibility does not take a lock at all — so N tickets commit concurrently into one shared index

- **Severity:** medium — **downgraded from high after the predicted failure did not occur.**
  The lock is genuinely absent; a second, unrelated convention is currently preventing the
  damage. See "Why nothing broke" below, which is the most useful part of this entry.
- **Status:** open — no AC
- **Occurrences:** 1 (found by inspection during the `EPIC-TheNumberingGuaranteeHoldsAtEveryStage` drive, then **observed directly in the same run** — see "Observed, not just reasoned about" below)
- **First seen:** 2026-09-01 · **Last seen:** 2026-09-01
- **Where:** `templates/workflows-js/build-feature.js` (batch dispatch, `BATCH_SIZE = 12`) ·
  `templates/skills/building-epics/SKILL.md` §5 · `scripts/epic_lock.py` (absent)

**Symptom.** `/build-feature` dispatches every ticket in a dependency batch through
`parallel()` into **one shared worktree**, and each of those parallel ticket drives runs its
own `commit` phase. Nothing serialises them. In the run that surfaced this, batch 1 held four
tickets, so four `commit` agents were on course to `git add` and `git commit` against the same
index concurrently.

**The lock is absent in three independent places, which is why no single fix closes it.**

1. **The spec describes it.** `building-epics` §5 defines a commit-phase serialization lock at
   `<worktree_root>/.epic-commit-lock`, and opens with the correct reasoning: "The commit and
   pull-request phases mutate the git index and `HEAD`; they cannot run concurrently across
   sibling tickets in the same worktree."
2. **The prescribed helper does not exist.** §5.2 says to acquire via
   `python3 scripts/epic_lock.py --acquire ...`. That file is present in neither `scripts/`
   nor `templates/scripts/`. It is named in approved criteria and has never been written.
3. **The holder is no longer dispatched.** §5 assigns the lock to `ticket-supervisor`. ADR-006
   flattened the chain, and `build-feature.js` now states plainly: "No ticket-supervisor is
   dispatched here." Its inlined phase loop contains no lock of any kind — a grep for `lock`
   across the file returns only the word `block`.

So the responsibility was transferred without the mechanism, to a caller that never had one,
backed by a helper that was never built. §5 still reads as though it is in force.

**Observed, not just reasoned about.** This entry was opened from a code read, and the
predicted state appeared in the same run minutes later. Mid-drive, with batch 1's four tickets
in flight, the shared index held staged changes belonging to two different tickets driven by
two different agents:

```text
$ git diff --cached --name-only          # first poll
tickets/00_inbox/epics/EPIC-.../01_TICKET-20260825-GE-122d-1.md
tickets/00_inbox/epics/EPIC-.../08_TICKET-20260825-GE-122e-2.md

$ git diff --cached --name-only          # ~4 minutes later, still no commit
tickets/00_inbox/epics/EPIC-.../01_TICKET-20260825-GE-122d-1.md
tickets/00_inbox/epics/EPIC-.../03_TICKET-20260825-GE-122d-3.md
tickets/00_inbox/epics/EPIC-.../08_TICKET-20260825-GE-122e-2.md
```

No agent had committed at either sample. The window is not theoretical and not narrow: it
stayed open across two polls minutes apart, and it *widened* — the index accumulates staged
work from each ticket as that ticket's sign-off phases run, so exposure grows with batch size
rather than being a brief race at commit time. `BATCH_SIZE = 12` makes the worst case twelve
tickets deep.

What a commit landing in that window actually did is recorded under "Why nothing broke" below
— the outcome was **clean**, for a reason unrelated to the lock.

**Why the failure is silent rather than loud.** The obvious hazard — two `git commit`
invocations colliding on `index.lock` — is the *safe* one: git fails that loudly and the phase
reports an error. The damaging interleaving is quieter:

```text
agent A: git add <A's files>
agent B: git add <B's files>
agent A: git commit          <- commits A's files AND B's
agent B: git commit          <- "nothing to commit", or commits a fragment
```

A's commit would then contain B's work under A's message. That would defeat the repo's
commit-message-matches-diff rule mechanically rather than by author error, and strand B's
ticket with its changes committed under someone else's traceability. `check-commit-scope` is
**warn-only**, so it would observe this and not stop it.

**Why nothing broke — and why that is not the same as being safe.** The run reached a commit
with three *other* tickets' files sitting staged, and produced a clean single-file commit:

```text
$ git show --stat d6a7fe470
 .../10_TICKET-20260825-BP-900h-6.md   | 477 +++++++++++++++-
 1 file changed, 458 insertions(+), 19 deletions(-)

$ git status --short          # immediately after — the other three are STILL staged
M  .../01_TICKET-20260825-GE-122d-1.md
M  .../03_TICKET-20260825-GE-122d-3.md
M  .../08_TICKET-20260825-GE-122e-2.md
```

The `commit` agent commits by explicit pathspec, so it took its own file and left the rest of
the index alone. That is what saved the run, and it is worth recording plainly: **the
prediction above did not come true, and the reason is a convention in a different component.**

What that changes, and what it does not:

- **It does not restore the guarantee.** `commit.md` §"Never run `git add -A` / `git add .`.
  Stage by name" is prose in an agent template. Nothing enforces it, no test asserts it, and
  the driver does not depend on it — it simply happens to hold. A single commit path that
  omits the pathspec reintroduces the whole failure, and the autofix retry loop (`commit.md`
  Step 5, "re-stage the changed files") is exactly the kind of place where that is easy to
  get wrong.
- **It narrows the severity but not the surface.** Two independent mechanisms would both have
  to be correct forever for this to stay safe, and only one of them is written down as a
  requirement. The lock exists precisely so correctness does not depend on every future
  commit path remembering to scope itself.
- **It makes the `pull-request` half untested.** §5 covers commit *and* pull-request. The
  pull-request phase is deferred for epic members (`isEpicMember=true`), so this run never
  exercised concurrent `HEAD`/branch mutation at all. The observation above says nothing
  about that path.

Recording the non-occurrence matters as much as the occurrence would have: an entry claiming
a corruption that never materialises gets dismissed on the next read, and the real finding —
a missing control masked by an unenforced convention — gets dismissed with it.

**Why it has not been seen before.** The exposure needs a batch with two or more tickets whose
`files_touched` are disjoint enough to pass the parallelism gate — which is exactly the case
the gate is designed to *produce*. The better the batching works, the wider the window. Drives
that happened to yield single-ticket batches were never at risk, so the absence of prior
occurrences is not evidence of safety.

**Detection.** After any multi-ticket batch, verify each commit against its ticket rather than
trusting the drive's payload:

```bash
git -C <worktree> log --format="%h %s" --name-only <base>..HEAD
```

Every file in a commit must appear in that ticket's `files_touched`. A commit carrying a
sibling ticket's files is this defect, already realised.

**Countermeasure.** Two candidates, and the cheap one is worth taking first:

- **Set `BATCH_SIZE = 1`** — costs the parallelism but restores serial commits with a
  one-token change, and needs no new script. The dependency batching still does its work;
  only the within-batch concurrency is given up.
- **Write `scripts/epic_lock.py` and call it** from `driveTicketPhases` around the `commit`
  and `pull-request` phases, per §5.2. This is the specified fix, and it also closes the
  dangling reference in §5 that currently points at a non-existent file.

Whichever is chosen, §5's own caveat should be honoured: it already warns that the lock
"cannot be released after a child crash (lock-recovery requires user intervention)". A lock
added without stale-lock recovery converts a silent corruption into a permanent deadlock.

**Pattern:** `docs/reference/false-green-mechanisms.md` → a control specified in a runbook,
absent in the code path that inherited the runbook's responsibility. The document asserting
the guarantee is the reason nobody checks for it.

**Related.** `KI-BO-030` (the fresh-install blocker set, which also turns on a gate that is
registered but cannot run). The user-memory note "No parallel supervisors in shared worktree"
records the same hazard observed from the opposite direction — git object-store corruption
under concurrent supervisors — and predates this entry by months without the mechanism being
traced to a missing lock.

---

### KI-BO-20260901-1000 — The per-ticket phase list is frozen before the first phase runs, so a phase that a later phase declares necessary can never be dispatched — and `architect-review`, whose job is to declare exactly that, is ordered after the phases it gates

- **Severity:** blocker
- **Status:** open — no AC
- **Occurrences:** 1 run, **2 of 4 tickets in the batch** (`GE-122d-3`, `BP-900h-6`) — both halted, neither recoverable within the drive
- **First seen:** 2026-09-01 · **Last seen:** 2026-09-01
- **Where:** `templates/workflows-js/build-feature.js` — `driveTicketPhases()` Step 2/Step 3
  (`neededPhases` computed once at ~:1345, iterated at ~:1430) · `phaseOrder` (~:305)

**Symptom.** Two independent tickets in one batch halted with the same shape: `architect-review`
ran, concluded an ADR was required, flipped `requires_adr: true` and set
`agents.adr-author: needed` — and `adr-author` was then never dispatched. `python-coder`
subsequently refused to write code against a contract that had not been recorded, which is the
correct refusal, so the drive ends with two tickets stuck behind a phase the drive itself will
never run.

**Root cause — the list is a snapshot, not a queue.** Step 2 computes the phase list exactly
once, from the planner's opening snapshot:

```js
const neededPhases = sortByCanonicalPriority(
  selectDispatchPhases(orderedPhases.filter((p) => p.status === "needed"), isEpicMember)
);
```

Step 3 then walks it:

```js
for (const currentPhase of neededPhases) {
```

`neededPhases` is never recomputed. A phase promoted to `needed` *during* the drive is
invisible to the loop, because the loop is iterating a value captured before any phase ran.

**Two orderings make this specifically unrecoverable rather than merely late.** `phaseOrder`
puts `adr-author` at priority 2 and `architecture-diagram-author` at 3, but `architect-review`
— the phase that decides whether either is needed — at 4. So even if the list *were*
recomputed, a forward-only walk would already be past both slots by the time the decision is
made. The gating phase runs after the phases it gates. Freezing the list and ordering the
decider last are two independent bugs that happen to produce one symptom; fixing either alone
leaves the other.

**The signal is computed correctly and then discarded.** This is not a case of the system
failing to notice. The driver re-reads the ticket record after each phase, and those re-reads
returned the right answer — from this run's own journal, after `architect-review` signed off:

```text
"needed_phases":["ac-fulfillment-gate","ac-validator","adr-author","commit",
                 "documentation-expert","documentation-verifier","pr-reviewer",
                 "pull-request","python-coder","test-runner","test-writer"]
```

`adr-author` is right there, named, in a value the driver received and parsed. Nothing consumes
it. The read-back exists to feed the *completion* decision, not the *dispatch* decision, and no
code path connects the two. This is the fourth recorded instance in this register of a signal
being derived accurately and then not wired into the control flow it was derived for.

**Why the phase agents look worse than they are.** Both halts were well-reasoned and both were
right. `python-coder` on `GE-122d-3` verified ADR-037's status on disk rather than from memory,
found it `Proposed` with no amendment, noted six sibling ACs already consuming the
`NamespaceVerdict` shape it would have had to narrow, and stopped. `python-coder` on
`BP-900h-6` checked that `ADR-038` did not exist and cited architect-review's explicit
sequencing instruction. `test-runner` then re-derived the same blocker independently and
confirmed the red baseline was intact under `AC_ENFORCE_STRICT=1` (7 failed, matching
test-writer's record) rather than reporting a regression. The adjudication ladder classified
correctly at every step. The agents did their jobs; the driver had no way to act on the result.

**Countermeasure.** Both halves need addressing:

1. **Re-derive the pending set each iteration** instead of iterating a frozen array — drive
   from the record's live `needed` set, so a phase promoted mid-drive is picked up. The
   re-read already happens and already carries the answer; it needs connecting to dispatch.
2. **Move `architect-review` ahead of the phases it gates** in `phaseOrder`, or give
   `adr-author` and `architecture-diagram-author` a second slot after it. A decider that runs
   after the phases conditioned on its decision cannot work under any forward-only walk.

Until then, a ticket whose `requires_adr` is flipped by `architect-review` cannot be completed
by `/build-feature` and must be finished by hand — author the ADR, then re-drive.

**Pattern:** `docs/reference/false-green-mechanisms.md` → a correctly-computed signal with no
consumer. Distinct from the phantom-done family: nothing here claims success. The drive halts
honestly and reports the blocker; the defect is that the blocker is one the drive created for
itself and cannot clear.

**Related.** `KI-BO-20260901-0920` (filed the same run — the commit-phase lock, also a control
that the runbook describes and the flattened driver does not implement; ADR-006's flattening
dropped both). `KI-ACD-020` (a readiness gate dropping leaves silently — the same
computed-then-discarded shape one layer up, in `goal_to_epic.py`).

---

### KI-BO-20260901-1052 — `python-coder` signals a test handoff exactly as its template prescribes, and the driver rejects it for omitting a field the template never mentions — so the documented delegation path dead-ends every ticket that uses it

- **Severity:** high
- **Status:** open — no AC
- **Occurrences:** 1 (the only ticket in the batch that produced working production code)
- **First seen:** 2026-09-01 · **Last seen:** 2026-09-01
- **Where:** `templates/agents/python-coder.md` §"Test Delegation" (~:454-460) ·
  `templates/workflows-js/build-feature.js` (~:1595-1610)

**Symptom.** `GE-122d-1` was the one ticket in batch 1 that got real work done — a verified
77-line deploy-manifest fix in `scripts/build_phases.py`, checked against a live `build.py`
run. The drive then discarded the ticket with:

```text
Phase 'python-coder' returned 'status: handoff' but named no recognizable
handoff_target ('undefined'). Refusing to guess a re-dispatch target and refusing
to advance to the next phase in phaseOrder.
```

**The two sides define "handoff" differently, and neither references the other.**

`python-coder.md` §"Test Delegation" is unambiguous about the protocol, and the agent followed
it to the letter:

> 1. Add task items under the `### test-writer` section of `## Implementation Tasks`
>    describing what needs testing.
> 2. When signing off, use `(status: handoff)` instead of `(status: ok)` to signal that
>    test-writer must run next.
> 3. Do NOT create files under `unit_tests/` or any test directory.

Three steps, all performed. The target is named — in the ticket body section and again in the
returned `message` ("handed off to test-writer via a new `## Implementation Tasks` /
`### test-writer` section with the exact fix"). What the template never asks for, anywhere, is
a `handoff_target` key in the JSON return. The driver reads exactly that key and nothing else:

```js
const handoffTarget = phaseResult.handoff_target;   // undefined
```

So the agent communicated the target through the two channels its template defines — ticket
body and prose — and the driver looked in a third channel it was never told to populate.

**Why the driver's refusal is right and still produces the wrong outcome.** Refusing to guess
a re-dispatch target is correct; guessing would be worse. The defect is upstream of the
refusal: the contract the agent was given cannot produce the field the driver requires. A
fail-closed check is only as good as the contract it closes against, and here it fails closed
on conformant output.

**This is the documented happy path, not an edge case.** §"Test Delegation" exists because
`python-coder` is forbidden from writing tests: "You MUST NOT write or modify unit test files
directly." Any coder run that discovers its tests need adjusting — which the same template
makes *mandatory* for bug fixes ("every bug fix requires a regression test... add the test
requirement to the `### test-writer` section") — is routed into `status: handoff`. So the
prescribed route for a common, template-mandated situation terminates the ticket.

**What it cost.** `GE-122d-1`'s fix was complete and verified; 4 of its 6 red-baseline tests
remained red for a diagnosed test-fixture path bug (the fixture assumed a bare
`<target>/hooks/`, contradicting ADR-004's shim design) that `python-coder` correctly
classified as `test_drift` and correctly declined to fix itself. That is the system working
as designed right up to the moment the handoff was dropped. The work survives only because it
was left staged — nothing committed it, and nothing recorded that it exists.

**Countermeasure.** Make the two ends agree, in whichever direction is cheaper:

- **Have the driver accept the template's channel** — read the handoff target from the
  ticket's `## Implementation Tasks` subsection heading when `handoff_target` is absent,
  before refusing. The information is already on disk in a structured, parseable place.
- **Or add the field to the template contract** — state in §"Test Delegation" that the JSON
  return must carry `handoff_target: "test-writer"`, and add it to the result schema so a
  missing value is caught at authoring time rather than at dispatch time.

Either fixes it; doing neither leaves the delegation path unusable. The first is preferable
because it makes the *record* authoritative, consistent with how every other phase decision
in this driver is taken from the ticket read-back.

**Pattern:** `docs/reference/false-green-mechanisms.md` → a contract split across two
components with no shared definition and no test spanning both. The agent template and the
workflow are versioned together and deployed together, and still disagree.

**Related.** `KI-BO-20260901-1000` (same run, same driver, also a dispatch decision that
ignores what the ticket record already says). Both are instances of the driver's dispatch
logic and the ticket record having drifted apart; the record is right in both cases.

---

### KI-BO-20260826-1900 — The done-proof gate collects parametrized pytest ids and then cannot match one, so a covers-tagged parametrized test reads as "not run" and blocks the merge

- **Severity:** medium
- **Status:** open — no AC
- **Occurrences:** 1
- **First seen:** 2026-08-26 · **Last seen:** 2026-08-26
- **Where:** `scripts/ac_store/done_proof.py` — `_find_nodeid_for_test` (lines 1000-1006)
  against the result-line regex at line 103. Surfaces through the **required** CI check
  `Proof-of-done coverage check (BO-2500b)` and the `check-done-proof` pre-commit hook.

**Symptom.** `BO-2400c-1-vii` was covered by a passing, correctly `# covers:`-tagged test.
The required CI check failed anyway:

```text
[check-done-proof] BO-2400c-1-vii: linked test not run:
  unit_tests/workflows/test_bo2400c1vii_reference_examples.py::
  test_ac1vii_each_documented_example_executes_against_the_real_function
```

The test existed, was tagged, ran, and passed. The only thing unusual about it was
`@pytest.mark.parametrize`.

**Cause, and the reason it is a defect rather than a missing feature.** The two halves of the
gate disagree about what a nodeid looks like.

- The result parser at line 103 matches
  `^(\S+::test_\w+(?:\[.*?\])?)\s+(PASSED|FAILED|…)` — the `(?:\[.*?\])?` group means it
  **deliberately captures** parametrized ids such as `::test_foo[0]` into the results dict.
- The lookup at lines 1000-1006 builds `suffix = f"::{func_name}"` and accepts a nodeid only
  when `nodeid.endswith(suffix)`. A parametrized id ends `::test_foo[0]`, never `::test_foo`.

So the scanner goes to the trouble of collecting parametrized results, and the matcher is
structurally incapable of finding any of them. Both fallback loops at 1001 and 1004 use the
same `endswith`, so neither rescues it.

**Why this bites hard.** The verdict is `not run`, which is the gate's *fail-closed* wording
for "the pytest run never reached this test" — a phrase that sends the reader looking for a
collection error, an import failure, or a skip. None of those is happening. The test ran and
passed in the very same pytest invocation whose output the gate just parsed.

It also arrives late and asymmetrically. The pre-commit hook and the CI job disagree in
practice: at commit time the hook passed for this branch, and CI failed. Reproducing the CI
result locally requires the exact invocation *and* the right working directory —

```bash
env --chdir=<worktree> python scripts/commit_guardian/check_done_proof.py \
  --mode ci-changed --base origin/main --test-root .
```

— because run from outside the repo it exits 0 and reports nothing, which reads as a pass.
That is the `KI-BP-*` "silence is not a pass" shape again: a gate invoked slightly wrong is
indistinguishable from a gate satisfied.

**Consequence for authors.** Parametrization is the natural shape for any AC of the form "each
of N cases must hold" — precisely the ACs most worth testing thoroughly. Today that shape is
unmergeable when the test carries a `# covers:` tag, and nothing tells the author why. The
silent workaround is to write N near-duplicate functions; the *quiet* workaround, and the
dangerous one, is to drop the `# covers:` tag to get the gate to stop complaining, which
removes the AC's proof entirely while turning the check green.

**Fix.** Match the parametrized form in the lookup — accept a nodeid when it equals
`::func_name` **or** starts with `::func_name[`. Because parametrization means one tag maps to
many nodeids, the pass/fail rule needs a decision at the same time, and the safe one is: every
matching nodeid must pass, so a single red case still fails the gate. A `next()`-style
first-match would let a green `[0]` mask a red `[1]`, which converts this bug into a
false-green — strictly worse than the current fail-closed behaviour. Whoever fixes it should
also reconcile the hook and CI paths, since the two currently disagree on the same commit.

**Workaround in force.** `unit_tests/workflows/test_bo2400c1vii_reference_examples.py` uses
three named functions over a shared helper rather than one parametrized test. Both the module
docstring and the helper name this KI and say not to collapse them back until the gate matches
parametrized ids — the constraint is recorded where someone would otherwise reintroduce it,
not only here.

**A second, narrower gap found in the same investigation, not yet its own entry.** The gate's
only exemption from requiring a covers tag is the composite one (`BO-2500a-6`: an AC whose
`covered_by` is non-empty derives proof from its children). There is no exemption for a **leaf**
declaring `test_required: false`. Such a record can therefore never be marked `done` — the
schema permits the declaration and the gate refuses its consequence. That deserves care rather
than a quick exemption: `test_required: false` is exactly the escape hatch a phantom-done would
reach for, so the right answer is probably to require the field be justified in
`test_rationale` and reviewed, not to make it a silent bypass. Recorded here so the next person
meets both halves at once. (In this instance the correct resolution was not an exemption at
all: the record's `test_required: false` was simply wrong, and executing the documentation
page's own examples turned out to be a real behavioural test.)

**Pattern:** `docs/reference/false-green-mechanisms.md` — adjacent to, but not an instance of,
the presence-only family. This one fails *closed*, so it costs merges rather than hiding
defects; the false-green risk is in the two tempting fixes (drop the tag; first-match wins).

**Related.** `KI-BO-20260826-1332` (the store's `work_status` disagreeing with reality — same
theme of a gate reading a proxy rather than the thing itself). `KI-ACS-001` (a validation run
that reported clean because it was invoked in a way that checked nothing).

---

### KI-BO-20260831-1330 — The fast lane invokes `assemble-bundle` with two flags that were deliberately deleted, so its context-bundle gate can never be satisfied

- **Severity:** blocker
- **Status:** **RESOLVED 2026-09-01** — the two flags are gone from the lane. Verified:
  `grep -c "conventions\|--acs" templates/workflows-js/fast-lane-ship.js` returns **0**, and a
  live run reached its coder phase with a 20,645-byte bundle. Fixed as part of the `BO-2400c-1-vi`
  bundle shrink (the layer set was reduced, which removed the two invocations along with the
  layers they passed), so it was closed incidentally rather than deliberately — which is why it
  sat here reading `blocker / open` after it had stopped being true.
  **Left as a warning:** a stale blocker is not harmless. This entry was the top of the severity
  list when the register was consulted on 2026-09-01 to decide what to build next, and it
  displaced two real ones. Re-verify a blocker before planning against it.
- **Occurrences:** 1
- **First seen:** 2026-08-31 · **Last seen:** 2026-08-31
- **Where:** `templates/workflows-js/fast-lane-ship.js`, the `context-bundle` phase's Step 2
  invocation; `injection_builders.py` `assemble-bundle` argparse surface

**Symptom.** `/fast-lane-build INF-700b-2` halts:

```
status: blocked
failing_phase: context-bundle
context_bundle_state: incomplete
"The context bundle was obtained but is incomplete: the cache breakpoint marker
 is absent, or one of its layers is empty."
```

`obtained: true`, `bytes: 10287`. The content came back — this is **not** the pointer-instead-of-content
failure in `KI-BO-20260826-1214`. The bundle is genuinely incomplete.

**Cause.** The workflow's Step 2 tells the phase agent to invoke `assemble-bundle` with
`--conventions` and `--acs`. Those flags **do not exist**. `BO-2400c-1-vi` removed them
deliberately — not made optional, *removed* — so a caller cannot reintroduce the two largest
duplicate layers the design retired (`conventions` duplicates the harness-injected
`CLAUDE.md`; `acs` duplicates AC records the receiving agent can read from its own
workspace). Passing either makes argparse reject the whole command.

The agent did the sensible thing: ran with the three flags that do exist
(`--architecture`, `--high-level`, `--prior-tests`) and folded a pointer to the AC store into
the `high_level` layer. The bundle assembled, exit 0, no stderr — and then failed the
completeness check, because the layer set no longer matches what the workflow validates.

**So the two halves of one feature disagree about their own interface.** `BO-2400c-1-vi`
narrowed the CLI; nothing updated the caller or the completeness contract it validates
against. Every fast-lane run for a `python-coder` AC hits this.

**Why it reads as something else.** The message says "incomplete", which invites you to
look at the layers' *content* — whether a doc was too big, whether a file was missing. The
actual fault is one directory away, in an argparse surface the workflow has no test against.
The phase agent's own report is what surfaced it, in prose, as an aside.

**Fix direction.** Reconcile the caller with the CLI, in one change, and add the test that
would have caught it: assert the workflow's invocation string only names flags
`assemble-bundle` actually accepts. Then decide whether the completeness contract should
still demand the two retired layers — it should not, and that is the substantive half.
A shared constant for the layer set, read by both the builder and the validator, removes
the class rather than this instance.

**Related.** `KI-BO-20260826-1214` (same phase, same halt, different cause: content returned
as a pointer rather than inlined — that one is about the size of the payload, this one about
the shape of the command). Both make the lane unable to ship; fixing either alone is not
enough.

---

### KI-BO-20260831-1331 — A half-created fast-lane worktree is invisible to `git worktree`, so it cannot be cleaned up and its symptom reads as store-wide corruption

- **Severity:** high
- **Status:** open — no AC
- **Occurrences:** 1
- **First seen:** 2026-08-31 · **Last seen:** 2026-08-31
- **Where:** `setup_ticket_worktree.py create-fastlane-worktree`, and the resolver's error
  message in `templates/workflows-js/fast-lane-ship.js`

**Symptom.** A fast-lane run halted at `resolve` with:

```
resolve_connected_build_set: AC id 'INF-700c-1' not found in the store at
.../worktrees/inf-700c-1/docs/acceptance-criteria
... the run also emitted ~3695 lines of "ERROR: <path>.yaml: expected a YAML mapping,
got NoneType" for effectively every AC file in that store
```

The message concludes "this looks like a store-wide corruption or wrong ac-root path".
**It is neither.** Measured:

| Check | Result |
|---|---|
| Empty `.yaml` in that worktree's store | **3695** |
| Empty objects in `.git/objects` | **0** |
| Empty `.yaml` in the main checkout | **0** |
| Empty `.yaml` in two sibling fast-lane worktrees | **0** |
| Disk usage | 3% of 1007G |

So the object store is intact and every other checkout is fine. `create-fastlane-worktree`
wrote a directory tree of zero-byte files **and a corrupt `.git` gitfile**
(`fatal: invalid gitfile format`), then failed before registering the worktree.

**The cleanup path is closed.** `git worktree list` does not contain it, so
`git worktree remove --force` refuses with *"is not a working tree"*, and
`git worktree prune` finds nothing to prune. The only recourse is to move or delete the
directory by hand. An operator following the obvious commands gets two refusals that both
look like *they* are holding it wrong.

**Why the misdiagnosis matters more than the corruption.** The blast radius of the real
fault is one throwaway worktree. The blast radius of the *message* is the whole AC store:
it points a reader at `docs/acceptance-criteria/`, which is shared, tracked, and the thing
this repo is most afraid of losing. The correct first move — check whether the git object
store is intact — is not suggested anywhere.

**Fix direction.** Make `create-fastlane-worktree` atomic or self-cleaning: if registration
does not complete, remove the partial directory before returning, and return non-zero. On
the reading side, when a store scan finds *every* file unparseable, that is evidence about
the **checkout**, not the store — the resolver should say so and check
`git -C <worktree> rev-parse --git-dir` before blaming the ac-root. Cheapest immediate
guard: have the worktree phase verify the new worktree appears in `git worktree list` and
that a known file is non-empty, before any later phase trusts it.

**Related.** `KI-BP-20260826-1331` (a shared deployed `.leafcutter/` being a collage of
whatever each worktree last wrote — same family: worktree provisioning that half-succeeds
and is believed).

---

### KI-BO-20260831-1332 — The fast lane's roster is python-coder + test-writer, so it refuses a third of the ready queue with no upstream signal

- **Severity:** medium
- **Status:** open — no AC
- **Occurrences:** 1 (3 ACs affected in one sitting)
- **First seen:** 2026-08-31 · **Last seen:** 2026-08-31
- **Where:** `templates/workflows-js/fast-lane-ship.js` roster / build-set refusal;
  `scripts/ac_store/scan_ac_store.py` ready-queue construction

**Symptom.** `/fast-lane-build INF-400b-2-ii` refuses immediately:

```
status: refused
"1 member(s) declare a deliverable or proof obligation no phase in this run's roster produces"
reason: "no phase in this run's roster produces work assigned to 'llm-expert'
         (roster: ['python-coder', 'test-writer'])"
```

**The refusal itself is good and should be kept.** It happens *before any claim or dispatch*,
names the AC, the missing producer and the actual roster, and leaves no `in_progress` state
to clean up. That is the correct shape for a gate that cannot proceed.

**The defect is upstream silence.** Nothing between the AC store and the operator says an
`llm-expert` AC is un-fast-lane-able. `scan_ac_store.py` lists them as `ready` alongside
`python-coder` ACs; `readiness: approved` says nothing about which builder can take them;
neither `/build-ac` nor the fast lane's own documentation mentions the roster. In the
`INF-400b-2-ii` / `INF-700b-1-i` / `INF-700b-1-ii` group, **3 of 9 ready ACs** were in this
category — discovered only by launching a lane at each and reading the refusal.

There is a second-order cost. `INF-400b-2-ii` is assigned `llm-expert` *and* carries six
`test_spec` descriptors, so it is not routable to a single agent at all: `llm-expert` cannot
write `.py`, and `test-writer` does not own template prose. It needs two agents in sequence,
which the fast lane has no shape for. Driven by hand, this inverted TDD order — the
implementation necessarily landed before its tests, and a red baseline had to be recovered
afterwards by stashing the production diff.

**Fix direction.** Cheapest useful step: have `scan_ac_store.py` report the assigned agent
per ready AC (it already reads the field) and let the operator filter, or add a
`--fast-lane-eligible` flag that applies the roster. Better: publish the roster as data the
store can read, so eligibility is derived rather than discovered by refusal. Separately,
decide whether an AC whose implementation surface is prose but whose proof surface is Python
should be *split* at authoring time — that is a question for IT-PO's enrichment pass, not for
the lane.

**Trap.** The refusal reads as a per-AC problem ("this AC is wrong"), so the natural response
is to re-author the AC. The AC is fine. The mismatch is between the store's notion of ready
and the lane's notion of buildable, and re-authoring one record does not touch it.

---

### KI-BO-20260831-1930 — The driver deliberately drops the `pull-request` phase for an epic member, the generator emits it as `needed`, and nothing reconciles them — so every epic ticket halts the drive at completion

- **Severity:** blocker
- **Status:** open — no AC
- **Occurrences:** 3 (three consecutive drives of EPIC-StartingNewWorkTheProperWayAlways,
  each halting on a different ticket as it became the first to finish)
- **First seen:** 2026-08-31 · **Last seen:** 2026-08-31
- **Where:** `templates/workflows-js/build-feature.js:406`
  (`phases.filter((p) => p.agent !== "pull-request")`) and `:1384`
  (`deferredPhases = isEpicMember ? ["pull-request"] : []`), against
  `scripts/ac_store/generate_ticket_from_ac.py`, which emits `pull-request: needed` on every
  generated ticket

**Symptom.** An epic ticket completes every phase, then the drive halts:

```
Ticket "..." was NOT recorded complete.
0 needed phase(s) are outstanding in the ticket's own record: .
The completion write failed: Refusing to set status: done. The ticket's own
frontmatter still lists `pull-request: needed` (not among the 8 agents the
request asked me to check)...
```

Note the shape: **zero outstanding phases, and a refusal anyway.** The driver's own list is
complete; the ticket's list has one more entry.

**Cause.** Both halves are individually correct and they were never introduced to each other.

The driver *deliberately* removes `pull-request` from an epic member's phase list, because a
single epic-level PR covers every ticket on the branch. That is intentional, documented in
the source, and right. The generator, which does not know or care whether its output will
land in an `EPIC-*/` folder, writes `pull-request: needed` into every ticket it produces. So
the phase is never dispatched, no sign-off is ever written, and the completion writer — which
reads the ticket rather than the driver's phase list — correctly refuses to mark done with a
`needed` phase outstanding.

**Why blocker.** It is not one ticket, it is every ticket in every epic. Measured on the
current tree, `grep -rl "pull-request: needed" tickets/00_inbox/epics/` returns **333**
tickets spanning **23** epic folders, **316** of which are not yet done. The observed epic
contributed 25 of those 333 — it was the first to hit the halt, not the size of the problem.
The drive halts on whichever ticket finishes first, so fixing that one ticket by hand just
moves the halt to the next, which is exactly what three consecutive drives did before the
pattern was visible.

**It also cannot be diagnosed from the halt message.** The message names the ticket and the
phase, so the natural reading is "this ticket is missing a sign-off" — and the natural
response, re-running the drive, reproduces it identically because the phase the ticket wants
is the one the driver has decided not to run.

**Fix direction.** Make the generator emit `pull-request: not_needed` when the target path is
inside an `EPIC-*/` folder — the ticket then states what the system actually does, and the
Sign-offs row is omitted with it (a `not_needed` agent must not appear there). The runtime
alternative — having the driver reconcile the frontmatter when it defers a phase — is worse:
it means an agent rewriting the record to match its own behaviour, which is the shape that
makes a record stop being independent evidence.

**Workaround in use — on one unmerged branch, and nowhere else.** The 25 tickets of
EPIC-StartingNewWorkTheProperWayAlways were set to `pull-request: not_needed` by hand
(`9682d6adf`). That commit is reachable from exactly one branch:
`git branch --contains 9682d6adf -a` returns `EPIC-StartingNewWorkTheProperWayAlways` and its
remote, and nothing else. On `main` not one of those 25 is corrected and the other 308 were
never touched, so anyone reading from `main` has the defect live in full. Do not read
"workaround in use" as "the pain is handled" — it is handled on a branch that has not landed.

The reasoning behind that hand-correction is worth preserving, and holds for the branch it was
made on: it is a correction, not a suppression, because `not_needed` means "explicitly
excluded from this ticket", which is precisely what the driver does. They were NOT set
`signed_off` — no per-ticket PR phase ran, and saying one did would be false.

**Sequencing warning — the 316 must be repaired BEFORE the completion guard is unified.** A
fix is being specified that makes the completion guard consistent (`KI-BO-20260831-1932`).
Today that guard has two doors and only one of them reads the ticket, so roughly two in three
of these tickets slip past it into a phantom `done` instead of halting. That leniency is the
only reason a population of 316 is survivable at all. Once the guard is consistent **all 316
halt reliably** — which is the correct behaviour, and a large immediate operational cost that
has to be paid deliberately rather than discovered. The mechanical repair of the 316 (fix the
generator, then sweep the tickets that already exist) has to land first. Unify the guard first
and the next drive halts on ticket one of 316, with 315 behind it.

**Related.** `KI-BO-20260831-1931` (the sibling record-vs-driver disagreement, on comment
status rather than phase membership).

**Pattern:** `docs/reference/false-green-mechanisms.md` — the inverse: a gate that blocks
correctly on a record the rest of the system has already decided to ignore.

---

### KI-BO-20260831-1931 — Ticket completeness is judged from the newest per-agent COMMENT, and the driver halts before dispatching, so a stale comment blocks every future run and the record cannot heal itself

- **Severity:** high
- **Status:** open — no AC
- **Occurrences:** 2 (tickets ACD-2100a-1 and ACD-2100d-2, two consecutive drives)
- **First seen:** 2026-08-31 · **Last seen:** 2026-08-31
- **Where:** the per-ticket completeness evaluation in
  `templates/workflows-js/build-feature.js`, against the `## Comments` sign-off entries the
  `signoff` skill writes

**Symptom.** A ticket whose frontmatter reads `python-coder: signed_off` halts the drive with

```
python-coder (the latest sign-off entry for 'python-coder' in the record reads
status 'handoff', not a passing outcome)
```

The frontmatter and the newest comment disagree, and the comment wins.

**Why it is not self-correcting, which is the actual defect.** The driver evaluates
completeness *before* dispatching any phase. A run against the affected epic dispatched
**11 agents, all status-checkers, and not one phase agent** — it read the records, found a
non-passing newest comment, and stopped. So the only thing that could write a newer comment
is the phase the driver has already declined to run. A re-run is byte-identical and produces
the identical halt. The observed epic halted this way twice in a row.

**How the stale comment gets there, and the part worth internalising.** On ACD-2100a-1 the
phase had genuinely completed. A re-dispatched `python-coder` returned `status: ok` and
**deliberately wrote no comment**, reasoning that "re-writing it would duplicate/risk
corrupting a correct history". That caution is defensible in isolation and it is what left
the earlier `handoff` as the newest entry. An agent doing the careful thing created an
unrecoverable block.

**Fix direction.** Either resolve completeness from the frontmatter `agents:` map — which the
sign-off protocol already requires be kept in lockstep with the checklist — or, if the newest
comment is to remain authoritative, require a phase returning `ok` to write a comment saying
so, so "no new comment" cannot mean "still blocked". The two sources must not be able to
disagree while only one is read.

**Detection.** Compare each ticket's frontmatter `agents:` values against the status on the
newest `### <timestamp> — <agent> (status: ...)` entry for that agent. Any disagreement is
this defect. `check_ticket_signoff_parity.py` does **not** catch it — it reconciles
frontmatter against the `## Sign-offs` checklist, not against the comment log.

**Related.** `KI-BO-20260831-1930` (same class: the driver's model of a ticket and the
ticket's own record disagreeing, with no reconciliation).

---

### KI-BO-20260831-1932 — The completion guard refuses one ticket and passes another on identical conditions

- **Severity:** medium
- **Status:** open — no AC
- **Occurrences:** 1 (one drive, three tickets, split outcome)
- **First seen:** 2026-08-31 · **Last seen:** 2026-08-31
- **Where:** the completion-write step of `templates/workflows-js/build-feature.js`, and
  `scripts/set_ticket_status.py`'s agents-parity check

**Symptom.** In a single drive, with three tickets in exactly the same state — every phase
signed off except `pull-request: needed`, no sign-off entry for it — the guard **refused**
ticket 01 and **flipped tickets 03 and 20 to `status: done`**.

The refusal cited the condition explicitly: "the ticket's own frontmatter still lists
`pull-request: needed` ... Per my closing protocol I only mark a ticket done when every phase
the ticket names as needed is confirmed signed off". The other two met that description
equally and were written anyway.

**Why it matters more than the inconsistency itself.** The refusing path is the correct one.
The lenient path is a phantom-done write: it records `status: done` on a ticket the guard's
own stated rule says is not done. Whichever way this is unified, it should be unified toward
the refusal — but a guard that produces both outcomes from one condition gives no signal
about which it will do next time, so neither result can be trusted as evidence.

**A secondary consequence, observed.** Ticket 20 was flipped to `done` while its
`source_ac` (`ACD-2100d-2`) was still `work_status: todo`, which
`check-ticket-ac-status-parity` then blocked at commit time. The lenient write produced a
state a different gate had to catch.

**Fix direction.** Make the completion write take its phase list from the ticket, not from
the caller's request. Both observed paths had the same 8-item request; only one of them
went and read the ticket for a ninth.

**Why that direction, spelled out — it has already been read backwards.** Two agents read the
paragraph above on the same day and drew opposite conclusions from it, so the reasoning
belongs in the entry rather than in the reader.

Taken literally and on its own, the direction unifies both paths onto the refusal. While the
tickets still say `pull-request: needed`, that converts an intermittent blocker into a
permanent and universal one — 316 tickets, per `KI-BO-20260831-1930`. An implementer can
reasonably conclude from that alone that the direction is wrong. It is not wrong; it is
mis-ordered if taken alone. See the sequencing warning on that entry for the order.

The tempting alternative — have the completion writer trust the exclusion list its caller
hands it — must be rejected, and rejected explicitly, because it is what the obvious fix looks
like. The guard's refusal is worth something only while the record is authored by someone
other than the party being checked. A writer that accepts the drive's word about which phases
do not count has stopped checking the drive, which is the only thing it was ever for. It would
fix today's symptom by removing the guard.

The direction completes the fix only when paired with making the RECORD true — the generator
emitting `pull-request: not_needed` for epic members, per `KI-BO-20260831-1930` — so that a
writer reading the ticket gets the right answer. The two halves are a pair. Reading the ticket
without correcting the ticket halts everything; correcting the ticket without reading it
leaves a guard that trusts its caller. Neither works alone.

**Related.** `KI-BO-20260831-1930` — the `pull-request: needed` entry that put all three
tickets in this state.

---

### KI-BO-032 — `/fast-lane-build` silently builds a different batch when the AC you named is not `readiness: approved`

- **Severity:** high — the failure is a green run against the wrong work, with no signal
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-09-01 · **Last seen:** 2026-09-01
- **Where:** `templates/workflows-js/fast-lane-build.js` (hardcoded `select_batch`
  invocation) against `fast_lane.py`'s `select_batch`, which filters on `_is_approved`

**Symptom.** An operator says "fast-lane `TKT-600a-1`". `fast-lane-build.js` takes no AC
argument at all — it hardcodes `select_batch --ac-root <root> --limit <N>`, which returns
"the next N **approved** unimplemented ACs by priority". The named AC is never consulted.
If it is not `readiness: approved`, the lane builds five unrelated ACs and reports success.

Measured on the real store at `931b4beb4`:

```
select_batch    --limit 5        -> ["ACS-500g-6-i", "BP-900b-3", "BP-900g-10-i",
                                     "BP-900g-10-ii", "BP-900g-8-ii"]
select_connected --ac TKT-600a-1 -> ["TKT-600a-1"]
```

Zero overlap. Nothing in the run says the requested AC was dropped, because nothing in the
run ever received it.

**Why the readiness field cannot be relied on to prevent this.** `TKT-600a-1` has been
`readiness: draft` for its entire history — including the whole period it was
`work_status: done`. So "draft" here does not mean "not ready to build"; it means nobody
ran the approval gate. Any AC that reached done outside `/plan-feature` is in the same
state, and every one of them is invisible to `select_batch` while looking perfectly
buildable to an operator reading the store.

**Fix direction.** Two independent halves, both cheap:

1. Give `fast-lane-build.js` the `ac` argument its sibling already has. `fast-lane-ship.js`
   accepts `args.ac` and resolves via `select_connected` (dependency-ordered,
   **readiness-agnostic**) — the correct behaviour already exists one file over.
2. Failing that, make the silence impossible: when the caller names an AC that
   `select_batch` did not return, refuse rather than substitute. A lane that cannot build
   what was asked for should say so, not build something else and exit 0.

**Workaround until fixed.** Use `/fast-lane-ship` with `{ac: "<ID>"}` for any targeted
single-AC build, and confirm the resolution before dispatching:

```
python3 <root>/.leafcutter/scripts/build_orchestration/fast_lane.py select_connected --ac <ID> --ac-root <store>
python3 <root>/.leafcutter/scripts/build_orchestration/fast_lane.py check_producibility --ac-ids <ID> --ac-root <store>
```

An empty `select_connected` result is a clean no-op in the lane, so checking first is the
difference between a diagnosis and a wasted run.

**Related.** `KI-BP-20260826-1331` — a different fast-lane false-green (install phase), not
this one. The shared shape is worth naming: the fast lane's failure mode is consistently a
**successful run against the wrong inputs**, which no gate downstream of input selection can
detect.

---

### KI-BO-20260901-1045 — Every handoff halts the drive: the driver routes on a `handoff_target` field that no agent template tells any agent to emit

- **Severity:** blocker
- **Status:** open — no AC
- **Occurrences:** 2 observed (ACD-2100a-1 on 2026-08-26, ACD-2100a-4 on 2026-09-01),
  but the mechanism guarantees it for every handoff from every agent
- **First seen:** 2026-08-26 · **Last seen:** 2026-09-01
- **Where:** `templates/workflows-js/build-feature.js:1595`
  (`const handoffTarget = phaseResult.handoff_target;`) and the refusal at `:1606`,
  against `templates/agents/python-coder.md` — and against every other agent template

**Symptom.** A phase returns `handoff` and the drive stops:

```
Phase 'python-coder' returned 'status: handoff' but named no recognizable
handoff_target ('undefined'). Refusing to guess a re-dispatch target and
refusing to advance to the next phase in phaseOrder.
```

**Cause, and it is not "the agent forgot".** The driver reads the target from a
`handoff_target` key on the phase's returned payload. Grep the entire agent template
directory:

```
grep -c handoff_target templates/agents/python-coder.md   -> 0
templates/agents/ files mentioning handoff_target         -> 0
```

**No agent template anywhere names that field.** What `python-coder.md` actually documents
is a *ticket-file* convention, in three places:

- `:142` — "Adds tasks to `### test-writer` section and uses `(status: handoff)` instead of
  `(status: ok)`"
- `:458` — "When signing off, use `(status: handoff)` instead of `(status: ok)` to signal
  that test-writer must run next."
- `:601` — "`(status: handoff)` to test-writer for the assertion-only fix."

So the protocol is specified as *write a section in the ticket and mark the comment*, and it
is read as *set a key in the return value*. An agent that follows its template **exactly**
produces a handoff the driver cannot route. This is not intermittent and not agent-dependent:
it is every handoff, always.

**Why blocker rather than high.** The handoff path is not an edge case — it is the mandated
route for the Test Delegation rule, where a coder that needs a test changed must hand off
rather than edit tests itself. So the one protocol the repo requires coders to use is the one
that halts the drive, and the halt is unrecoverable by re-running: the cached phase result is
byte-identical, so the same `undefined` comes back. Both observed instances required a human
to read the prose and act on it.

**The information is always present and always ignored.** In both observed cases the target
was unambiguous in the record:

- `ACD-2100a-1` — the coder's comment named test-writer and gave a full remediation manifest:
  file, function, and the exact one-line edit.
- `ACD-2100a-4` — the coder wrote an entire `## Implementation Tasks` → `### test-writer`
  section, which is *precisely* what `python-coder.md:142` instructs it to do.

The driver is right to refuse to guess. It is looking in the wrong place: the ticket says who
the target is, in the structured heading its own template mandates.

**Fix direction.** Resolve the target from the ticket rather than from the return payload —
the `### <agent>` heading under `## Implementation Tasks` is already structured, already
mandated, and already populated. If the return-payload contract is the one to keep instead,
then every agent template that can emit `handoff` must be told to set `handoff_target`, and a
`handoff` returned without it should be a template-conformance error named as such, not an
`('undefined')` the reader has to decode. Do not do both halves independently — the two-sided
contract with only one side documented is the defect.

**Trap for whoever fixes it.** The refusal message reads as a per-ticket problem, so the
natural response is to fix that ticket's comment by hand. That works, and it hides the
defect: the drive then runs until the next handoff, which is how this reached two occurrences
across two weeks before the pattern was visible. Check `grep -c handoff_target
templates/agents/` before concluding an instance is a one-off.

**Related.** `KI-BO-20260831-1930` (the driver defers a phase the generator marks needed) and
`KI-BO-20260831-1931` (completeness read from the newest comment while the driver halts before
dispatching) — the same family: a two-sided contract whose halves were specified separately
and never reconciled, failing closed in a way that reads as a ticket defect.

**Pattern:** `docs/reference/false-green-mechanisms.md` — the inverse face: a gate that fails
closed correctly, on a field the other side of its own contract was never told to provide.

---

### KI-BO-20260831-1520 — The fast lane's green gate runs only the AC's own tests, so a build that breaks 19 other tests reaches review reporting "gates green"

- **Severity:** high
- **Status:** open — no AC
- **Occurrences:** 1
- **First seen:** 2026-08-31 · **Last seen:** 2026-08-31
- **Where:** `templates/workflows-js/fast-lane-ship.js` — the `greenCoverageInvocation`
  string, and the absence of any full-suite step anywhere in the lane

**Symptom.** A fast-lane build of `BO-100e-1` / `BO-100e-1-i` widened `build-feature.js`'s
single planner dispatch into a multi-look loop. Its own new tests passed. The lane's payload
reported the build complete with *"gates green (red-baseline, green+coverage, review)"*.

The branch broke **19 pre-existing tests** in `unit_tests/prompt_assembly/` — every
`build-feature.js` driver test that models an epic. None of them appear in the lane's own
report.

**Root cause — the gate is AC-scoped by construction, and nothing else is suite-scoped.**

```js
const greenCoverageInvocation =
  `python3 ${gateScript} verify_green_and_coverage` +
  ` --ac-ids ${batchIds} --test-root ${worktreePath} --ac-root ${acStoreRoot}`;
```

`--ac-ids` narrows the run to tests tagged for the ids being built. That is deliberate and is
what makes the lane fast; the comment above it says so (*"inlined lean loop — scoped to the
resolved ids"*). The defect is not the scoping. It is that **the lane runs nothing broader at
any point**, and then reports the narrow result in language that reads as a verdict on the
change.

`pr-reviewer` does not close the gap either: it reads the working **diff**. The 19 broken
tests are not in the diff — they are files the change breaks without touching. A reviewer
looking only at what changed cannot see them by construction.

**What this cost, concretely.** The review phase spent a full cycle on a branch whose suite was
already red, and returned three high-confidence findings about the diff — good findings, all
three real — while never mentioning that the branch did not build. Had those findings been
clean, the lane would have committed and opened a PR with 19 failing tests.

**The 19 tests were not the whole of it, and that is the part worth reading.** Repairing them
took four more rounds and surfaced three further defects the lane's report said nothing about,
including a regression against `BO-300a-5` — an ALREADY-COMPLETED criterion — and an unbounded
loop with no cap and no operator-visible error. Six defects in total on a build the lane
reported as `status: ok, gates green`. So the scoped gate does not merely miss "some other
tests": it misses whether the change is correct at all, while its report reads as a verdict
that it is. Treat the number 19 in this entry as the count that was VISIBLE at the time, not
the count that existed.

**Not undetected forever — detected late, behind a green.** `Test suite (pytest)` is a required
CI check and runs the full suite, so the PR would have gone red. The damage is ordering and
trust: the lane declares its own work sound before anything has checked that claim, and an
operator reading `status: ok, gates green` has no signal that the assertion is scoped. This is
the `docs/reference/false-green-mechanisms.md` shape where a **narrow check is reported in wide
language** — the check did exactly what it says; the report does not say what it checked.

**Why the AC-scoped gate cannot simply be widened.** Running the full suite per fast-lane build
costs ~18 minutes locally (measured on this branch: `4538 passed` in 1098s), against a lane
designed to be lean. Two shapes that keep the speed:

1. **Run the full suite once, after the coder loop settles and before `pr-reviewer`.** One run
   per build, not per gate iteration. It also stops wasting a review cycle on a branch that
   does not build.
2. **Keep the gate scoped but fix the report.** Have `verify_green_and_coverage` state the
   scope it actually ran (`N tests matching ac-ids X, Y`), and have the lane's payload and PR
   body carry that qualifier instead of an unqualified "gates green". Cheaper, and honest, but
   it only stops the wrong belief — it does not stop the broken PR.

These are not alternatives; (2) is the floor and holds whether or not (1) ships.

**The repo already had this rule, for the other pipeline.** `CLAUDE.md` → *"Full test suite +
ruff at epic-finalize (before merge)"* exists because per-ticket sign-offs run only that
ticket's own tests and cross-cutting breakage slips through. That is this defect exactly, one
pipeline over. The fast lane was built after that instruction and did not inherit it.

**Pattern:** a check that is honest about what it did, reported in language that implies more.

**Related.** `KI-BO-007` (a phase reported complete against the agent returning cleanly rather
than against an observable side effect — the same substitution of a proxy for the thing).

---

### KI-BO-20260901-1450 — UNDER INVESTIGATION: the fast lane isolates its worktree but not the process-level state around it, and three shared surfaces already misfired with only ONE lane running

- **Severity:** unknown — under investigation, see "What we are asking for" below
- **Status:** **UNDER INVESTIGATION** — filed before the confirming experiment, deliberately.
  Contributions wanted; this entry is a request for evidence as much as a record.
- **Occurrences:** 3 distinct surfaces, each observed at least once on 2026-09-01, **all with a
  single lane running**
- **First seen:** 2026-09-01 · **Last seen:** 2026-09-01
- **Where:** `$GIT_COMMON_DIR/config`; `<root>/.build_manifest.json`; the shared `.leafcutter`
  install tree reached through each worktree's symlink

**Why this is filed now, before the experiment.** The intended next step is to run two fast
lanes concurrently on independent acceptance criteria and observe what actually breaks. That
experiment has not been run. Filing first means the predictions are on record *before* the
result, so they can be scored honestly rather than reconstructed afterwards to match whatever
happened. If the experiment contradicts the entry, the entry is wrong and should say so.

**The shape of the concern.** `/fast-lane-build` isolates the thing everyone thinks about — it
opens a fresh worktree per run (`fast-lane/<slug>` off `origin/main`) and claims its ACs before
building, so two lanes cannot take the same criterion. What it does **not** isolate is the
process-level state that every worktree of the repository shares. Three such surfaces bit a
single lane on 2026-09-01:

| surface | what happened with ONE lane |
|---|---|
| `.git/config` | A test fixture set `user.name` / `user.email` inside a worktree it created. Worktrees share `$GIT_COMMON_DIR/config`, so the identity leaked to the whole repository family and **four** commits landed misattributed across three different worktrees. `KI-TQ-012`. |
| `.build_manifest.json` | A build targeted at a worktree wrote a manifest with no usable `output_mappings`; a later commit **in a different tree** was then blocked by `check-build-drift` reporting 170 false gaps. `KI-BP-011`, `KI-CG-20260831-manifest-shadowing`. |
| shared `.leafcutter` | Worktrees symlink to one install tree, so `build.py --target-dir <worktree>` deploys *through* the link and replaces the shared deployed package for every other tree. `KI-BP-016`. |

**Why the existing coverage does not reach this.** `ACD-2000b-4` governs parallel safety at
requirement grain, and its unit is the **acceptance criterion's file footprint** — which two
criteria touch which repository files. That is a real and separate gap (its host was decided on
2026-09-01: the claim path, `filter_already_claimed`). None of the three surfaces above is an AC
footprint. They are process-level singletons that no criterion in the store currently mentions,
so building `ACD-2000b-4` in full would leave all three untouched.

**The hypothesis, stated so it can be falsified.** Each of these degrades with N lanes rather
than improving, because each is a single shared resource written by every run:

1. Concurrent commits misattributed, or attributed inconsistently within one lane's own history,
   whenever any run executes a suite that writes git config.
2. `check-build-drift` / `check-output-drift` blocking commits in lane B because lane A wrote the
   manifest last — a cross-lane failure whose message names neither lane.
3. A build in lane A changing the deployed package that lane B's hooks and agents are executing
   from, mid-run.

**What we are asking for.** This is filed deliberately incomplete. If you have seen any of the
following, adding it here is more valuable than a fix right now:

- **A parallel-lane run that went wrong**, especially one where the failure surfaced in a
  different worktree from the one that caused it. Cross-tree symptoms are the hard part; the
  message never names the culprit.
- **A fourth shared surface** we have not listed. Candidates nobody has checked: the pre-commit
  cache under `~/.cache/pre-commit`, `.security-allowlist` resolution through the symlink
  (`KI-BP-017` touches this), the feedback sink `debugging/logs/feedback.jsonl`, and the AC
  store's own claim records under concurrent writers.
- **Evidence that a surface here is actually safe** under concurrency. A negative result is
  worth as much as a positive one and will shorten the list.
- **A severity judgement.** We have deliberately not assigned one. Whether this is a blocker on
  running lanes in parallel, or an annoyance that a convention avoids, depends on how the three
  behave together — which nobody has measured.

**Explicitly NOT claimed.** That parallel lanes are unsafe. They may well be fine in practice;
several of the observations above have known one-line mitigations (do not run `build.py` against
a worktree; reset the git identity after any suite that writes it). The claim is narrower: the
lane's isolation story stops at the worktree boundary, three surfaces past that boundary have
already misfired at N=1, and nobody has checked what they do at N>1.

**Related.** `KI-TQ-012` (the git-identity leak, and the only one of the three with a named
root cause). `KI-BP-011` (the manifest is written to the package that ran the build rather than
the install it describes). `KI-CG-20260831-manifest-shadowing` (the reader side of the same
defect). `KI-BP-016` (`build.py --target-dir` against a worktree deploys over the shared tree).
`KI-BO-020` (the release-on-failure path is dead, so an aborted lane strands its claims — the
one lane-level defect that is unambiguously worse with more lanes).

**Pattern (provisional):** isolation designed around the artifact people can see — the working
tree — while the machinery underneath it stays global, so the blast radius of a single run is
larger than the directory it was given.

---

### KI-BO-20260901-1620 — `permits_shell` is a three-state field read as two, so the fix for KI-BO-020 picked an agent the schema also calls read-only — and three shell dispatches still go to the one agent that explicitly forbids it

- **Severity:** high — one live charter violation on the claim path, and the guard that should
  catch it does not exist
- **Status:** open — no AC
- **Occurrences:** 1 systemic (4 dispatch sites, 3 still wrong)
- **First seen:** 2026-09-01 · **Last seen:** 2026-09-01
- **Where:** `config/agent_registry.json` (`permits_shell`, declared on exactly 2 of ~40 agents);
  `config/agent_registry.schema.json:123-125`; `templates/workflows-js/fast-lane-ship.js:490`
  (the fix) and lines **666**, **750**, **824** (the unfixed dispatches)

**Symptom — the field has three states and the code reads two.** The schema is explicit:

> `permits_shell` … True if this agent's registered charter permits running repository-mutating
> shell commands … **False or absent means the agent must be treated as read-only** for
> dispatch-permission gates.

Measured across the registry, only **two** agents declare it at all:

| agent | `permits_shell` | schema meaning |
|---|---|---|
| `status-checker` | `false` | read-only |
| `worktree-agent` | `true` | may run repository-mutating shell |
| everyone else, incl. `python-coder` | **absent** | read-only |

`KI-BO-020`'s fix reasoned from the wrong predicate. Its comment at `fast-lane-ship.js:481-489`
justifies the substitution as: *"dispatch an executor whose declared … entry does not explicitly
forbid running shell commands (permits_shell !== false) … python-coder's entry declares no such
restriction."* Under the schema's own definition, `absent` **is** the restriction. So the fix
replaced an agent the schema calls read-only with another agent the schema also calls read-only,
and the only agent actually chartered for this is `worktree-agent`.

It works in practice — `python-coder` does not refuse, and a live run confirmed the release
succeeds — so the *behaviour* is fixed. The *justification* is not, and it is written into the
code as a comment future readers will copy.

**The larger half: three dispatches were never fixed.** `KI-BO-020` was scoped to the release
path, so only that one moved. These still send `status-checker` — the single agent that
explicitly declares `permits_shell: false` — to run Bash:

| line | dispatch | what the command does |
|---|---|---|
| 666 | resolve | reads the store |
| 750 | producibility | reads the store |
| **824** | **claim** | **flips `todo` → `in_progress` in the AC store** |

Line 824 is the one that matters. Claiming *writes* to the store, which is repository-mutating
by the schema's own wording, and it is dispatched to the agent that forbids exactly that. It is
also the mechanism every parallel fast-lane run depends on for mutual exclusion.

**Why it has not blown up yet, and why that is not reassurance.** `status-checker` refuses by
*judgement*, not by mechanism — it reads its own charter and declines. It refused the release
prompt twice (`KI-BO-020`) because that prompt opened `You are the release-phase agent`, an overt
role reassignment. The claim prompt opens `You are the claim-phase agent for a fast-lane build`
— the same shape. It has not refused **yet**. Nothing prevents it doing so on the next run, on a
different model, or after a template edit, and if it refuses at the claim step the run loses its
only exclusion guarantee.

**Nothing enforces the field.** No hook, gate or test compares a workflow's `agentType`
dispatches against `permits_shell`. The field is declared, documented, and consulted by exactly
one hand-written comment. That is why a wrong reading of it survived review and shipped.

**Suggested fix, and the ordering matters.**

1. **Decide what the field means and make `absent` explicit.** Either backfill `permits_shell`
   on every registry entry so there is no third state, or change the schema so absent means
   "permitted" and `false` is the only restriction. The current "absent == false" reading is
   defensible but nobody follows it, which is the evidence it is the wrong default.
2. **Enforce it mechanically.** A check that walks each `templates/workflows-js/*.js` for
   `agentType:` literals whose prompt contains a shell invocation, and fails when the named agent
   is not `permits_shell: true`. Without this, step 1 is another field nobody reads.
3. **Fix the three dispatches**, claim first. The honest options are the same two `KI-BO-020`
   named: dispatch an agent whose charter actually covers it, or stop using an agent. Note that
   the second is **not available** — the E2 engine gives the workflow body no filesystem or
   subprocess access, so every side effect must go through an `agent()` call. That constraint
   should be recorded wherever this is fixed, because "just call the CLI directly" is the
   obvious suggestion and it cannot be done.
4. **Consider whether a chartered executor agent should exist.** These four dispatches all do the
   same thing: run one deterministic `fast_lane.py` subcommand and parse its JSON. That is not
   `status-checker`'s job and it is not `python-coder`'s either. Authoring one is `llm-expert`'s
   surface — the `KI-BO-020` fix comment says as much and explicitly defers it.

**Related.** `KI-BO-020` (resolved — the release path; this entry is its residual).
`KI-BO-20260901-1450` (the fast lane's isolation stops at the worktree boundary; the claim path
is the mechanism that entry's parallel-safety question depends on).

**Pattern:** a permission field with a documented tri-state, no enforcement, and two of ~40
records populated — so the first person to consult it reasoned from the populated cases and got
the default backwards, in a comment that now teaches the error.
