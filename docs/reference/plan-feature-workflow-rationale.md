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
`install_shims` populates on the project's own checkout; `git worktree add`
only ever checks out TRACKED content). `git rev-parse --git-common-dir`
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
(fetch, branch-create, worktree-add via setup_ticket_worktree.py). It must
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
