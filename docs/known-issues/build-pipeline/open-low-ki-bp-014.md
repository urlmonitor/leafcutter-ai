---
title: "KI-BP-014 — The commit agent can stall indefinitely waiting on the autofix agent it dispatched, leaving a fully-staged commit unmade and no error"
description: "KI-BP-014 — The commit agent can stall indefinitely waiting on the autofix agent it dispatched, leaving a fully-staged commit unmade and no error"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - build_pipeline
related_docs:
  - docs/known-issues/build-pipeline.md
  - docs/known-issues/README.md
---

# KI-BP-014 — The commit agent can stall indefinitely waiting on the autofix agent it dispatched, leaving a fully-staged commit unmade and no error

> One known issue, split out of `docs/known-issues/build-pipeline.md` on
> 2026-09-14. Index: [build-pipeline.md](../build-pipeline.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** the pre-commit-failure → `precommit-autofix` → retry path in the `commit` agent template

**Symptom.** The commit agent hit a `check-ac-schema` failure, dispatched the autofix agent as
designed, and then never retried. It returned after **~76 minutes** with the message *"HEAD
confirmed unchanged (commit did not silently land). Waiting for the autofix agent to complete
before retrying."* — a status update, not a result. The autofix agent had in fact completed
successfully and applied a correct one-line fix.

**State it left behind.** Benign but easy to misread: all five intended files correctly staged,
`HEAD` unchanged, nothing lost. The agent's own report was accurate about what it had *not* done,
which is the reason nothing broke. But no commit existed, no error was raised, and the caller had
no signal other than the elapsed time.

**Why it is worth an entry.** The failure mode is a hang, not a crash, so nothing surfaces it —
no timeout, no failed status, no retry cap. From the caller's side it is indistinguishable from
"still working" for as long as you are willing to wait. Recovery was trivial once noticed
(re-run the hooks, confirm they pass, commit from the main loop with `COMMIT_AGENT_MODE=1`), but
noticing depended on a human wondering why it was taking so long.

**What this does NOT indicate.** The autofix path itself worked: the fix was correct and its
report was accurate and well-reasoned. The gap is purely in the parent's wait-and-retry step.

**Fix direction.** Bound the wait and make the outcome explicit. The parent should either
re-check the hooks and retry once the child reports completion, or return a `blocker` naming the
autofix agent and the hook that failed. "Waiting" is not a terminal state a caller can act on.

---
