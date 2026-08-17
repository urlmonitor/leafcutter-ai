---
title: "ADR-024: Interactive Gates Pause and Persist Instead of Cancelling When Headless"
description: "Records the decision to replace the cancel-on-headless behaviour of interactive workflow gates with a pause-and-persist substrate. When no human is reachable, a gate terminates the run cleanly, writes a durable pending-question record keyed by run id under .leafcutter/paused_runs/, and returns a distinct paused_awaiting_input status instead of silently resolving to a safe default and exiting with status ok. Resume re-invokes the same workflow with the human's answer available and resumeFromRunId set so the harness replays committed agent() calls, execution deterministically reaches the same gate, and resolveGate() consults the record's answer before making the gate's agent() call. Covers the shared substrate helper imported by plan-feature.js, build-feature.js, and finalize-feature.js, the answer-application-by-type contract, question-type validation, durability and idempotency, and the E2/ADR-030 body constraints."
type: "adr"
status: "active"
created: "2026-07-20"
last_updated: "2026-07-20"
deciders:
  - BrainCandy
components:
  - build_orchestration
related_docs:
  - docs/architecture/adrs/ADR-030-dual-engine-workflow-support.md
  - docs/architecture/adrs/ADR-001-self-hosting-boundary.md
  - docs/reference/workflow-constraints.md
  - docs/reference/workflow-authoring-contract.md
  - docs/architecture/components/build-orchestration.md
  - docs/acceptance-criteria/build-orchestration/BO-2300-interactive-pause-resume/
related_code:
  - templates/workflows-js/plan-feature.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/finalize-feature.js
---

# ADR-024: Interactive Gates Pause and Persist Instead of Cancelling When Headless

## Status

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-07-20 |
| Deciders | BrainCandy |
| Author | adr-author |
| Supersedes | — |

## Context

The E2 workflow engine (Claude Code's built-in Workflow runtime; scripts live in
`templates/workflows-js/*.js`, top-level-body form per ADR-030) executes workflow
bodies deterministically and statelessly. There is **NO `prompt()` primitive** in
E2 — every user gate is implemented as an `agent()` turn dispatched to
`status-checker` that is expected to relay a question to a human and return
`{ action: ... }`.

**Defect.** When a run is headless/background (no human reachable), the
`status-checker` cannot get an answer. The parse-failure catch blocks in
`templates/workflows-js/plan-feature.js` then resolve gates to hardcoded safe
defaults — `{ action: "cancel" }` for mid-stage/product-truth gates,
`{ choice: "cancel" }` for the covered-route gate, `{ action: "defer" }` for the
final gate — each of which immediately `return`s and exits the workflow with
`status: "ok"`. In `finalize-feature.js` the Step 4 merge gate (schema-enforced)
returns `{ status: "blocked" }` → the workflow returns
`{ status: "halted", reason: "user_declined_merge" }`. In all cases the run
silently gives up and discards the pending decision; no state marking "paused at
gate X" is persisted. `build-feature.js` has NO interactive gates today.

**Concrete real-world instance.** This design session's own `/build-feature` run
was disrupted; the cancel-on-headless behaviour is exactly what bites background
automation.

**Key finding that shapes the decision.** The AC constraints repeatedly said to
"align with the existing `resumeFromRunId` run-resume cache" and "how the existing
crash-resume run state is persisted." Investigation found:

- `resumeFromRunId` is a **harness** mechanism (a parameter of the Workflow tool),
  NOT a repo artifact. On resume the Claude Code runtime replays completed
  `agent()` calls from the run's `journal.jsonl` in the transcript dir
  (`.claude/projects/.../workflows/wf_*/`). No repo file implements it; the term
  appears nowhere in the codebase.
- There is **NO in-repo durable pending-question store.** The repo's own resume
  mechanisms are: git-commit-log parsing (`scanCommittedStages` in
  `plan-feature.js`, keyed on commit subjects like `"plan-feature(BA):"`) and the
  ticket frontmatter `agents:` map (`build-feature` phases).
- A workflow body **cannot** block mid-process waiting for a human — it runs to
  completion, errors, or is stopped, then is re-invoked with `resumeFromRunId` to
  replay cached `agent()` results.
- A workflow body has **no filesystem or Node.js access** (per
  docs/reference/workflow-constraints.md). It therefore cannot write or read the
  pending-question record itself — all persistence must be **agent-mediated** (an
  `agent()` dispatch, since agents carry Bash/Write tools), and on resume the
  human's answer is supplied via `args`.

## Decision

Introduce a **"pause-and-persist" substrate**.

- **PAUSE** = terminate the run cleanly, persist a pending-question record, and
  return a distinct status.
- **RESUME** = re-invoke the same workflow with the human's answer available and
  `resumeFromRunId` set, so the harness replays committed `agent()` calls,
  execution deterministically reaches the same gate, and the gate now finds the
  answer and proceeds.

The following rules realise this decision. Each is a binding commitment.

1. **New durable artifact — the pending-question record**, keyed by run id, at
   `<repo>/.leafcutter/paused_runs/<run_id>.json`. It MUST survive process exit.
   Because the E2 body has no filesystem access, the record is written and read
   **via an `agent()` dispatch** (the dispatched agent may invoke a small Python
   helper to do the actual JSON read/write) — never by `fs` calls in the workflow
   body. The engine integration (gate migration, `resolveGate`, returning
   `paused_awaiting_input`) is JavaScript in the workflow files.
   Shape:

   ```json
   {
     "run_id": "string",
     "status": "paused_awaiting_input | cancelled | running | completed",
     "question": "<object, shape from BO-2300b-1>",
     "context": "<snapshot, shape from BO-2300c-1>",
     "pause_point": "<resume marker referencing the resumeFromRunId run + gate id>",
     "answer": "object | null"
   }
   ```

   Required fields: `run_id`, `status`, `question`, `pause_point`.

2. **Distinct status `paused_awaiting_input`.** A paused run MUST return
   `paused_awaiting_input` — never `"ok"`, never `"cancelled"`. Only
   `paused_awaiting_input` is resume-eligible (BO-2300a-2).

3. **Inlined substrate helper (not an imported module).** The pause/resume helper
   — `resolveGate()`, `validateAnswerShape()`, `applyAnswerByType()` — is defined
   **inline** in each engine file that has gates (`plan-feature.js`,
   `finalize-feature.js`; `build-feature.js` has no gates). E2 workflow bodies are
   self-contained and **cannot import local modules** (an ES-module `import` is a
   SyntaxError inside the harness's async IIFE, and the runtime provides no module
   access), so a single shared imported module is not viable. The `n_location_rule:
   all` requirement is satisfied by *migrating every gate* across the engine files,
   not by a physical shared module. The inline copies MUST be kept identical; a
   future build-time injection (build.py) could dedupe them from one source, but no
   runtime import is possible. (An earlier draft shipped an unimported
   `pause-resume-substrate.js` ES module; it was dead code and has been removed.)

4. **CORRECTNESS KEY: `resolveGate()` MUST consult the record's `answer`
   (supplied via the resume `args`, or read by a resume `agent()` dispatch)
   BEFORE making the gate's live `agent()` call.** Otherwise, on resume the harness
   replays the cached headless-default answer and re-cancels. Checking the answer
   first is what makes resume correct and idempotent (BO-2300e-1-i).

5. **Answer application by type (BO-2300d-1).** The substrate MUST apply the
   answer according to its type:
   - `approve` → proceed past gate
   - `edit` → re-dispatch the step with feedback
   - `cancel` → graceful stop (keep committed stages, open no PR)
   - `priority_choice` → set run priority
   - `free_text` → carry into the step

   Resume MUST continue from the pause point — completed/committed stages MUST NOT
   be re-run.

6. **Question types + validation (BO-2300b-1/-2/-2-i).** Each gate MUST declare its
   type (`single_choice | priority_choice | free_text`) and valid answer shape. A
   wrong-shape or unparseable answer MUST be rejected (not applied); the run MUST
   stay paused and re-present the same question — it MUST NOT crash.

7. **Durability (BO-2300e-1 + edges).** The record MUST survive process exit and
   resume in a new process. On resume, before applying a valid answer,
   `resolveGate()` checks the record's state via an agent-mediated **`read-pause-record`**
   dispatch (`agent({run_id, gate_id}, {label: "read-pause-record"})`; the agent
   reads the durable file, the body does no fs). The substrate MUST guard against
   idempotent double-apply. Resuming a run whose record is absent (`{exists: false}`)
   MUST be a no-op that reports "nothing to resume" (not an error). A stale/expired
   pause (`{stale: true}`) MUST be reported as unresumable with a reason rather than
   silently corrupting state.

8. **Idempotent pause (BO-2300a-1).** Re-reaching the same gate for an
   already-paused run MUST NOT create a duplicate record.

9. **Error-handling policy.** All state-store reads/writes are external I/O and
   MUST follow the project error-handling policy (typed except, WARNING+ log, no
   bare except, no silent swallow). Pause/persist transitions MUST be logged for
   observability.

10. **E2/ADR-030 constraints.** The workflow body MUST NOT use `Date.now()` /
    `new Date()` / `Math.random()` (timestamps/seed MUST be passed via args). The
    change MUST preserve `build.py` round-trip parity (ADR-001) via
    `python scripts/build.py --target-dir .`.

## Consequences

### Positive

- Background/headless runs no longer silently cancel and discard in-progress work
  at interactive gates.
- A paused run is durable and resumable across process exit — the human can answer
  the gate question minutes or hours later.
- Every gate across the three engine files shares one audited mechanism
  (`resolveGate()`), so the correctness invariant is maintained in a single place.
- `paused_awaiting_input` is a first-class, unambiguous status — operators and
  tooling can distinguish "waiting for input" from "done" and "cancelled" without
  inspecting log output.

### Negative / follow-ups

- Introduces a new on-disk store (`.leafcutter/paused_runs/`); care is needed to
  purge stale records and keep the store from growing unboundedly.
- Resume depends on the harness `resumeFromRunId` contract remaining stable; if
  that contract changes (e.g. journal format, replay ordering), the substrate must
  be updated in lockstep.
- "Align with existing" in the original ACs is honoured in spirit — the design is
  keyed on `run_id` and relies on `resumeFromRunId` replay — but not by reusing a
  literal pre-existing store (none existed).
- The `edit` answer type (re-dispatch a step with feedback) requires the target
  step to be idempotent or to treat the re-dispatch as a superseding call; each
  gate implementation must document this contract.

## Alternatives

### Alternative A — Persist pause state via the existing git-commit-log pattern

Emit a `"PAUSED-AT-<gate>"` commit detected by `scanCommittedStages`.

**Rejected.** Couples pause state to commit history and is awkward for carrying
the question/context/answer payload across process exit. The question object
(including valid choices and the serialised context snapshot) is not appropriate
for a commit subject line.

### Alternative B — Fake a durable, blocking input channel inside the workflow script body

Block inside the workflow body waiting for a human answer via polling or a
side-channel file.

**Rejected.** The E2 body cannot block; the E2 runtime does not support mid-body
suspension. The harness `resumeFromRunId` re-invoke model is the only supported
resume mechanism. Faking a blocker inside the body would circumvent the
deterministic replay guarantee that makes `resumeFromRunId` correct.

> **Implementation note.** The architect-review ticket phase MUST confirm the
> script-vs-harness boundary before implementation begins — the correctness of
> RESUME depends on the harness replaying committed `agent()` calls in order, and
> any implementation that misunderstands where that boundary sits will produce
> incorrect behaviour.

## References

- [ADR-030 — Dual-Engine Workflow Support](ADR-030-dual-engine-workflow-support.md) — establishes the E2 top-level-body form that this ADR extends with the pause substrate.
- [ADR-001 — Self-Hosting Boundary](ADR-001-self-hosting-boundary.md) — the `build.py` round-trip parity constraint that the shared substrate module must satisfy.
- [docs/reference/workflow-constraints.md](../../reference/workflow-constraints.md) — E2 body constraints (no `Date.now()`, no blocking, no side-channel I/O) that the substrate must obey.
- [docs/reference/workflow-authoring-contract.md](../../reference/workflow-authoring-contract.md) — the authoring contract for `agent()` calls and `resumeFromRunId` replay semantics.
- [docs/architecture/components/build-orchestration.md](../components/build-orchestration.md) — the component that owns all three engine workflow files.
- [docs/acceptance-criteria/build-orchestration/BO-2300-interactive-pause-resume/](../../../acceptance-criteria/build-orchestration/BO-2300-interactive-pause-resume/) — the AC store for this epic; individual sub-tickets (BO-2300a through BO-2300e) carry the testable behavioral specs.
