---
title: "Re-verified all 18 open known-issues entries mentioning /plan-feature against current code"
date: "2026-09-23"
time: "14:45"
type: manual
components: 
  - ac_driven_dev
  - build_orchestration
  - build_pipeline
  - commit_guardian
  - agent_registry
  - supervisor_system
summary: "Audited every open known-issue tied to the /plan-feature workflow against the code as it stands today, closing four that were already fixed and sharpening the evidence on the rest."
description: "Docs-only, one commit. Eighteen open entries across six known-issues registers (ac-driven-dev, build-orchestration, build-pipeline, commit-guardian, agent-registry, supervisor-system) were re-checked against current code rather than each entry's own narrative. FIVE resolved (KI-BO-018, a confirmed duplicate of the already-resolved KI-ACD-009; KI-CG-005; KI-ACD-006; KI-BO-032; KI-BO-027) — and notably four of the five were fixed by work unrelated to the ACD-2100 epic, which the registers had never caught up to. Five confirmed still true with fresh dated evidence, most consequentially KI-ACD-007: product-truth artifacts still land in the user's main checkout, because ptStoreDir was never given the worktree-isolation fix that the AC store received. Five amended with explicit new closure conditions (KI-ACD-008, KI-ACD-019, KI-BP-007, KI-BP-012, KI-AR-001). One left open as cannot-determine (KI-SS-001 — a property of the agent harness, not repo code; a blocker is not closed merely because it could not be reproduced). All register header counts recomputed from table rows: ac-driven-dev 27 to 26, build-orchestration 51 to 48, commit-guardian 70 to 69."
commits: 
  - b3b905f6
breaking: false
---

## Entry

Eighteen open known-issues entries mention `/plan-feature`. Each was re-checked
against the code as it stands, by reading what the entry names and running it
where that was cheap — not by reasoning from the entry's own narrative, and not
by assuming the recently-merged ACD-2100 epic had fixed anything.

### Resolved (5)

- **KI-BO-018** (blocker) — `/plan-feature`'s false `worktree-agent` permission
  halt. Both halves are gone: no agent-relayed registry read remains in the
  workflow, and repo-root resolution goes through `git rev-parse
  --git-common-dir` with a sibling-directory fallback. Confirmed a **duplicate**
  of the already-resolved `KI-ACD-009` — the same mechanism filed in a second
  register — and cross-linked rather than quietly closed.
- **KI-CG-005** (blocker) — product-truth hooks hard-failing on an absent,
  explicitly optional store, gating every AC YAML commit. Verified by
  reproducing the reported scenario in a scratch store: the validator returns
  `{"outcome": "nothing-examined"}` and exits 0.
- **KI-ACD-006** — a run authoring zero ACs reporting `status: "ok"`. All three
  cancel sites now return `"cancelled"`.
- **KI-BO-032**, **KI-BO-027**.

Four of these five were fixed by work unrelated to ACD-2100, some of it weeks
old. That is the more useful finding: register entries rot silently, and a stale
blocker costs a reader the same attention as a live one.

### Still true (5)

Most consequential is **KI-ACD-007**. `acStoreDir` is overridden from the
worktree payload, but `ptStoreDir` is a `const` relative literal handed to the
authoring dispatch as-is — so the worktree-isolation fix landed for the AC store
and was never mirrored to the product-truth store, and product-truth artifacts
still land in the user's main checkout.

**KI-CG-20260831-1933** was reproduced end-to-end in a scratch repo, and
surfaced a second defect alongside it: `commit_guardian.json` ships
`"strict": true` for `check-predone-scope` while both of its own `_comment`
blocks describe it as advisory-by-default, so the blocking path is what a fresh
install actually gets.

Also still true: **KI-BO-20260901-1620**, **KI-BP-20260826-1331**,
**KI-AR-002**.

### Partially fixed (5)

`KI-ACD-008`, `KI-ACD-019`, `KI-BP-007`, `KI-BP-012`, `KI-AR-001` — each Status
line now says precisely what closed, what remains, and the new closure
condition.

`KI-BP-012`'s amendment was softened in review before landing. The audit
concluded that `/plan-feature`'s pre-flight depends on a path no build phase
deploys and that a consumer therefore fails closed. The declaration point is
correct and stands; the "broken today" reading is contradicted by measurement —
`unit_tests/portability/test_acd_2100d_1.py` and `test_acd_2100d_3.py` build a
real install and assert the installed route reaches the same first question as
source, and they pass. The entry now records a latent invariant rather than an
observed consumer failure.

### Cannot determine (1)

**KI-SS-001** (blocker) — a backgrounded sub-agent that waits is a property of
the agent harness, not something readable from repo code. Left open with the
attempt recorded. A blocker is not closed because it could not be reproduced.
