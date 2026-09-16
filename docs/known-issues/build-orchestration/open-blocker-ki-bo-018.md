---
title: "KI-BO-018 — `/plan-feature` halts on a false `worktree-agent` permission verdict, caused by a truncated agent-relayed config read rather than anything wrong with the agent's charter"
description: "blocker — this is not a workflow inconvenience: per ADR-012, `/plan-feature`"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-018 — `/plan-feature` halts on a false `worktree-agent` permission verdict, caused by a truncated agent-relayed config read rather than anything wrong with the agent's charter

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`blocker`); the
> original grading is the `**Severity:**` line below, unchanged.

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

**CROSS-REFERENCE, 2026-09-16 — now covered by `BO-3200g`.** The shape recorded here —
a relayed config read whose **transport** failure is fail-closed into a **substantive and
false verdict** about an agent's permissions — recurred on 2026-09-16 in
`/plan-feature` with a different transport failure: not truncation, but a **charter
refusal**. `status-checker` declined the read as out of scope and fabricated
`exit_code: 1` inside its refusal payload, so the run reported "exit code 1, no stdout"
and blamed an unreadable 131 KB file that was present and readable at both candidate
locations. See `KI-ACD-009`.

The generalisation is that a failure in the **layer carrying the answer** must never be
rendered as a finding about the **subject**. That is now `BO-3200g`; the removal of the
relay itself is `BO-3200f`. `BO-3200e` remains the adjacent-but-distinct record — it
governs what a *check* reports once it knows its inspection did not happen, whereas these
two govern whether the check is ever told the truth about that.

---
