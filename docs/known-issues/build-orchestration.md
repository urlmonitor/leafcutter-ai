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

Refiled 2026-08-18 as **KI-ACS-001** in
[`docs/known-issues/ac-store.md`](ac-store.md): *an AC is marked `done` with no link
to the code implementing it.*

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

### KI-BO-007 — A structural test makes code comments load-bearing

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

### KI-BO-008 — The harness default stub is generically positive, so a new gate silently breaks older fixtures

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
