---
title: "ADR-078: Which Runtime /plan-feature's Pause, Resume and Human Gates Run On"
description: "Open choice between hardening the E2 workflow engine (A), moving /plan-feature onto the LangGraph decision kernel (B), or shipping a standalone LangGraph graph (C). Work every option needs can start now. The shared JS gate block and a run-state script wait for the choice, because under B or C LangGraph's interrupt, checkpointer and the kernel's interaction ledger would replace both."
type: "adr"
status: "active"
created: "2026-10-25"
last_updated: "2026-10-25"
deciders:
  - BrainCandy
components:
  - build_orchestration
  - ac_driven_dev
  - decision_kernel
  - finalize
related_docs:
  - docs/architecture/adrs/ADR-024-interactive-pause-resume.md
  - docs/architecture/adrs/ADR-030-dual-engine-workflow-support.md
  - docs/architecture/adrs/ADR-052-capabilities-replace-agents-prompts-are-compiled.md
  - docs/architecture/adrs/ADR-054-process-representation-and-maturity-model.md
  - docs/architecture/adrs/ADR-055-capability-registry-starts-empty.md
  - docs/architecture/adrs/ADR-070-shell-runner-runs-workflow-shell-commands.md
  - docs/architecture/components/interactive-pause-resume-substrate.md
  - docs/architecture/components/decision-kernel.md
  - docs/acceptance-criteria/build-orchestration/BO-4500-fix-once-every-route/BO-4500.yaml
  - docs/roadmap.md
related_code:
  - templates/workflows-js/plan-feature.js
  - templates/workflows-js/finalize-feature.js
  - templates/workflows-js/_shared/README.md
  - scripts/pause_store.py
  - templates/scripts/commit_changes.py
  - templates/scripts/worktree.py
  - kernel/scheduler/nodes_interaction.py
  - kernel/interaction/ledger.py
  - kernel/interaction/submissions.py
  - kernel/persistence/checkpointer.py
  - kernel/adapters/claude_code/SKILL.md
  - requirements-dev.txt
---

# ADR-078: Which Runtime /plan-feature's Pause, Resume and Human Gates Run On

## Status

| Field | Value |
|---|---|
| **Status** | Proposed — awaiting decision |
| **Date** | 2026-10-25 |
| **Author** | adr-author, for BrainCandy |
| **Deciders** | BrainCandy |
| **Supersedes** | None |

This record sets out the options and the author's recommendation. **No option has been
chosen.** The choice stays open until BrainCandy records it here.

---

## Context

### The E2 engine gives the gate code no shared home

Under [ADR-030](ADR-030-dual-engine-workflow-support.md), every workflow is an E2 top-level
body. That body has no `require`, no filesystem and no subprocess
([ADR-070](ADR-070-shell-runner-runs-workflow-shell-commands.md), "A workflow body cannot run
a command itself", lines 68-76). E2 also has no user-input global, so every person-facing gate
is an agent turn (ADR-030:201). Every shell command runs through a depth-1 agent. ADR-070
sends these to `shell-runner`, and any reply that is not a result ends the run (ADR-070 §5).
Shared logic can reach a workflow only by build-time marker inlining from
`templates/workflows-js/_shared/` (ADR-070 §6; `_shared/README.md`). Two blocks use this today:
`workspace-answer.js` and `commit-answer.js`.

The gate code has never been moved there. `plan-feature.js` (3,169 lines) and
`finalize-feature.js` each carry a hand-copied `validateAnswerShape`, `applyAnswerByType`,
`resolveGate` and `pauseAtGate`. The copies are at plan-feature.js:1514, :1541, :1649 and :1756,
and at finalize-feature.js:277, :303, :328 and :395. Finalize's copy is headed "keep them in
sync" (finalize-feature.js:263-268). The copies have already drifted. Fixes reached
plan-feature only, so finalize's merge-to-main gate can be passed by an agent's answer. This
is [KI-BO-20260925-finalize-gate-accepts-agent-answers](../../known-issues/build-orchestration/open-blocker-ki-bo-20260925-finalize-gate-accepts-agent-answers.md)
(blocker).

### Resume state is rebuilt from git by agents

A resumed run does not load its own state. Agents rebuild it by scanning git and the AC store:
`scanOrphanedAcDrafts` (plan-feature.js:608), `scanCommittedStages` (:817) and
`recoverFlowRefFromCommit` (:1362). The pause record itself is written and read through agents
that call `scripts/pause_store.py`. Four open known issues come from this design:

- [KI-ACD-20261009-resume-reclassifies](../../known-issues/ac-driven-dev/open-high-ki-acd-20261009-resume-reclassifies.md)
  (high): on resume, the classifier is asked again and the owner's answer is dropped.
- [KI-ACD-20261009-resume-reads-own-drafts-as-orphans](../../known-issues/ac-driven-dev/open-high-ki-acd-20261009-resume-reads-own-drafts-as-orphans.md)
  (high): a resumed run offers its own reviewed drafts back as crash orphans.
- [KI-ACD-20260927-po-origin-agent-defeats-partial-run-recovery](../../known-issues/ac-driven-dev/open-low-ki-acd-20260927-po-origin-agent-defeats-partial-run-recovery.md)
  (low): crash recovery depends on `origin_agent` values that the PO template does not write.
- [KI-BO-20260928-pause-verify-rejects-an-enveloped-read-back](../../known-issues/build-orchestration/open-high-ki-bo-20260928-pause-verify-rejects-an-enveloped-read-back.md)
  (high): the read-back check rejects a written pause record because an agent wrapped it in an
  envelope.

Hardening E2 can fix each of these one at a time. The common cause stays: a run's state lives
nowhere the run can load it from directly.

### LangGraph is already in the repo, but only for the kernel

`requirements-dev.txt:61-62` pins `langgraph==1.2.12` and `langgraph-checkpoint-sqlite==3.1.1`.
The repo ships no adopter-facing requirements file. The decision kernel already has the parts a
durable human-in-the-loop needs:

- **Pause:** `kernel/scheduler/nodes_interaction.py:22,133` pauses with `interrupt()`.
- **Idempotent answers:** `kernel/interaction/ledger.py:3-11,149-167` writes a first-write-wins
  submission ledger entry before `Command(resume=…)`.
- **Checkpoints:** `kernel/persistence/checkpointer.py:23,55-75` builds an `AsyncSqliteSaver`.
- **Human vs host answers:** `kernel/interaction/submissions.py:5-8` says a host result "can
  never answer a human question, approve, or grant permissions".
- **Claude Code transport:** `kernel/adapters/claude_code/SKILL.md` has the session carry
  `waiting_host` / `waiting_human` packets.

**The human/host split is self-declared, not authenticated.** `_route_problem` compares
`raw["actor"].get("kind")` with the kind the packet expects (submissions.py:127-131, 151-154).
`Actor` is just `{id, kind}` (kernel/contracts/task.py:27-31). `ActorKind` is
`human | host | service` (kernel/contracts/enums.py:172-177). The Claude Code skill tells the
session to write `{"kind": "human", "id": "human:user"}` into the submission file itself
(SKILL.md:67-69). So the kernel catches an honest mistake. It does not stop an agent that
claims to be the person, which is exactly the finalize blocker's failure mode.

### Roadmap, shipping and neutrality limits

- **The kernel is not shipped.** `docs/roadmap.md:162` says it "lives in leafcutter-ai only;
  not shipped to adopters". Engineering workflows on the kernel are
  `phase_kernel_3_workflows`, which is Planned (roadmap.md:182-184).
- **A kernel run needs a Jev credential.** `RunService.start_run` refuses to start without
  one (kernel/service.py:139, 220-223).
- **Adopters get plan-feature.** The current phase_1 outcome is a portable MVP that installs
  into any project, and `/plan-feature` ships to adopters. Workflow scripts are deployed only
  when `workflows.enabled` is set (scripts/build_phases_workflows.py:151-152).
- **Neutrality.** [BO-4500](../../acceptance-criteria/build-orchestration/BO-4500-fix-once-every-route/BO-4500.yaml)
  (lines 106-109) and BO-4500b (lines 122-124) require shared steps to keep working if routes
  move to LangGraph or the Claude Agent SDK.
- **Kernel capabilities.** Under [ADR-052](ADR-052-capabilities-replace-agents-prompts-are-compiled.md)
  and [ADR-054](ADR-054-process-representation-and-maturity-model.md), a known sequence belongs
  in a LangGraph workflow. Under [ADR-055](ADR-055-capability-registry-starts-empty.md), legacy
  agents such as PO, BA and IT PO enter the kernel registry only through a `legacy_admission`
  that names an ADR.

These pieces work the same under every option: the workspace maker (`templates/scripts/worktree.py`),
the shared commit step (`templates/scripts/commit_changes.py`, BO-4500a), `scripts/pause_store.py`
and the AC-store writers. The LLM stages (PO, BA, IT PO) stay Claude Code work under every
option. In the kernel, they would be `host.*` handoffs.

### Cost of not deciding

Without a decision, the next step by default is option A's shared GATE-ANSWER block plus a
`plan_run.py` run-state script. That work is wasted if B or C is chosen. Meanwhile the finalize
blocker and the three high resume KIs stay open.

---

## Decision

**Proposed — awaiting decision.** BrainCandy has not chosen between A, B and C. The
sub-decisions below are the author's proposal. They bind only once the Status row reads
Accepted, and §3 binds only with the option filled in.

### 1. Work safe under every option (proposed to start now)

Each item reuses framework-neutral pieces and survives a move to LangGraph:

1.1 plan-feature's commits MUST go through the shared commit step. This is
[BO-4500a-5-ii](../../acceptance-criteria/build-orchestration/BO-4500-fix-once-every-route/BO-4500a-5-ii.yaml):
in progress, with `work_status: todo` in the store at 411b87761.

1.2 A stage-set script MUST name the parent AC each stage edited, so the commit stages the
parent with its children.

1.3 One hardened AC-record writer MUST replace the per-stage agent writes.

1.4 Every workspace root plan-feature uses MUST come from the workspace maker's answer and
never from the current checkout.

1.5 Finalize's merge gate MUST get a minimal fix at the call site that accepts only a
person's answer. This is the KI-BO-20260925 blocker fix, and it MUST NOT wait for §3.

### 2. Work deferred until §3 is decided

2.1 The shared JS GATE-ANSWER `_shared/` block MUST NOT be built before §3 is decided.

2.2 `plan_run.py` (a run-state script) MUST NOT be built before §3 is decided.

Under B or C, LangGraph's `interrupt()`, its checkpointer and the kernel's interaction ledger
replace both. Building them first would be duplicate work.

### 3. Runtime choice — OPEN

| | A: harden E2 | B: kernel | C: standalone LangGraph graph |
|---|---|---|---|
| Run state | Agent-relayed pause record + `plan_run.py` | Kernel checkpointer + run store | Its own `AsyncSqliteSaver` |
| Gate code | Inlined `_shared/` block | `interrupt()` + ledger + `check_submission` | `interrupt()` + the same ledger/check, imported, not copied |
| Adopter dependency | None new | Kernel + Jev credential + langgraph | langgraph + checkpoint-sqlite only |
| Ships to adopters today | Yes | No (roadmap.md:162) | Only with a new adopter requirements file |
| Fixes the resume-KI cause | No: each KI patched one by one | Yes | Yes |
| Person-only answers | Needs new work | Needs new work: actor kind is self-declared | Needs new work: same |

**Author's recommendation (not a decision): lean towards C.** C gets the LangGraph pause,
checkpoint and ledger model that removes the git-scan resume class. It also avoids the two
facts that stand against B in phase_1: the kernel is not shipped, and every kernel run needs a
Jev credential. C is recommended on one condition: the plan-feature graph MUST import the
kernel's submission check and ledger from one shared module, not a copy. Copying them would
repeat the "keep them in sync" failure one level up. Under the recommendation, C
gives way to B once `phase_kernel_3_workflows` ships the kernel to adopters.

**Questions that must be answered before §3 is decided:**

- **Q1 Adopter shipping.** Can phase_1 add langgraph and checkpoint-sqlite to adopter
  installs? Or does plan-feature become repo-only until the kernel ships?
- **Q2 Answer attribution.** How is a person's answer attributed so that it is not
  self-declared? Today `actor.kind` is written by the same session that does host work.
- **Q3 Host handoffs.** How do host handoffs run inside a Claude Code session? Who drives the
  graph, the session or a CLI the session calls, and how does that fit the depth-1 limit?
- **Q4 Paused runs.** What happens to runs paused under `.leafcutter/paused_runs/` when the
  runtime changes: migrate them, finish them under E2, or discard them with notice?

---

## Consequences

### Positive

- §1 removes the finalize blocker and the commit and parent-staging faults now, without
  waiting for the runtime choice.
- §2 avoids building a JS gate layer and a run-state script that B or C would throw away.
- Q2 is raised for all three options. The attribution gap exists in the kernel too, not just
  in E2.

### Negative

- The deferral leaves the three high resume KIs open until §3 is decided and built.
- C adds the first third-party runtime dependency to adopter installs (Q1).
- C still overlaps the kernel until phase_kernel_3, even with the shared module.
- B makes plan-feature depend on Jev and an unshipped component.

### Operational

- Finalize's call-site fix (§1.5) is a stopgap. Finalize's gate copy stays hand-kept until a
  later change removes it under the chosen option.
- Whichever option is chosen, it MUST come with a migration note for paused runs (Q4).

---

## Alternatives

None of A, B or C is rejected yet. They are the open options in §3. Each one's case
against is recorded here so it can be checked when the choice is made:

- **A — harden E2.** Its case against: the resume KIs come from rebuilding state by scanning
  git through agents, and a shared block does not change that. It also adds a third inlined
  block to an engine that the BO-4500 neutrality clause expects routes to leave.
- **B — kernel.** Its case against, for phase_1: the kernel is not shipped (roadmap.md:162),
  every kernel run needs a Jev credential (service.py:220-223), and PO, BA and IT PO would
  each need an ADR-055 `legacy_admission`.
- **C — standalone graph.** Its case against: a second LangGraph host in the repo, and a new
  adopter dependency. If the kernel's interaction code were copied rather than imported, it
  would recreate the drift behind the finalize blocker.
- **Build the shared GATE-ANSWER block and `plan_run.py` now, whatever the choice.** The author
  recommends against this: under B or C they are replaced by `interrupt()`, the checkpointer and
  the ledger, so the work would be thrown away.

---

## References

- [ADR-024](ADR-024-interactive-pause-resume.md): the current pause/resume substrate.
- [Interactive pause/resume substrate](../components/interactive-pause-resume-substrate.md)
  and [decision kernel](../components/decision-kernel.md) component docs.
- [BO-4500a-5-ii](../../acceptance-criteria/build-orchestration/BO-4500-fix-once-every-route/BO-4500a-5-ii.yaml):
  plan-feature commits through the shared step.
