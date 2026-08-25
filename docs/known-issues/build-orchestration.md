---
title: "Known issues — build-orchestration"
description: "Open, observed defects in the build-orchestration component: the fast-lane build loop, its gates, and the AC lifecycle transitions it performs. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-08-25
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

**Adding an issue.** Append a new `### KI-BO-NNN` section using the next free number.
Nothing here is generated — edit it by hand. Fill in what you actually know; an issue
recorded with a thin `Evidence` line is far better than one not recorded.

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
- **Status:** open · AC **BO-2400c-1-v**
- **Occurrences:** 1
- **First seen:** 2026-08-14 · **Last seen:** 2026-08-18
- **Where:** `templates/workflows-js/fast-lane-build.js`

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

---

### KI-BO-007 — `build-feature` counts a phase as completed when the agent halted without doing it, yielding `status: ok` with no PR

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/workflows-js/build-feature.js` — the per-phase result handling
  that populates `completed_phases`

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

### KI-BO-019 — A CRLF acceptance-criterion record is rewritten LF end-to-end by a single `work_status` flip, and every value-level check still passes

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

### KI-BO-020 — `_update_ac_work_status` raises `ValueError`, all three call sites catch only `OSError`, and the escape strands acceptance criteria in `in_progress` permanently

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
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
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

Whichever is chosen, the operator-facing message must stop saying "was not obtained" when
`obtained` was true. Distinguish *not obtained* from *obtained but unusable, because X* —
the current text sent a reader looking for an assembly failure that had not happened.

---

### KI-BO-020 — The fast lane's release-on-failure path is dead: it dispatches `status-checker`, which refuses the role, so aborted runs strand their claims

- **Severity:** high — silent, and it defeats a criterion believed to be working
- **Status:** open
- **Occurrences:** 1 observed; every failing path that releases is affected
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
