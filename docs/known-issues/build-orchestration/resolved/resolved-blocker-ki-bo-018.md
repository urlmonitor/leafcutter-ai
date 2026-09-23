---
title: "KI-BO-018 — `/plan-feature` halts on a false `worktree-agent` permission verdict, caused by a truncated agent-relayed config read rather than anything wrong with the agent's charter"
description: "blocker — this is not a workflow inconvenience: per ADR-012, `/plan-feature`"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-09-23'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-018 — `/plan-feature` halts on a false `worktree-agent` permission verdict, caused by a truncated agent-relayed config read rather than anything wrong with the agent's charter

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../../build-orchestration.md).
> Filename severity is the three-level index bucket (`blocker`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** blocker — this is not a workflow inconvenience: per ADR-012, `/plan-feature`
  is the canonical entry path for **all** new work, and this defect halts that workflow
  before any authoring agent is dispatched. There is no fallback path that avoids it.
- **Status:** **RESOLVED 2026-09-23** — see the dated closure note at the foot of this entry.
  Original line, preserved: open — no AC
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

**Closed 2026-09-23.** Re-verified against the current code, not this entry's narrative:

- **Primary mechanism confirmed gone.** No `resolve-workspace-setup-permission` dispatch, and
  no read of `config/agent_registry.json` via an agent round-trip, remains anywhere in
  `templates/workflows-js/plan-feature.js`. Lines 2140-2148 document the removal directly:
  "ACD-2100b-5 removed that dispatch (the registry read now happens locally, in
  `scripts/worktree/check_workspace_setup_permission.py`...) and these four helpers had no
  other caller, so they were removed with it." Lines 2320-2432 show the workflow now only
  consumes a pre-computed verdict via `args.workspace_setup_permission`, failing closed when
  it is absent (a distinct, correctly-worded outcome from a denial), and rendering six
  distinguishable `outcome` values (`granted`, `read_failure`, `parse_failure`,
  `agent_not_found`, `no_entries_collection`, `permission_denied`) as six different messages —
  exactly this entry's own "Fix direction".
- **The verdict is produced by a pure local script, not a dispatch.**
  `scripts/worktree/check_workspace_setup_permission.py` reads
  `<repo_root>/.leafcutter/config/agent_registry.json` directly (`_load_registry()`), makes no
  agent call and no network call, and is invoked by the `plan-feature` skill (real Bash/Read
  access) before the workflow runs — never by the workflow body itself, which the E2 engine
  gives no filesystem primitive to (confirmed at check_workspace_setup_permission.py:22-34).
- **Secondary observation (cwd) also confirmed fixed.** Both
  `_buildRepoRootResolutionSnippet()` (plan-feature.js:2062-2097) and the pre-flight's own
  `resolve_repo_root()` (check_workspace_setup_permission.py:155-188) resolve the repository
  root via `git rev-parse --git-common-dir` (worktree-aware), with the documented three-step
  fallback: the start directory itself, then its immediate non-hidden children, then its
  parent's immediate non-hidden children — the ADR-001 self-hosting sibling-directory case
  this entry's secondary observation names. Neither ever falls back to a bare cwd-relative
  read.
- **Behavioral evidence, not just narrative.**
  `AC_ENFORCE_STRICT=1 python -m pytest unit_tests/workflows/test_bo_1500f_1.py unit_tests/workflows/test_bo_1500f_1_real_registry_read.py -q`
  → 8 passed (re-run 2026-09-23, mask off). `BO-1500f-1.yaml` confirmed `work_status: done`,
  `readiness: approved`.
- **Duplicate, confirmed and cross-linked.** This is the same mechanism and the same cwd
  defect as `KI-ACD-009`
  ([`docs/known-issues/ac-driven-dev/resolved/resolved-blocker-ki-acd-009.md`](../../ac-driven-dev/resolved/resolved-blocker-ki-acd-009.md)),
  which records the identical 2026-09-07 `ACD-2100b-5` fix and was itself closed 2026-09-23
  once its own closure condition (the `BO-1500f-1` store transition) landed via PR #864. This
  entry is closed as a duplicate resolution, not an independent one.

---
