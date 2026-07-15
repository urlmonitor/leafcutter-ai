---
title: "ADR-021: Always-On Product-Truth Authoring Phase in /plan-feature"
description: "Records the decision to wire the product-truth authoring agents (pt-classifier, mock-data-author, mockup-author, flow-author) into the /plan-feature workflow as an always-on phase between ac-triage and the AC pipeline. The classifier runs on every invocation and its outcome derives the run-set; artifact agents run in a fixed order behind per-stage approve/edit/cancel gates with surgical, commit-before-next commits; the approved flow is handed to the business-analyst and its reported flow_backlinks are reconciled into step.implements by apply_flow_backlinks.py; and the phase self-skips non-silently when the product-truth store is absent. Realises the flow-first authoring surface of ADR-020."
type: "adr"
status: "accepted"
created: "2026-07-14"
last_updated: "2026-07-14"
deciders:
  - BrainCandy
components:
  - ux_prototyping
  - ac_store
  - build_pipeline
related_docs:
  - docs/architecture/adrs/ADR-020-product-truth-flow-first-upstream-layer.md
  - docs/architecture/adrs/ADR-010-ac-store-as-authoritative-backlog.md
  - docs/product-truth/README.md
  - templates/skills/plan-feature/SKILL.md
related_code:
  - templates/workflows-js/plan-feature.js
  - docs/product-truth/scripts/apply_flow_backlinks.py
  - docs/product-truth/scripts/generate_product_truth.py
  - docs/product-truth/scripts/validate_product_truth.py
---

# ADR-021: Always-On Product-Truth Authoring Phase in /plan-feature

## Status

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-07-14 |
| Deciders | BrainCandy |
| Author | documentation-expert |
| Supersedes | — |
| Amends | — (realises ADR-020's flow-first authoring surface) |

## Context

ADR-020 established the **product-truth store** as the flow-first upstream layer:
flows are the primary product-intent artifact and acceptance criteria are *derived
from* flow steps. It named four authoring agents — `pt-classifier`,
`mock-data-author`, `mockup-author`, `flow-author` — and a `business-analyst`
hand-off that turns an approved flow into ACs.

Those agents existed and were registered, but **nothing dispatched them.** Every
product-truth artifact in the store had been walked by hand. `/plan-feature`
went straight from `ac-triage` into the AC pipeline (PO → BA → IT-PO), so a
feature was never actually "defined the product-truth way": no flow was drafted,
nothing was reviewed as a picture, and `step.implements` back-links were never
written. The flow-first vision was documented but unwired.

Two adversarial reviews and a runtime probe established the ground truth this
decision rests on:

- The **runtime workflow file is `templates/workflows-js/plan-feature.js`** (the
  E2 dialect built to `.claude/workflows/plan-feature.js`). The legacy
  `scripts/workflows/plan-feature.js` is dead for consumers.
- The workflow **cannot run raw git/filesystem calls** — every git/file
  operation is an agent dispatch (`commit`, `status-checker`). Any "is the store
  present" or "what did a prior run commit" step must therefore be an agent
  dispatch, and `log()` is a no-op under E2 (so an observable signal must also be
  a dispatch, not a log line).
- `business-analyst` **self-discovers the flow via `index.json`**; a `flow_ref`
  input is inert. It only *reports* a `flow_backlinks` map — it does NOT write
  `step.implements`. Closing that gap needs a dedicated reconciliation step.
- The feature was **already largely specified by existing approved/reviewed ACs**
  (UXP-491, UXP-401/401a, UXP-402/402a, UXP-530/531/592, UXP-540–543/594), so the
  work was to *wire and reconcile*, not to re-specify.

This ADR records how the four agents are wired into `/plan-feature` and the
contracts that keep the wiring safe.

## Decision

**`/plan-feature` gains an always-on product-truth (PT) phase, inserted after
`ac-triage`/covered-handling and before the AC pipeline. It classifies the
request, drafts only the artifacts the request needs (each behind a review gate,
each committed surgically), hands the approved flow to the business-analyst, and
reconciles the BA's reported back-links into the flow — degrading non-silently
when the store is unavailable.**

Seven rules realise this:

1. **Always-on classifier; run-set derived from the outcome.** `pt-classifier`
   is dispatched exactly once on every invocation. The set of artifact agents to
   run is derived from `classifier.outcome`
   (`full-set | mockup+data | mockup-only | mock-data-only | none`) via the
   canonical `OUTCOME_TO_STAGES` mapping — the row-for-row inverse of the
   validator's `OUTCOME_BY_COMBO`. The advisory `dispatch` array is **never
   trusted**: it is validated against the outcome and the outcome wins on
   disagreement. `outcome = none` (config / schema / docs) is today's behaviour —
   no PT agents, straight to the AC pipeline.

2. **Fixed authoring order.** The artifact agents always run in the fixed
   `PT_ORDER` `mock-data → mockup → flow`, filtered to the run-set. Ordering is
   deterministic regardless of the order the classifier happens to list agents in
   (a flow reads the mock data and mockups; a mockup reads the mock data).

3. **Per-stage gate + commit-before-next.** Each stage is presented at a review
   gate offering approve / edit / cancel. `edit` re-dispatches the same stage
   agent with the user's feedback (bounded retries) before re-gating. `approve`
   commits that stage's output **before** the next agent is dispatched; if the
   commit fails, the phase aborts and the next agent is never dispatched (the
   `BO-1500b-1` commit-before-next invariant, applied to the PT phase). `cancel`
   opens no PR, preserves every prior committed stage, and leaves the cancelled
   stage's draft uncommitted.

4. **Surgical commit staging.** A PT stage commit stages only the stage's reported
   artifact paths and their derived files plus `docs/product-truth/index.json`. A
   wholesale `git add docs/product-truth` is forbidden (it would drag unrelated
   derived churn), and `docs/acceptance-criteria/` is a **separate commit
   surface** excluded from PT commits — and conversely the AC-store commit never
   reaches into `docs/product-truth`. Commit subjects are
   `plan-feature(MOCK-DATA|MOCKUP|FLOW): <component>`.

5. **Protected-branch refusal (fail-closed).** `commitStageOutputProductTruth`
   reuses the no-main-commit guard: it confirms the authoring worktree's branch
   is not `main` (via a `status-checker` branch probe) and returns an error
   *without dispatching the commit agent* when the branch is `main` or cannot be
   confirmed non-main. This satisfies the In-Place Workflow Specs protected-branch
   AC policy for the PT commit surface.

6. **Flow → business-analyst, with reconciliation ownership.** The flow and its
   regenerated `index.json` are committed **before** the BA stage so the BA can
   self-discover the flow via `index.json` (the free-text derivation instruction
   carries the intent; `flow_ref` is inert). When the triage route is `technical`
   (which normally skips the BA) but a flow was produced, the BA stage is **forced
   in** with an L1 anchor so the derived L2s are not orphaned. **Flow-derived-AC
   parenting rule (orphan-prevention):** the flow→BA handoff instruction always parents
   every flow-derived L2/L3 under the run's L1 — under the triage `parent_l1_id` when
   present, otherwise under the component L1 (the product-owner-authored L1 on the
   strategic route for a net-new capability, else the flow's covering L1 via
   `index.json` `by_component`). In production the ordering `ac-triage → PT phase → AC
   pipeline` guarantees an anchor: a net-new capability routes `strategic`, so the PO
   authors an L1 before the BA derives from the flow (the E2E that surfaced the orphan
   risk bypassed triage, so no PO L1 existed — an E2E-shortcut artifact, not a
   production routing gap). The BA authors L2/L3 only and never invents an L1; if no
   component L1 exists it reports the gap rather than emitting an orphaned AC that
   `scan_ac_orphans.py` / `check_ac_parent_covered_by` would reject. After the BA runs,
   `docs/product-truth/scripts/apply_flow_backlinks.py` writes the BA's reported
   `flow_backlinks` into the flow's `step.implements[]` (union, order-preserving)
   and re-runs `generate_product_truth.py`. Because this re-mutates the
   already-committed flow, `index.json`, and the just-authored ACs' derived
   `product_truth` back-refs, it is a **dedicated reconciliation commit**, never
   folded into a stage commit. The reconciliation script — not the BA and not the
   generator — is the single owner of writing the authored flow→AC edge.

7. **Non-silent store-absent self-skip.** Before running any artifact agent (and
   only when the outcome is not `none`), the phase probes for
   `docs/product-truth/` and its scripts via a `status-checker` dispatch. If the
   store is absent (e.g. a consumer install where `build.py` does not deploy it,
   or an authoring worktree branched before the store landed), the phase emits an
   **observable, non-silent signal** (a telemetry/warning dispatch — never a
   silent no-op, because `log()` is inert under E2) and skips the PT phase; then
   `ac-triage` and the AC pipeline proceed normally. The phase can therefore never
   silently do nothing.

8. **New-entity admission is owned by `mock-data-author`.** `index.json`
   `entity_registry` is authoritative, hand-maintained vocabulary — *not* a
   generator-derived field. `generate_product_truth.py` recomputes only the derived
   indexes (`by_component` / `by_entity` / `by_flow` / `by_ac`) and
   `impl_status` / `impl_summary`; it never touches `entity_registry`, and
   `validate_product_truth.py` only *reads* it and hard-errors on any flow/mock/mockup
   entity missing from it. When a mock-data dataset introduces a genuinely-new entity
   (e.g. a net-new `Review`), the **`mock-data-author`** admits that name to
   `entity_registry` in the same `index.json` edit that registers the artifact in
   `artifacts[]`, then re-runs the generator/validator. The registry write lives in
   exactly one agent: `pt-classifier` (which only names entities), `mockup-author`, and
   `flow-author` consume the vocabulary and assume the introducer has admitted it. Prior
   to this, no agent admitted new entities (the mock-data-author template even said "the
   generator/validator own the registry", which they do not), so a genuinely-new entity
   stalled the pipeline on a hard validator error — the gap the plant-reviews E2E
   surfaced.

Crash-resume recognises the `plan-feature(<STAGE>)` commit subjects on the branch,
skips re-dispatching already-committed stages, and recovers the flow reference from
a committed `FLOW` commit so a resumed run still feeds the BA.

**Registry:** following the existing convention, plan-feature-dispatched agents
carry `spawned_by: ["user"]` and the workflow is not a registered caller (PO / BA
/ IT-PO prove this validates), so no registry change is required.

## Consequences

### Positive

- **The flow-first vision is actually executed.** `/plan-feature` now drafts a
  reviewable flow (plus mock data and mockups) and derives ACs from it, so ADR-020's
  upstream layer is realised rather than only documented.
- **Cannot silently no-op.** The store-absent path emits an observable signal and
  still runs AC authoring, so a missing store degrades loudly instead of quietly
  skipping product-truth work.
- **Safe commits.** Surgical staging, commit-before-next, the protected-branch
  refusal, and cancel-preserves-prior-commits mean a partial or aborted run leaves
  a clean, reviewable branch and never touches `main`.
- **Honest flow↔AC links.** `apply_flow_backlinks.py` owns writing
  `step.implements`, so the authored edge and every derived field
  (`impl_status`, `index.json` `by_ac`, each AC's `product_truth`) are regenerated
  consistently and idempotently.

### Negative

- **Cost and latency.** A `full-set` run adds two Opus agents (mock-data, flow)
  plus one Sonnet (mockup) and their gate/commit dispatches on top of the PO / BA /
  IT-PO pipeline. Only `pt-classifier` is Haiku.
- **Runtime depends on the store being deployed.** Until the product-truth store
  and its scripts are present at runtime, the phase self-skips (non-silently). The
  real assurance that the loop produces linked artifacts is a real-agent
  end-to-end run on the self-hosting tree; mocked/behavioural tests cannot prove
  the integrated loop on real data.
- **Reconciliation double-mutation.** The back-link reconciliation re-mutates
  already-committed flow / index / AC files and so requires its own commit path,
  designed explicitly rather than folded into a stage commit.

### Neutral

- The downstream AC pipeline (PO / BA / IT-PO, `scan_ac_store.py`,
  `generate_ticket_from_ac.py`) is unchanged; the PT phase feeds it a reviewed
  journey to decompose.
- Derived `impl_status` on the two meta-flows (`author-product-truth`,
  `define-a-feature`) is recomputed from AC `work_status` by the generator — never
  hand-edited (ADR-020 rule 3).

## Alternatives

### Alternative A — Trust the classifier's `dispatch` array for the run-set

Let the classifier emit an explicit list of agents to run and dispatch exactly
that.

**Rejected.** The `dispatch` array is advisory and can disagree with the
`outcome`. Deriving the run-set from `outcome` via the canonical
`OUTCOME_TO_STAGES` table (and treating `dispatch` as an inconsistency signal that
falls back to skipping PT) keeps one source of truth for routing and matches the
validator's `OUTCOME_BY_COMBO`.

### Alternative B — Have the business-analyst write `step.implements` directly

Let the BA both derive ACs and write the flow back-links in one pass.

**Rejected.** The BA self-discovers the flow and only *reports* `flow_backlinks`;
making it also mutate the committed flow would fold a re-mutation of already-committed
artifacts into an authoring stage and blur ownership of the authored edge. A
dedicated reconciliation script keeps the write single-owned, idempotent, and
unit-testable against a real on-disk flow.

### Alternative C — Silently skip the PT phase when the store is absent

Detect a missing store and quietly fall through to AC authoring.

**Rejected.** A silent skip is the phantom-done failure mode this repo exists to
prevent: the workflow would appear to run the product-truth way while doing
nothing. The skip must emit an observable signal (an agent dispatch, since `log()`
is inert under E2).

### Alternative D — Wholesale-commit `docs/product-truth/**` after each stage

Stage the whole store directory on each PT commit.

**Rejected.** A blanket add drags unrelated derived churn into a stage commit and
violates the surgical-staging invariant. Committing only the reported artifact
paths plus `index.json`, on a surface separate from `docs/acceptance-criteria/`,
keeps each commit scoped and reviewable.

## References

- [ADR-020 — Product-Truth Store as the Flow-First Upstream Layer](ADR-020-product-truth-flow-first-upstream-layer.md) — the store this phase authors into.
- [ADR-010 — AC Store as Authoritative Backlog](ADR-010-ac-store-as-authoritative-backlog.md) — the backlog the derived ACs populate.
- `templates/workflows-js/plan-feature.js` — the E2 runtime workflow the PT phase is wired into.
- `docs/product-truth/scripts/apply_flow_backlinks.py` — the reconciliation script that writes `step.implements` and re-runs the generator.
- `docs/product-truth/scripts/generate_product_truth.py` — the single writer of derived `impl_status` / `product_truth` back-refs.
- [templates/skills/plan-feature/SKILL.md](../../../templates/skills/plan-feature/SKILL.md) — the skill surface documenting the PT phase.
- AC coverage: UXP-595 (L1) and UXP-544–549 / UXP-595a; reconciled UXP-401, UXP-402, UXP-530, UXP-543.
