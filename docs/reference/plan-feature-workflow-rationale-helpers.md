---
title: "Reference: plan-feature workflow rationale, helper and handoff comments"
description: "Third volume of the rationale comments moved verbatim out of templates/workflows-js/plan-feature.js: guard, helper, resume and handoff comments, grouped by the code each explains."
type: reference
status: active
created: 2026-10-14
last_updated: 2026-10-14
components:
  - ac_driven_dev
related_docs:
  - docs/reference/plan-feature-workflow-rationale.md
  - docs/reference/plan-feature-workflow-rationale-gates.md
---

# Reference: plan-feature workflow rationale (helpers and handoffs)

Continuation of `plan-feature-workflow-rationale-gates.md`, in the same form: long rationale comments moved out of `templates/workflows-js/plan-feature.js` so the workflow file stays within its size ratchet. The text is unchanged; only the `//` comment markers were dropped. Each section names the code it explains; the workflow keeps a one-line pointer here.

## The no-main-commit guard

Explains: The fail-closed branch check before every stage commit.

```text
---------------------------------------------------------------------------
AC BO-1500c-3 — NO-MAIN-COMMIT DEFENSIVE GUARD (fail-CLOSED)

Always run the branch check, regardless of whether authoringWorktreePath
is set. When null, use `git branch --show-current` without -C.
ALL failure paths abort the commit — cannot risk committing to main or
an unconfirmable branch.
---------------------------------------------------------------------------
```

## Display name to stage key mapping

Explains: The inverse of stageDisplayName().

```text
Display name → internal stage key mapping (inverse of stageDisplayName()).
Keyed on the LOWERCASED display name (the subject scan lowercases below), so
"MOCK-DATA" → "mock-data" → "mockdata", "MOCKUP" → "mockup", "FLOW" → "flow".
```

## The product-truth phase helpers

Explains: The banner above the PT phase helper functions.

```text
===========================================================================
PRODUCT-TRUTH (PT) PHASE HELPERS

The PT phase runs on every invocation (always-on) between ac-triage and the
AC authoring pipeline. It dispatches pt-classifier, derives the run-set from
the classifier OUTCOME (never the dispatch array), then drafts the required
product-truth artifacts (mock data → mockups → flow) each behind a user gate,
committing each approved stage surgically. See ADR (always-on PT phase).
===========================================================================
```

## The no-main-commit guard in the PT commit helper

Explains: The mirror of the commitStageOutput guard.

```text
-------------------------------------------------------------------------
NO-MAIN-COMMIT DEFENSIVE GUARD (fail-CLOSED) — mirrors commitStageOutput.
-------------------------------------------------------------------------
```

## The reconcile-run parse guard

Explains: The non-fatal parse of the reconciliation reply.

```text
Guard the parse: a non-JSON reconcile-run response must NOT throw out of the
top-level body (the ACs are already committed by this point). Reconciliation
is intentionally non-fatal — the caller only logs on status:error.
```

## Inline pause-resume helpers

Explains: Why the pause-resume helper is defined inline (ADR-024).

```text
§R — Inline pause-resume helpers (ADR-024 BO-2300 RESUME half).
E2 workflow bodies are self-contained and cannot import local modules
(ES-module import is a SyntaxError inside the test-harness IIFE, and the
runtime has no module access), so the pause-resume helper is defined inline
here. The same helper is inlined in finalize-feature.js — keep them in sync.
```

## Carrying feedback through a resumed edit

Explains: The feedback field kept on a resumed edit decision.

```text
Carry `feedback` through. The mid-pipeline gate reads gateDecision.feedback to
thread the user's notes into the re-dispatched author prompt; dropping it here
re-ran the author with EMPTY feedback and burned the single MAX_EDIT_RETRIES
attempt, so a resumed `edit` aborted the pipeline uncommitted.
```

## Verifying the pause persist

Explains: The read-back after the pause record write.

```text
VERIFY THE PERSIST (never trust the write): read back via the shared retrying
read, so a brace-dropped reply cannot fail a record that IS on disk (2026-10-09)
and an unreadable reply (null) is never "verified".
```

## Placement of --store-dir

Explains: Why --store-dir precedes the pause_store subcommand.

```text
`--store-dir` is defined on pause_store.py's TOP-LEVEL parser, not on
the write/read subparsers, so argparse requires it to precede the
subcommand name -- placing it after (e.g. "write ... --store-dir DIR")
is rejected as an unrecognized argument.
```

## A worktree path that stays null

Explains: The halt when no authoring worktree directory exists.

```text
BO-1500a-5-i shapes (3)/(4): success-shaped but no directory, vs.
no-failure-reported and no directory/branch. Either way this must
halt -- authoringWorktreePath must NEVER stay null past this point.
```

## The orphan gate closure

Explains: Why the orphan gate's live closure is never invoked.

```text
ADR-024: resolveGate checks args.resume_answer before ever considering a
live decision — and (ACD-2100c-1) never dispatches liveGateFn at all, so
this closure's own agent() call is built for API-shape parity with the
other four gates but is never actually invoked.
```

## A missing orphan decision fails closed

Explains: The absent .action/.choice case at the orphan gate.

```text
Fail CLOSED, not destructively — see the covered-route gate below. A
missing decision here must never be treated as the user choosing "no";
resolveGate() only ever reaches this line via a validated resume_answer,
so an absent .action/.choice at this point is itself a gate failure.
```

## A flow forces the BA stage in

Explains: Why a technical route with a flow still runs the BA.

```text
technical route BUT a flow was produced — FORCE the BA stage in so the flow's
steps derive L2s (else the flow steps would be orphaned). The BA dispatch
below supplies an L1 anchor for the component when parent_l1_id is absent.
```

## Crash-resume stage skip

Explains: The skip of stages already committed in a prior session (BO-1500b-2).

```text
-----------------------------------------------------------------------
Crash-resume: skip stages that already committed in a prior session
(AC BO-1500b-2).
-----------------------------------------------------------------------
```

## A resumed edit still dispatches the author

Explains: Why the edit resume answer does not skip the authoring dispatch.

```text
"edit" is the one resume answer that does NOT move past this step's gate
— it re-dispatches the author WITH the supplied feedback, exactly like a
live edit-retry, so the authoring dispatch below must never be skipped
for it (skipping would drop the feedback on the floor).
```

## The flow to BA handoff

Explains: What the BA derives from an approved product-truth flow.

```text
Flow → BA handoff: when a product-truth flow was approved this run, the BA
derives L2/L3 from the flow's steps (self-discovered via index.json — a
structured flow_ref input is inert) and reports a flow_backlinks map the
reconciliation step writes back into step.implements.
```

## The flow-derived AC parenting rule

Explains: Orphan prevention for L2/L3 records derived from a flow step.

```text
FLOW-DERIVED-AC PARENTING RULE (orphan-prevention): every L2/L3 you derive
from a flow step MUST have an L1 parent, or scan_ac_orphans.py /
check_ac_parent_covered_by (pre-commit hooks) will flag it. Give an
explicit anchor in BOTH branches — never leave a flow-derived AC parentless.
```

## Commit before the next stage

Explains: The commit-before-next-stage invariant (BO-1500b-1).

```text
approve — commit stage output before dispatching the next agent.

COMMIT-BEFORE-NEXT-STAGE INVARIANT (AC BO-1500b-1):
The commit MUST succeed before the while-loop exits and the outer
for-loop advances to the next pipeline step.
```

## Reconciliation after the BA stage

Explains: The dedicated reconciliation commit after the BA stage.

```text
-----------------------------------------------------------------
Reconciliation (Track 1.3): AFTER the BA stage is committed, write
the BA's reported flow_backlinks into the flow's step.implements and
regenerate derived data as a DEDICATED reconciliation commit (it
re-mutates the already-committed flow + index + ACs).
-----------------------------------------------------------------
```

## The final-gate cancel attribution

Explains: Why the final-gate cancel is attributed to a person.

```text
AC BO-1500c-1-i — NO-PR GUARANTEE (final-gate cancel).
AC BO-2300a-2 — distinct terminal status (see the mid-gate cancel above).
ACD-2100c-5 — `cancelled_by: "person"` (see the mid-gate cancel above
for why this branch is only ever reached with person attribution).
```

## Delivery: push and open the PR

Explains: The delivery step after the final commit (BO-1500c-1).

```text
-----------------------------------------------------------------------
§D — Delivery: push authoring branch to origin and open a PR to main.
(AC BO-1500c-1)
-----------------------------------------------------------------------
```

## The workspace-setup permission gate banner

Explains: The banner above the registry-read pointer (ACD-2100b-5).

```text
-------------------------------------------------------------------------
Pre-Stage-0 — Workspace-Setup Permission Gate (ACD-2100b-5).
-------------------------------------------------------------------------
```

## Crash-resume stage output recovery

Explains: Why a committed stage's AC ids are recovered from the commit body.

```text
Crash-resume: this stage's output is already in git history.
Recover the AC IDs from the commit body so they are included in
allAcsWritten (and thus in the final approval set and PR body).
```

## The structured ENOREPO marker

Explains: Why the repository-resolution failure marker in `_buildRepoRootResolutionSnippet` is an errno-style code, not an English phrase (moved verbatim out of plan-feature.js, ACD-2100b-1 and ACD-2100b-2).

```text
Structured, fixed-vocabulary marker (mirrors buildRepoAnchoredReadCommand()'s
own REGISTRYREADFAIL tags below), using an errno-style CODE rather than
an English phrase. This command's own literal source text is dispatched
as part of the agent() prompt on EVERY run regardless of which branch
actually executes, so an English reason word here (e.g. "found",
"missing", "denied") would leak into the observable report of every
OTHER branch's run too. A code with zero lexical overlap with either
the "not found" or "permission refused" vocabulary (ACD-2100b-1), NOR
with the word "unreadable" itself, is what keeps those two reports —
and this run's own report, whatever outcome it turns out to be —
genuinely distinguishable (ACD-2100b-2: this same static command text
is also dispatched, unconditionally, on the uninterpretable-registry
outcome, so a tag containing "unreadable" would leak that word into
every uninterpretable-registry report too).
```
