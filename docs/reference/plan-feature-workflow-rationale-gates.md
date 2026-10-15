---
title: "Reference: plan-feature workflow rationale, resume and gate comments"
description: "Second volume of the rationale comments moved verbatim out of templates/workflows-js/plan-feature.js: pause, resume, gate, cancel and pre-flight comments, grouped by the code each explains."
type: reference
status: active
created: 2026-10-14
last_updated: 2026-10-14
components:
  - ac_driven_dev
related_docs:
  - docs/reference/plan-feature-workflow-rationale.md
---

# Reference: plan-feature workflow rationale (gates and resume)

Continuation of `plan-feature-workflow-rationale.md`, in the same form: long rationale comments moved out of `templates/workflows-js/plan-feature.js` so the workflow file stays within its size ratchet. The text is unchanged; only the `//` comment markers were dropped. Each section names the code it explains; the workflow keeps a one-line pointer here.

## The pre-flight outcome field

Explains: The Pre-Stage-0 permission verdict reading.

```text
The pre-flight's own `outcome` field distinguishes the same facts
ACD-2100b-1 (registry unreadable), ACD-2100b-2 (registry
uninterpretable), and ACD-2100b-3 (denied vs. absent vs. no entries
collection, ACD-2100b-3-i) used to distinguish via separate
dispatch/interpretation branches in this file. Switching on that field
(rather than collapsing to a single boolean) is what keeps those
outcomes distinguishable from one another (it_requirements) — the
report below states the exact fact the pre-flight established, and
never a fact it did not (e.g. "not found" is never worded as "denied").
```

## Absent versus permission-refused registry

Explains: The read_failure report rendering.

```text
ACD-2100b-1 AC-2: an absent registry and a permission-refused registry
both classify as outcome="read_failure" on the pre-flight side (see
scripts/worktree/check_workspace_setup_permission.py's `_load_registry()`),
but that script now attaches a distinguishing `location` and `reason`
to the verdict for exactly this case -- render both here rather than
the old single static string, so the two Given conditions produce
genuinely different reports instead of a byte-identical one.
```

## The denied report names the permission setting

Explains: The permission_denied report text.

```text
ACD-2100b-3 AC-4: the denied report must direct the reader at the
permission setting to change, not just state the denial in prose --
name the `permits_shell` field of config/agent_registry.json literally
(confirmed the real field name via `_resolve_agent_outcome()` and the
deployed config/agent_registry.json before naming it here).
```

## Resolving the setup script to an absolute path

Explains: `worktreeScriptResolution` before the worktree-setup dispatch.

```text
Resolve the setup script to an ABSOLUTE, repository-anchored location
BEFORE building the worktree-setup dispatch's own command text — never a
`{{config.output_root}}`-relative path, whose resolution would depend on
the dispatching agent's own working directory and could silently select
the wrong physical copy (KI-ACD-004, ACD-2100a-1). Learning the resolved
path via a dedicated dispatch first (rather than resolving it inline
inside the worktree-setup command) is what lets the worktree-setup
dispatch's own static command text carry the literal absolute path,
satisfying "the run's own record of the command it issued names an
absolute location" rather than an unexpanded shell variable.
BO-2300a-1-ii: workspaceSetupAgentId (worktree-agent), same as
worktree-setup below -- never status-checker.
```

## The worktree-setup step is dispatched exactly once

Explains: The worktree-setup dispatch.

```text
The worktree-setup step is dispatched EXACTLY ONCE either way. On success
it runs the resolved, absolute, repository-anchored invocation. On
failure it re-issues the SAME resolution command, which fails again for
real and deterministically — so the failure, and the exact location that
could not be resolved, is observable on the worktree-setup step's own
record. This must never silently fall back to a `{{config.output_root}}`-
relative invocation that could select the wrong physical copy (AC-3).
```

## A refused or uninterpretable setup reply halts

Explains: The `wtParsed === null` halt.

```text
BO-1500a-5-i: a refusal, an out-of-scope reply, or an uninterpretable
reply is a failed setup, halting BEFORE exit_code/wtPayload checks and
before Stage 0 dispatches any authoring agent. wtParsed is null only for
a STRING reply with no parseable JSON (free text, not a structured
outcome) -- the OLD code fell through to `if (wtPayload) {...}` instead.
```

## A missing covered-gate answer fails closed

Explains: The `_covGateResult` guard.

```text
Fail CLOSED, not destructively. A null result here means the gate could not
be answered at all — the agent died, refused the role it was handed, or
returned unparseable text (KI-ACD-005). Defaulting that to "cancel" made a
transport failure indistinguishable from the user genuinely choosing to
cancel, and silently discarded the request. Surface it instead.
```

## Product-Truth phase overview

Explains: The PT phase body.

```text
Product-Truth (PT) Phase — ALWAYS-ON; runs between triage and the AC pipeline.
Dispatches pt-classifier, derives the run-set from the OUTCOME (never the
`dispatch` array), self-skips (non-silent) when the store is absent, then
drafts mock-data → mockup → flow (filtered) each behind a user gate, committing
each approved stage surgically. `outcome:"none"` and unparseable classifier
output fall straight through to the AC pipeline.
```

## PT-stage cancel status

Explains: The PT-stage cancel return.

```text
NO-PR GUARANTEE (PT cancel): prior committed PT stages preserved, current draft uncommitted.
AC BO-2300a-2 — distinct terminal status for a cancelled run. `cancelled_at`
alone was not enough: nothing machine-readable reads it, so a caller
branching on `status` saw a plain success.
ACD-2100c-5 — `cancelled_by: "person"` (see the mid-gate cancel above
for why this branch is only ever reached with person attribution).
```

## Crash-resume: recovering AC ids from commit bodies

Explains: The `resume-log` scan in the authoring loop.

```text
Scan line-by-line. Real `git log --format=%B` concatenates commit
bodies with a BLANK line between each subject and the rest of its body
(and between commits), so a blank-line split shatters the subject away
from the `AC IDs:` line and resumedAcIds is always []. Instead, track
whether we are inside a commit whose subject is for THIS stage — any
plan-feature(...) subject line resets the state — and read the
`AC IDs:` line from within that commit.
```

## Reconciliation is skipped on a crash-resumed BA stage

Explains: The `pt_reconciliation_skipped_on_resume` signal.

```text
m6 — the flow reconciliation lives in the BA approve branch below; a
crash-resumed (already-committed) BA stage `continue`s past it, so
baFlowBacklinks is lost and step.implements would never be reconciled.
Emit an OBSERVABLE, non-silent signal that reconciliation must be run
manually rather than silently dropping it. (A full re-derivation on
resume is out of scope; the observable signal is the required minimum.)
```

## The gate id a step is presented under

Explains: `stepGateId` in the authoring loop.

```text
ACD-2100c-3 AC-1: the gate id this step's decision point is presented
under. Used to detect that THIS process invocation is resuming a run
that previously paused right here, so the authoring dispatch below (the
step BEFORE the decision point) is not re-run for an answer that moves
past the gate.
```

## The subject binding of a resume answer

Explains: `isPausedAtThisStep` in the authoring loop.

```text
ACD-2100c-3-i: the subject binding (is THIS step the decision the run is
ACTUALLY paused at?) must be checked BEFORE any part of a supplied
resume_answer is acted on — checking only whether the SUPPLIED answer
names this step's gate is not that check, because an answer naming a
DIFFERENT decision point always fails that comparison even when this
step genuinely is the one being waited on (the mismatch case this AC
covers). peekPausedGateId() reads the durable record directly, so the
determination is anchored to the real, on-disk pause state rather than
to whatever gate_id the (possibly wrong) answer claims. Only consulted
when a resume is actually being attempted (args.resume_answer present)
— a fresh, non-resumed invocation never pays for this extra read.
```

## Not re-dispatching the author on a resume past the gate

Explains: The `skipAuthorOnResume` branch.

```text
ACD-2100c-3 AC-1/AC-2: on a resume whose answer moves past this step's
gate, do NOT re-dispatch the authoring agent — the drafted work already
on disk from the paused run is what must carry forward unchanged, and
re-dispatching here is exactly the "repeat the steps before the
decision point" this AC forbids. The AC ids from the paused run are
recovered below from the persisted pause record (via resolveGate()'s
`_resumedContext`), not re-derived from a fresh authoring dispatch. An
"edit" resume answer is excluded from this skip (see
skipAuthorOnResume above) — it dispatches normally, below.
```

## Recovering AC ids at a mid-pipeline gate

Explains: The mid-gate `_resumedContext` recovery.

```text
ACD-2100c-3 AC-1/AC-2: this step's authoring dispatch was skipped
above because this process is resuming right at this gate — recover
the AC ids the paused run already drafted from the record resolveGate()
just read, rather than treating `written` as empty (which would
silently drop them from the commit / cancel messaging below).
```

## A cancelled run is distinct from a successful one

Explains: The mid-gate cancel return.

```text
AC BO-2300a-2 — a cancelled run must be machine-readably distinct from a
successful one. `status: "ok"` here made "the user aborted and zero ACs
shipped" indistinguishable from "the pipeline completed" for any caller
that branches on `status` — which is the only reason the field exists.
ACD-2100c-5 — `cancelled_by: "person"` attributes this discard to the
person who chose it. This branch is reachable ONLY via a decision
object returned by resolveGate() (every pause-related/non-person
status was returned above, before this line), and resolveGate()
returns a decision object ONLY after validating
`resume_answer.channel === "person"` -- so every arrival here is
already known to be person-attributed. Without this field a
legitimate discard is indistinguishable from a fallback discard
after the fact (Implementation Notes).
```

## Recovering AC ids at the final gate

Explains: The final-gate `_resumedContext` recovery.

```text
ACD-2100c-3 AC-1/AC-2: the it-po authoring dispatch was skipped above
because this process is resuming right at the final gate — recover
the AC ids the paused run already drafted (and left on disk,
untouched) from the record resolveGate() just read, instead of
treating `written`/`allAcsWritten` as empty.
```

## Merging the all_acs snapshot without double counting

Explains: The `all_acs` union at the final gate.

```text
H-2 fix: `all_acs` is the pre-pause snapshot of EVERY AC id drafted
by the time this run paused — both already-committed earlier
stages AND this (final-gate) stage's own not-yet-committed ids.
The earlier-committed stages were ALREADY re-added a few dozen
lines above via the independent git-log crash-resume reconstruction
(`committedStageKeys`), so a blind push here double-counts them.
But the snapshot is NOT a strict subset of that reconstruction: the
reconstruction only recovers ids for stages visible in git log
(i.e. already committed), while this stage's own ids are still
uncommitted at pause time and exist ONLY in this snapshot — a
blind drop of this block would silently lose them (turning a
visible double-count into an invisible under-count, which is worse).
Union with de-duplication is therefore the only correct merge.
```
