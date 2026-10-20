---
title: "Reference: plan-feature workflow rationale and decision history"
description: "Rationale, tombstone, and decision-history comments moved verbatim out of templates/workflows-js/plan-feature.js, grouped by the code each explains."
type: reference
status: active
created: 2026-10-14
last_updated: 2026-10-14
components:
  - ac_driven_dev
related_docs:
  - docs/reference/README.md
---

# Reference: plan-feature workflow rationale

Long rationale and history comments moved out of `templates/workflows-js/plan-feature.js` so the workflow file stays within its size ratchet. The text is unchanged; only the `//` comment markers were dropped. Each section names the code it explains; the workflow keeps a one-line pointer here.

## Repository-anchored support-script resolution

Explains: `_buildRepoRootResolutionSnippet()` and `buildRepoAnchoredResolutionCommand()`.

```text
Repository-anchored support-script resolution
(ACD-2100a-1 / KI-ACD-004, extended by ACD-2100a-3 / KI-ACD-009 cause 1).
`{{config.output_root}}` is a BUILD-TIME placeholder that resolves to a bare
relative name (".leafcutter") baked into the compiled template. A shell
command built with that placeholder is resolved by the DISPATCHING AGENT'S
OWN working directory, not by anything this workflow controls — in the
ADR-001 self-hosting dev layout that selects the deployed build-output copy
sitting in the untracked workspace parent, not the copy that belongs to the
repository this run is actually operating on (KI-ACD-004).

The E2 workflow body has no filesystem access of its own (ADR-030: no `fs`,
`process`, `__dirname` reachable from the sandboxed script body), so the
fix cannot be "read the path here" — it must happen INSIDE a dispatched
shell command, at the moment that command actually runs, and the resolved
ABSOLUTE path must then be embedded literally into any later command that
needs it, so the run's own record of what it issued names a real,
repository-anchored location rather than a cwd-relative placeholder.

A run started with cwd set to a LINKED `git worktree` (e.g. the very
AC-authoring worktree this route creates) is itself "inside a git
repository" by `git rev-parse --show-toplevel`'s definition — but that
command reports the WORKTREE'S OWN directory, which holds no installed
`.leafcutter/` of its own (ADR-001: it is untracked build output that only
`install_shims` populates on the project's own checkout; a workspace's
checkout only ever holds TRACKED content). `git rev-parse --git-common-dir`
does not have that problem: it always resolves to the ONE `.git` directory
shared by the main checkout and every one of its linked worktrees,
regardless of which of them the command runs from — so its parent
directory is "the repository being operated on" even from inside a
worktree (KI-ACD-009 cause 1).
```

## Removed Pre-Stage-0 registry-read helpers

Explains: the Pre-Stage-0 workspace-setup permission section (tombstone for four removed helpers).

```text
buildRepoAnchoredReadCommand(), _parseRegistryUnreadableDiagnostic(),
_describeRegistryInterpretationFailure(), and
_resolveWorkspaceSetupAgentEntryState() used to live here, supporting the
Pre-Stage-0 workspace-setup permission dispatch above. ACD-2100b-5 removed
that dispatch (the registry read now happens locally, in
scripts/worktree/check_workspace_setup_permission.py, invoked by the
plan-feature skill before this workflow runs — see that section's own
comment) and these four helpers had no other caller, so they were removed
with it rather than left as dead code.
```

## Pre-Stage-0 workspace-setup permission gate

Explains: `workspaceSetupAgentId` / `workspaceSetupPermission` at Pre-Stage-0.

```text
The isolated-workspace setup step below runs repository-mutating commands
(fetch, branch-create, workspace make via the workspace maker). It must
be dispatched only to an agent whose registered charter (config/agent_registry.json)
permits running repository/shell commands.

ACD-2100b-5 moved the registry read OUT of this workflow body. The E2
engine (ADR-030) contextifies this body with EXACTLY agent, parallel,
pipeline, phase, log, args, workflow, budget — no module loader and no
filesystem primitive of any kind (canonical statement: unit_tests/
_workflow_engine_harness.py docstring, "ENGINE FIDELITY" section) — so
this workflow physically cannot read config/agent_registry.json itself.
The agent()-dispatch round-trip this section used to make existed only to
work around that sandbox; it is gone. The plan-feature SKILL now runs a
LOCAL pre-flight script (scripts/worktree/check_workspace_setup_permission.py)
BEFORE invoking this workflow — the skill runs in the main agent loop,
which has real Bash/Read access — and passes that script's verdict through
`args.workspace_setup_permission`, the only injected global that carries
caller-supplied data. This workflow makes NO agent() dispatch and touches
no filesystem for this check at all; it only consumes the pre-computed
verdict, and fails closed whenever one does not reach it.
```

## Final-gate falsy-result guard

Explains: the `_finalGateResult` guard in the final gate of the pipeline loop.

```text
ACD-2100c-2: resolveGate() never returns a falsy value TODAY -- every
path out of it is either one of the four pause-related statuses
handled above (which return before this line), or a decision object
from applyAnswerByType(). The `|| { action: "defer" }` fallback that
used to sit here was unreachable dead code and was removed for
clarity with no behaviour change at the time.

ACD-2100c-5: that "never returns falsy" property is a fact about
resolveGate()'s CURRENT body, not a contract enforced at this call
site -- the next refactor of resolveGate() (or a future sixth gate)
can silently reintroduce a falsy return, and a test written only
against the destructive-fallback LINE would have been deleted along
with it, letting the invariant lapse unnoticed (this AC's own
test_rationale). So this guard is restated here as a standing
invariant over the exit path, not a repair to one known line: a
missing/falsy gate result is a gate FAILURE (KI-ACD-005), never a
user cancellation and never a silent "defer" -- it must fail CLOSED
with the same "undetermined" vocabulary the other four call sites
already use, so the drafted work is never discarded and no stop is
ever attributed to the person on this path.
```

## DECISION HISTORY

Explains: the whole file (formerly the DECISION HISTORY tail of plan-feature.js).

```text
DECISION HISTORY
================================================================================
- 2026-09-25 [python-coder]: /quick-fix, live incident wf_734389cf-248 (run
  itpo-split-20260925 ended pause_persist_failed because status-checker
  refused pause_store.py write as outside its scope; see docs/known-issues/
  build-orchestration/open-high-ki-bo-20260901-1620.md). (1) BO-2300a-1-ii:
  repointed the pause-store round trip and resolve-worktree-setup-script-
  path from "status-checker" to "worktree-agent" (permits_shell: true).
  Main-body dispatches use the module-level `workspaceSetupAgentId`
  (~l.2342); peekPausedGateId()/resolveGate()/pauseAtGate() each use their
  OWN local `_shellPermittedAgentId` instead, because those three are
  extracted VERBATIM into a standalone Node driver (no top-level body) by
  test_acd_2100c_1.py's TestSixthDecisionPointInheritsTheRule -- confirmed
  by direct execution to ReferenceError otherwise. Does not narrow
  args.workspace_setup_agent's override contract (that only ever covered
  the worktree-BOOTSTRAP dispatch, ACD-2100b/BO-1500f-1; confirmed by grep
  no test asserts these six honor it). (2) BO-1500a-5-i: the Pre-Stage-0
  bootstrap previously fail-hard ONLY on an explicit non-zero exit_code; a
  refusal, an uninterpretable reply, a success-shaped reply naming no
  worktree_path, or a no-failure reply naming neither a directory nor a
  branch all fell through silently. All four now halt via the shared
  buildSetupFailureResult() helper with a distinguishing
  setup_failure_kind before any authoring agent is dispatched. See
  unit_tests/_plan_feature_harness_defaults.py's DECISION HISTORY for the
  companion harness-side default this required. (quick-fix; no ticket)
```

## Flow-ref recovery: parsing git log by commit header

Explains: `recoverFlowRefFromCommit()`.

```text
Parse per-commit by scanning lines. Real `git log --name-only
--format=%H%x00%s` output is: a header line `<hash>\x00<subject>`, a BLANK
line, then the commit's file list — with NO blank line between one commit's
last file and the next commit's header. A blank-line split therefore
misaligns headers and files. Instead, treat any line containing \x00 as a
new commit header (recording its subject) and collect the subsequent
non-empty lines as that commit's files until the next header. Return the
first *.flow.json belonging to a commit whose subject matches the FLOW stage.
```

## Shape-valid is not person-authored

Explains: The `channel` provenance check in `resolveGate()`.

```text
ACD-2100c-4: shape-valid is not the same as person-authored. A
well-formed, enum-valid answer can be constructed by anything with
write access to args.resume_answer (an automated agent, a stale
replay, a test) -- validateAnswerShape() cannot and must not be asked
to tell the difference, because that would put content back in charge
of the decision this AC exists to gate. Provenance is checked as a
property of the answer itself (`channel`), never inferred from its
content: only `channel === "person"` is treated as the person's own
decision. Anything else -- a different value, or the field's absence
-- is refused exactly like an unanswered gate (same
"paused_awaiting_input" status, same gate_id, record left untouched
below), except the terminal payload also names WHY: provenance, never
a shape/parse complaint, so the journal cannot read this refusal as
"could not understand the answer" (KI-ACD-005).
```

## Carrying the pause record context back to the caller

Explains: The `_resumedContext` hand-back in `resolveGate()`.

```text
ACD-2100c-3 AC-1/AC-2: carry the pause record's own context snapshot
back to the caller so the step(s) BEFORE this decision point are not
re-dispatched on resume -- the caller recovers the AC ids already
drafted (and left on disk, untouched) by the paused run from the
persisted record instead of re-running the authoring agent.
```

## Clearing the pause record once the run moves past the gate

Explains: The pause-record clear in `resolveGate()`.

```text
ACD-2100c-3 AC-4: once the resumed run has moved PAST this decision
point, no record of it waiting must remain on disk. "edit" does NOT
move past the gate -- it re-dispatches the step with feedback and
re-presents essentially the same decision -- so the record is
deliberately left in place for that one answer type; every other
answer clears it here, before the caller performs the work (commit /
PR / terminal return) that actually commits the run past the gate.
Ordering matters (see this ticket's Implementation Notes): if the
process dies between this clear and that later work, the run is left
uncommitted-but-not-listed-as-waiting rather than the worse state of
committed-yet-still-listed-as-waiting.
```

## A failed pause-record clear must be observable

Explains: The clear-failure branch in `resolveGate()`.

```text
Fail loudly, not silently: a stale record left behind makes this
run look permanently paused to any later reader (AC-4). This does
NOT block the caller from proceeding past the gate — the answer
has already been validated and applied above, and the ordering
comment before this block explains why the clear happens before
the caller's own commit/PR/terminal-return work — but the failure
must be observable, not discarded.
```

## No matching resume answer: the run pauses

Explains: The pause-and-persist tail of `resolveGate()`.

```text
No matching resume_answer: the ONLY remaining channel that reaches the
person running the route is a pause-and-persist record surfaced through
this run's own terminal payload (ACD-2100c-1 / KI-ACD-005). `liveGateFn`
is still accepted as a parameter — every one of the five existing call
sites, plus any future one, still builds and passes it — but it is
deliberately NEVER invoked. Its whole purpose was to dispatch an agent()
call to obtain a human answer by proxy, which is exactly the dispatch
this AC forbids ("no dispatch whose purpose was to obtain an answer to
any of the five"). Leaving the closure unread rather than deleting the
parameter (which would force a signature change at every call site) is
what makes the guard live on THIS function — the class every decision
point routes through — instead of on a per-site opt-out that a sixth,
newly added gate would have to remember to apply.
```

## The pause payload carries the question

Explains: The terminal payload of `pauseAtGate()`.

```text
Carry the actual question content in the terminal payload (ACD-2100c-1):
in this sandboxed E2 body the run's own top-level return value is the
ONLY channel back to the caller (the /plan-feature skill, running in the
human's own session). A bare `gate_id`/`status` pair forces that caller
to separately look up what is being asked; `question` is the exact
object already built above for the persisted record, just never
returned until now.
```

## No pre-flight verdict at all fails closed

Explains: The Pre-Stage-0 workspace-setup permission check.

```text
Fail closed when NO pre-flight verdict reaches this workflow at all. A
caller that invokes this workflow directly — e.g. Workflow({ scriptPath:
'.leafcutter/workflows/plan-feature.js' }), a real, currently-used
invocation path that bypasses the skill's own pre-flight step entirely —
supplies no such verdict. This is a DISTINCT fact from "the pre-flight ran
and denied permission" (handled below): the report here must name the
MISSING pre-flight itself, never assert a permission cause this run never
established (ACD-2100b-5 it_requirements; this is a new outcome of the
startup path and must not be worded as any of ACD-2100b-1/-2/-3's outcomes).
```
