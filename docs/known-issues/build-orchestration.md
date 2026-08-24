---
title: "Known issues — build-orchestration"
description: "Open, observed defects in the build-orchestration component: the fast-lane build loop, its gates, and the AC lifecycle transitions it performs. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-08-18
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

Reproduction, re-measured 2026-08-19 after the aiming fix (BO-2600b-1) landed in this
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

### KI-BO-014 — Resolving a one-criterion build set takes ~3 minutes, because every traversal re-parses the entire AC store

- **Severity:** high
- **Status:** open — no AC
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-19
- **Where:** `scripts/ac_store/scan_ac_store.py` — `traverse_ac_tree`, against
  `scripts/build_orchestration/fast_lane.py` — `resolve_connected_build_set`

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
